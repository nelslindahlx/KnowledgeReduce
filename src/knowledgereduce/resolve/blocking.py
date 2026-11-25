"""Sub-quadratic 3-stage blocking and clustering for claim deduplication."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from rapidfuzz import fuzz
from sklearn.cluster import AgglomerativeClustering, MiniBatchKMeans

from knowledgereduce.models import Claim
from knowledgereduce.resolve.embeddings import EmbeddingProvider, TfidfSVDProvider

_WS_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"[a-z0-9]{3,}")
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_APA_REF_RE = re.compile(r"^[A-Z][a-zA-Z'-]+,\s+[A-Z]\.(?:\s*[A-Z]\.)?")


@dataclass(frozen=True, slots=True)
class _ClaimMergeFeatures:
    """Precomputed O(N) claim features for fast Stage 2/Stage 3 merge checks."""

    subject_id: str | None
    norm_pred: str
    is_functional: bool
    norm_val: str
    object_id: str | None
    is_apa_ref: bool
    years: frozenset[str]
    numbers: frozenset[str]
    norm_stmt: str
    ends_punct: bool


def _resolve_functional_vocab(
    functional_predicates: frozenset[str] | None,
) -> frozenset[str]:
    """Resolve the functional predicate set without introducing a module import cycle."""
    if functional_predicates is not None:
        return functional_predicates
    # Lazy import avoids a circular import while reduce.__init__ loads reducer -> resolve.
    from knowledgereduce.reduce.conflicts import DEFAULT_FUNCTIONAL_PREDICATES

    return DEFAULT_FUNCTIONAL_PREDICATES


def _is_functional_predicate(predicate: str, functional_vocab: frozenset[str]) -> bool:
    norm = predicate.strip().upper()
    return norm in functional_vocab or norm.endswith(("_IN", "_AT", "_ON", "_YEAR", "_DATE"))


def _extract_merge_features(
    claim: Claim,
    functional_vocab: frozenset[str],
) -> _ClaimMergeFeatures:
    """Extract normalized statement, predicate, and numeric features once per claim."""
    stripped = claim.statement.strip()
    norm_pred = claim.predicate.strip().upper() if claim.predicate else ""
    is_func = bool(norm_pred) and _is_functional_predicate(norm_pred, functional_vocab)
    norm_val = (claim.object_literal or claim.object_id or "").strip().lower()
    return _ClaimMergeFeatures(
        subject_id=claim.subject_id,
        norm_pred=norm_pred,
        is_functional=is_func,
        norm_val=norm_val,
        object_id=claim.object_id,
        is_apa_ref=bool(_APA_REF_RE.match(stripped)),
        years=frozenset(_YEAR_RE.findall(claim.statement)),
        numbers=frozenset(_NUMBER_RE.findall(claim.statement)),
        norm_stmt=normalize_text(stripped),
        ends_punct=stripped.endswith((".", "!", "?")),
    )


def _features_compatible(a: _ClaimMergeFeatures, b: _ClaimMergeFeatures) -> bool:
    """Return False when precomputed features assert differing facts, years, or APA citations."""
    if (
        a.subject_id
        and b.subject_id
        and a.norm_pred
        and a.subject_id == b.subject_id
        and a.norm_pred == b.norm_pred
    ):
        if a.is_functional:
            if a.norm_val and b.norm_val and a.norm_val != b.norm_val:
                return False
        elif a.object_id and b.object_id and a.object_id != b.object_id:
            return False

    if a.is_apa_ref != b.is_apa_ref:
        return False

    if bool(a.years) != bool(b.years):
        undated = b if a.years else a
        dated = a if a.years else b
        # Allow an unpunctuated heading/fragment subsumed verbatim inside a longer dated
        # sentence to merge so the full dated sentence absorbs it without fact loss.
        is_subsumed_fragment = (
            bool(undated.norm_stmt)
            and not undated.ends_punct
            and len(dated.norm_stmt) > len(undated.norm_stmt)
            and undated.norm_stmt in dated.norm_stmt
        )
        if not is_subsumed_fragment:
            return False

    return not (a.numbers and b.numbers and a.numbers != b.numbers)


def _claims_compatible_for_merge(
    a: Claim,
    b: Claim,
    functional_vocab: frozenset[str] | None = None,
) -> bool:
    """Return False when two claims assert differing facts, years, or APA citations."""
    vocab = functional_vocab if functional_vocab is not None else _resolve_functional_vocab(None)
    return _features_compatible(
        _extract_merge_features(a, vocab),
        _extract_merge_features(b, vocab),
    )


class DisjointSet:
    """Path-compressed Union-Find structure for deterministic equivalence classes."""

    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, x: int) -> int:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            nxt = self.parent[x]
            self.parent[x] = root
            x = nxt
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1

    def groups(self) -> list[list[int]]:
        buckets: dict[int, list[int]] = defaultdict(list)
        for i in range(len(self.parent)):
            buckets[self.find(i)].append(i)
        return list(buckets.values())


def normalize_text(text: str) -> str:
    """Normalize whitespace and casing for exact-duplicate detection."""
    return _WS_RE.sub(" ", text.strip().lower())


def _token_blocking_keys(norm_text: str) -> list[str]:
    tokens = _WORD_RE.findall(norm_text)
    if not tokens:
        return [f"len_{len(norm_text) // 10}"]
    # Sort longest/rarest-looking tokens plus length bucket so overlapping facts share keys.
    top_tokens = sorted(set(tokens), key=lambda tok: (-len(tok), tok))[:4]
    len_bucket = len(norm_text) // 40
    return [f"{len_bucket}:{tok}" for tok in top_tokens]


def _cluster_dense_bucket(
    vectors: np.ndarray,
    bucket_claims: Sequence[Claim],
    semantic_threshold: float,
    *,
    functional_vocab: frozenset[str],
    bucket_features: Sequence[_ClaimMergeFeatures] | None = None,
) -> list[list[int]]:
    n = vectors.shape[0]
    if n <= 1:
        return [[0]] if n == 1 else []
    features = (
        bucket_features
        if bucket_features is not None
        else [_extract_merge_features(clm, functional_vocab) for clm in bucket_claims]
    )
    sim = np.matmul(vectors, vectors.T)
    dist = np.clip(1.0 - sim, 0.0, 2.0)
    np.fill_diagonal(dist, 0.0)
    for i in range(n):
        fi = features[i]
        for j in range(i + 1, n):
            if not _features_compatible(fi, features[j]):
                dist[i, j] = 2.0
                dist[j, i] = 2.0

    threshold = max(0.01, min(1.99, 1.0 - semantic_threshold))
    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=threshold,
        metric="precomputed",
        linkage="average",
    )
    labels = clustering.fit_predict(dist)
    groups: dict[int, list[int]] = defaultdict(list)
    for idx, label in enumerate(labels):
        groups[int(label)].append(idx)

    # Guard against average-linkage gluing two mutually incompatible claims through a bridge node.
    safe_groups: list[list[int]] = []
    for raw_group in groups.values():
        subgroups: list[list[int]] = []
        for idx in raw_group:
            placed = False
            f_idx = features[idx]
            for sg in subgroups:
                if all(_features_compatible(f_idx, features[other]) for other in sg):
                    sg.append(idx)
                    placed = True
                    break
            if not placed:
                subgroups.append([idx])
        safe_groups.extend(subgroups)
    return safe_groups


def cluster_claims(
    claims: Sequence[Claim],
    *,
    lexical_threshold: float = 0.88,
    semantic_threshold: float = 0.84,
    min_length: int = 20,
    embedding_provider: EmbeddingProvider | None = None,
    dense_cluster_limit: int = 400,
    functional_predicates: frozenset[str] | None = None,
) -> tuple[list[list[Claim]], list[Claim]]:
    """Group duplicate/near-duplicate claims into clusters without dropping representatives.

    Returns ``(clusters, dropped_short_claims)``.
    """
    functional_vocab = _resolve_functional_vocab(functional_predicates)
    kept: list[Claim] = []
    dropped: list[Claim] = []
    for clm in claims:
        has_structured_triple = bool(clm.subject_id and clm.predicate)
        if len(clm.statement.strip()) < min_length and not has_structured_triple:
            dropped.append(clm)
        else:
            kept.append(clm)

    if not kept:
        return [], dropped
    if len(kept) == 1:
        return [[kept[0]]], dropped

    # Stage 1: Exact normalized SHA-256 deduplication (O(N)).
    exact_groups: dict[str, list[Claim]] = defaultdict(list)
    for clm in kept:
        key = hashlib.sha256(normalize_text(clm.statement).encode("utf-8")).hexdigest()
        exact_groups[key].append(clm)
    stage1_clusters = list(exact_groups.values())

    if len(stage1_clusters) == 1:
        return stage1_clusters, dropped

    # Stage 2: Blocked lexical similarity over precomputed Stage 1 cluster heads.
    n_s1 = len(stage1_clusters)
    s1_features = [_extract_merge_features(group[0], functional_vocab) for group in stage1_clusters]
    s1_norms = [feat.norm_stmt for feat in s1_features]
    block_index: dict[str, list[int]] = defaultdict(list)
    for idx, norm in enumerate(s1_norms):
        for bkey in _token_blocking_keys(norm):
            block_index[bkey].append(idx)

    dsu = DisjointSet(n_s1)
    cutoff = lexical_threshold * 100.0
    checked_pairs: set[tuple[int, int]] = set()
    for members in block_index.values():
        if len(members) < 2 or len(members) > 250:
            continue
        for i_pos in range(len(members)):
            i = members[i_pos]
            fi = s1_features[i]
            norm_i = s1_norms[i]
            for j_pos in range(i_pos + 1, len(members)):
                j = members[j_pos]
                pair = (i, j) if i < j else (j, i)
                if pair in checked_pairs or dsu.find(i) == dsu.find(j):
                    continue
                checked_pairs.add(pair)
                if (
                    _features_compatible(fi, s1_features[j])
                    and fuzz.token_sort_ratio(norm_i, s1_norms[j]) >= cutoff
                ):
                    dsu.union(i, j)

    stage2_clusters: list[list[Claim]] = []
    s2_features: list[_ClaimMergeFeatures] = []
    for idx_group in dsu.groups():
        merged: list[Claim] = []
        for idx in idx_group:
            merged.extend(stage1_clusters[idx])
        stage2_clusters.append(merged)
        s2_features.append(s1_features[idx_group[0]])

    if len(stage2_clusters) < 2:
        return stage2_clusters, dropped

    # Stage 3: Semantic clustering over Stage 2 representatives.
    provider = embedding_provider or TfidfSVDProvider()
    rep_texts = [group[0].statement for group in stage2_clusters]
    vectors = provider.embed(rep_texts)

    if vectors.shape[0] < 2 or vectors.shape[1] == 0:
        return stage2_clusters, dropped

    n_s2 = len(stage2_clusters)
    final_clusters: list[list[Claim]] = []

    s2_reps = [group[0] for group in stage2_clusters]
    if n_s2 <= dense_cluster_limit:
        for idx_group in _cluster_dense_bucket(
            vectors,
            s2_reps,
            semantic_threshold,
            functional_vocab=functional_vocab,
            bucket_features=s2_features,
        ):
            combined: list[Claim] = []
            for idx in idx_group:
                combined.extend(stage2_clusters[idx])
            final_clusters.append(combined)
        return final_clusters, dropped

    # Sub-quadratic coarse partitioning for large datasets (10K-100K+ claims).
    n_coarse = max(2, min(n_s2 // 150, 256))
    kmeans = MiniBatchKMeans(
        n_clusters=n_coarse,
        random_state=42,
        n_init=3,
        batch_size=min(1024, n_s2),
    )
    coarse_labels = kmeans.fit_predict(vectors)
    buckets: dict[int, list[int]] = defaultdict(list)
    for idx, label in enumerate(coarse_labels):
        buckets[int(label)].append(idx)

    for bucket_indices in buckets.values():
        if len(bucket_indices) == 1:
            final_clusters.append(stage2_clusters[bucket_indices[0]])
            continue
        # Sub-partition unusually dense coarse buckets so AgglomerativeClustering stays bounded.
        for start in range(0, len(bucket_indices), dense_cluster_limit):
            sub_indices = bucket_indices[start : start + dense_cluster_limit]
            sub_vecs = vectors[sub_indices]
            sub_reps = [s2_reps[idx] for idx in sub_indices]
            sub_feats = [s2_features[idx] for idx in sub_indices]
            for local_group in _cluster_dense_bucket(
                sub_vecs,
                sub_reps,
                semantic_threshold,
                functional_vocab=functional_vocab,
                bucket_features=sub_feats,
            ):
                combined = []
                for local_idx in local_group:
                    orig_idx = sub_indices[local_idx]
                    combined.extend(stage2_clusters[orig_idx])
                final_clusters.append(combined)

    return final_clusters, dropped
