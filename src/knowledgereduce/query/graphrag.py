"""Hybrid GraphRAG retriever combining lexical, embedding similarity, and graph expansion."""

from __future__ import annotations

import re

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from rapidfuzz import fuzz

from knowledgereduce.models import Claim, ConflictRecord, Entity, ReliabilityRating
from knowledgereduce.query.analytics import k_hop_neighborhood
from knowledgereduce.resolve.embeddings import EmbeddingProvider, TfidfSVDProvider
from knowledgereduce.storage.base import GraphStore

_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


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
        self.embedding_provider = embedding_provider or TfidfSVDProvider()

    def retrieve(
        self,
        layer_id: str,
        query: str,
        *,
        top_k: int = 5,
        hops: int = 1,
        min_reliability: ReliabilityRating = ReliabilityRating.UNKNOWN,
    ) -> RetrievedContext:
        """Retrieve ranked claims, connected entities, and open conflict context."""
        layer_data = self.store.load_layer(layer_id)
        candidates = [c for c in layer_data.claims if int(c.reliability) >= int(min_reliability)]
        if not candidates or top_k <= 0:
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
        q_tokens = set(_TOKEN_RE.findall(q_low))

        scored: list[tuple[Claim, float, float, float]] = []
        for idx, clm in enumerate(candidates):
            stmt_low = clm.statement.lower()
            s_tokens = set(_TOKEN_RE.findall(stmt_low))
            tok_overlap = len(q_tokens & s_tokens) / len(q_tokens) if q_tokens else 0.0
            fuzzy_part = fuzz.token_set_ratio(q_low, stmt_low) / 100.0 if q_low else 0.0
            lex = 0.6 * tok_overlap + 0.4 * fuzzy_part
            sem = float(sem_scores[idx])
            qual = clm.quality_score / 100.0
            total = round(0.45 * lex + 0.45 * sem + 0.10 * qual, 4)
            scored.append((clm, total, round(lex, 4), round(sem, 4)))

        scored.sort(key=lambda item: (-item[1], item[0].claim_id))
        top_items = scored[:top_k]

        graph = self.store.to_networkx(layer_id)
        entity_map = {e.entity_id: e for e in layer_data.entities}
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
            claim_conflicts = [
                cf
                for cf in layer_data.conflicts
                if any(clm.claim_id in (cand.get("claim_ids") or []) for cand in cf.candidates)
                or cf.target_key == clm.claim_id
            ]
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
