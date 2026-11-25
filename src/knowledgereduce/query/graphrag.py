"""Hybrid GraphRAG retriever combining lexical, embedding similarity, and graph expansion."""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from rapidfuzz import fuzz

from knowledgereduce.models import Claim, ConflictRecord, Entity, ReliabilityRating
from knowledgereduce.query.analytics import k_hop_neighborhood
from knowledgereduce.resolve.embeddings import EmbeddingProvider, HashingEmbeddingProvider
from knowledgereduce.storage.base import (
    _SEARCH_STOP_WORDS,
    ClaimSummary,
    GraphStore,
    filter_matching_conflicts,
    tokenize_search_query,
)


@runtime_checkable
class _SummaryCapableStore(Protocol):
    def search_claim_summaries_lexical(
        self,
        layer_id: str,
        query: str,
        *,
        min_reliability: ReliabilityRating = ReliabilityRating.UNKNOWN,
        limit: int = 200,
    ) -> list[ClaimSummary]: ...

    def get_claim_summaries_by_ids(
        self, layer_id: str, claim_ids: Sequence[str]
    ) -> list[ClaimSummary]: ...


_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")
_HEADING_PREFIX_RE = re.compile(r"^(?:Chapter|Section|Part|Appendix)\s*(?:\d+|[IVXLCDM]+)?[:\s]")
_DIGIT_RE = re.compile(r"\d")


def _is_structural_heading(statement: str) -> bool:
    stripped = statement.strip()
    if not stripped or stripped[-1] in ".!?":
        return False
    if _HEADING_PREFIX_RE.match(stripped):
        return True
    if _DIGIT_RE.search(stripped):
        return False
    words = stripped.split()
    if not (2 <= len(words) <= 10):
        return False
    content_words = [w for w in words if w.lower() not in _SEARCH_STOP_WORDS]
    if not content_words:
        return False
    cap_count = sum(1 for w in content_words if w[0].isupper())
    return (cap_count / len(content_words)) >= 0.70


class RetrievedClaim(BaseModel):
    """Single claim result returned by Hybrid GraphRAG retrieval."""

    model_config = ConfigDict(extra="forbid")

    claim: Claim
    score: float
    lexical_score: float
    semantic_score: float
    graph_neighbors: list[dict[str, str]] = Field(default_factory=list)
    conflicts: list[ConflictRecord] = Field(default_factory=list)


class RetrievedContext(BaseModel):
    """Grounded multi-hop context bundle for downstream consumption or agent reasoning."""

    model_config = ConfigDict(extra="forbid")

    layer_id: str
    query: str
    results: list[RetrievedClaim] = Field(default_factory=list)
    related_entities: list[Entity] = Field(default_factory=list)
    conflicts: list[ConflictRecord] = Field(default_factory=list)


class HybridGraphRAGRetriever:
    """Combines lexical matching, vector similarity, and graph neighborhood expansion."""

    def __init__(
        self,
        store: GraphStore,
        *,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.store = store
        self.embedding_provider = embedding_provider or HashingEmbeddingProvider()

    def build_index(self, layer_id: str) -> int:
        """Precompute and persist claim embeddings for stateless embedding providers."""
        if not bool(getattr(self.embedding_provider, "is_stateless", False)):
            return 0
        model_id = str(getattr(self.embedding_provider, "model_id", "custom"))
        pairs = self.store.list_claim_texts(layer_id)
        claim_ids = [cid for cid, _stmt in pairs]
        statements = [stmt for _cid, stmt in pairs]
        vectors = self.embedding_provider.embed(statements)
        self.store.save_claim_embeddings(layer_id, claim_ids, vectors, model_id=model_id)
        return len(claim_ids)

    def retrieve(
        self,
        layer_id: str,
        query: str,
        *,
        top_k: int = 5,
        hops: int = 1,
        min_reliability: ReliabilityRating = ReliabilityRating.UNKNOWN,
        candidate_pool_size: int = 200,
    ) -> RetrievedContext:
        """Retrieve ranked claims, connected entities, and open conflict context."""
        if top_k <= 0:
            return RetrievedContext(layer_id=layer_id, query=query)

        is_stateless = bool(getattr(self.embedding_provider, "is_stateless", False))
        if is_stateless:
            model_id = str(getattr(self.embedding_provider, "model_id", "custom"))
            loaded_idx = self.store.load_claim_embeddings(layer_id, model_id=model_id)
            if loaded_idx is None:
                built = self.build_index(layer_id)
                if built == 0:
                    return RetrievedContext(layer_id=layer_id, query=query)
                loaded_idx = self.store.load_claim_embeddings(layer_id, model_id=model_id)
            if loaded_idx is None or not loaded_idx[0]:
                return RetrievedContext(layer_id=layer_id, query=query)

            idx_ids, idx_vecs = loaded_idx
            q_vecs = self.embedding_provider.embed([query])
            if idx_vecs.ndim == 2 and idx_vecs.shape[0] == len(idx_ids) and q_vecs.size > 0:
                q_vec = q_vecs[0]
                all_sem = np.clip(idx_vecs @ q_vec, 0.0, 1.0)
            else:
                all_sem = np.zeros(len(idx_ids), dtype=np.float32)

            id_to_sem = {cid: float(all_sem[i]) for i, cid in enumerate(idx_ids)}
            pool = max(candidate_pool_size, top_k * 20)
            if isinstance(self.store, _SummaryCapableStore):
                lexical_summaries = self.store.search_claim_summaries_lexical(
                    layer_id,
                    query,
                    min_reliability=min_reliability,
                    limit=pool,
                )
                lexical_ids = {c.claim_id for c in lexical_summaries}

                if len(idx_ids) > pool:
                    top_indices = np.argpartition(all_sem, -pool)[-pool:]
                    top_sem_ids = [idx_ids[int(i)] for i in top_indices]
                else:
                    top_sem_ids = list(idx_ids)

                missing_ids = [cid for cid in top_sem_ids if cid not in lexical_ids]
                semantic_summaries = (
                    [
                        c
                        for c in self.store.get_claim_summaries_by_ids(layer_id, missing_ids)
                        if int(c.reliability) >= int(min_reliability)
                    ]
                    if missing_ids
                    else []
                )
                candidates: list[Claim | ClaimSummary] = [
                    *lexical_summaries,
                    *semantic_summaries,
                ]
            else:
                lexical_claims = self.store.search_claims_lexical(
                    layer_id,
                    query,
                    min_reliability=min_reliability,
                    limit=pool,
                )
                lexical_ids = {c.claim_id for c in lexical_claims}

                if len(idx_ids) > pool:
                    top_indices = np.argpartition(all_sem, -pool)[-pool:]
                    top_sem_ids = [idx_ids[int(i)] for i in top_indices]
                else:
                    top_sem_ids = list(idx_ids)

                missing_ids = [cid for cid in top_sem_ids if cid not in lexical_ids]
                semantic_claims = (
                    [
                        c
                        for c in self.store.get_claims_by_ids(layer_id, missing_ids)
                        if int(c.reliability) >= int(min_reliability)
                    ]
                    if missing_ids
                    else []
                )
                candidates = [*lexical_claims, *semantic_claims]

            if not candidates:
                return RetrievedContext(layer_id=layer_id, query=query)
            sem_scores = [id_to_sem.get(c.claim_id, 0.0) for c in candidates]
        else:
            layer_data = self.store.load_layer(layer_id)
            candidates = [
                c for c in layer_data.claims if int(c.reliability) >= int(min_reliability)
            ]
            if not candidates:
                return RetrievedContext(layer_id=layer_id, query=query)

            texts = [c.statement for c in candidates]
            vectors = self.embedding_provider.embed([query, *texts])
            if vectors.shape[0] == len(candidates) + 1 and vectors.shape[1] > 0:
                q_vec = vectors[0]
                doc_vecs = vectors[1:]
                sem_scores = np.clip(doc_vecs @ q_vec, 0.0, 1.0).tolist()
            else:
                sem_scores = [0.0] * len(candidates)

        q_low = query.strip().lower()
        q_tokens_list = tokenize_search_query(query, max_tokens=24)
        q_tokens = set(q_tokens_list)
        q_fuzzy_str = " ".join(sorted(q_tokens)) if q_tokens else q_low

        candidate_token_sets: list[set[str]] = []
        df: dict[str, int] = dict.fromkeys(q_tokens, 0)
        for clm in candidates:
            s_toks = set(_TOKEN_RE.findall(clm.statement.lower()))
            candidate_token_sets.append(s_toks)
            for q_tok in q_tokens:
                if q_tok in s_toks:
                    df[q_tok] += 1

        n_cands = len(candidates)
        idf: dict[str, float] = {
            tok: math.log((1.0 + n_cands) / (1.0 + count)) + 1.0 for tok, count in df.items()
        }
        total_q_idf = sum(idf.values())
        wants_chapter = "chapter" in q_tokens

        scored: list[tuple[Claim | ClaimSummary, float, float, float]] = []
        for idx, clm in enumerate(candidates):
            s_tokens = candidate_token_sets[idx]
            matched_stmt = q_tokens & s_tokens
            idf_overlap = (
                sum(idf[tok] for tok in matched_stmt) / total_q_idf if total_q_idf > 0 else 0.0
            )

            s_content = s_tokens - _SEARCH_STOP_WORDS
            s_fuzzy_str = " ".join(sorted(s_content if s_content else s_tokens))
            fuzzy_part = (
                fuzz.token_set_ratio(q_fuzzy_str, s_fuzzy_str) / 100.0
                if q_fuzzy_str and s_fuzzy_str
                else 0.0
            )

            context_bonus = 0.0
            unmatched_q = q_tokens - matched_stmt
            if matched_stmt and unmatched_q and total_q_idf > 0:
                provenance_text = (
                    f"{clm.source_title} {clm.author_creator or ''} {clm.contextual_notes}"
                ).lower()
                prov_tokens = set(_TOKEN_RE.findall(provenance_text))
                prov_hits = unmatched_q & prov_tokens
                if prov_hits:
                    context_bonus = 0.20 * (sum(idf[tok] for tok in prov_hits) / total_q_idf)

            lex = min(1.0, 0.65 * idf_overlap + 0.35 * fuzzy_part + context_bonus)
            sem = float(sem_scores[idx])
            if not wants_chapter and _is_structural_heading(clm.statement):
                lex *= 0.75
                sem *= 0.75

            qual = clm.quality_score / 100.0
            total = round(0.55 * lex + 0.35 * sem + 0.10 * qual, 4)
            scored.append((clm, total, round(lex, 4), round(sem, 4)))

        scored.sort(key=lambda item: (-item[1], item[0].claim_id))
        top_winners = scored[:top_k]
        need_hydrate = [
            item[0].claim_id for item in top_winners if isinstance(item[0], ClaimSummary)
        ]
        hydrated_map = (
            {c.claim_id: c for c in self.store.get_claims_by_ids(layer_id, need_hydrate)}
            if need_hydrate
            else {}
        )
        top_items: list[tuple[Claim, float, float, float]] = []
        for cand_item, total, lex, sem in top_winners:
            if isinstance(cand_item, Claim):
                top_items.append((cand_item, total, lex, sem))
            elif cand_item.claim_id in hydrated_map:
                top_items.append((hydrated_map[cand_item.claim_id], total, lex, sem))

        seed_ids = [clm.claim_id for clm, _total, _lex, _sem in top_items]
        graph, sub_entities, sub_conflicts = self.store.get_k_hop_subgraph(
            layer_id,
            seed_ids,
            hops=hops,
        )
        entity_map = {e.entity_id: e for e in sub_entities}
        collected_entities: dict[str, Entity] = {}
        collected_conflicts: dict[str, ConflictRecord] = {}
        results: list[RetrievedClaim] = []

        for clm, total, lex, sem in top_items:
            neighbors: list[dict[str, str]] = []
            seen_neighbor_edges: set[tuple[str, str, str]] = set()
            if clm.claim_id in graph and hops > 0:
                sub = k_hop_neighborhood(graph, clm.claim_id, k=hops, directed=False)
                for src, dst, _key, attrs in sub.edges(keys=True, data=True):
                    rel_type = str(attrs.get("relation_type", ""))
                    edge_sig = (str(src), str(dst), rel_type)
                    if edge_sig in seen_neighbor_edges:
                        continue
                    seen_neighbor_edges.add(edge_sig)
                    if src == clm.claim_id and dst in sub.nodes:
                        other = dst
                        label = str(sub.nodes[dst].get("label", dst))
                    elif dst == clm.claim_id and src in sub.nodes:
                        other = src
                        label = str(sub.nodes[src].get("label", src))
                    elif src in sub.nodes and dst in sub.nodes:
                        other = dst
                        src_label = str(sub.nodes[src].get("label", src))
                        dst_label = str(sub.nodes[dst].get("label", dst))
                        label = f"{src_label} -> {dst_label}"
                    else:
                        continue
                    neighbors.append(
                        {
                            "node_id": str(other),
                            "relation_type": rel_type,
                            "label": label,
                            "source_id": str(src),
                            "target_id": str(dst),
                        }
                    )
                for node_id in sub.nodes():
                    if node_id in entity_map:
                        collected_entities[node_id] = entity_map[node_id]

            # Match conflicts touching this claim ID
            claim_conflicts = filter_matching_conflicts(sub_conflicts, {clm.claim_id})
            for cf in claim_conflicts:
                collected_conflicts[cf.conflict_id] = cf

            results.append(
                RetrievedClaim(
                    claim=clm,
                    score=total,
                    lexical_score=lex,
                    semantic_score=sem,
                    graph_neighbors=neighbors,
                    conflicts=claim_conflicts,
                )
            )

        return RetrievedContext(
            layer_id=layer_id,
            query=query,
            results=results,
            related_entities=list(collected_entities.values()),
            conflicts=list(collected_conflicts.values()),
        )
