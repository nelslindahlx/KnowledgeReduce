"""In-memory GraphStore backend backed by NetworkX MultiDiGraph."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Literal

import networkx as nx
import numpy as np
from numpy.typing import NDArray

from knowledgereduce.models import (
    Claim,
    ConflictRecord,
    Entity,
    KnowledgeLayer,
    LayerData,
    Relation,
    ReliabilityRating,
    StorageError,
)
from knowledgereduce.storage.base import (
    CLAIM_SORT_FIELDS,
    ClaimSummary,
    filter_matching_conflicts,
    layer_data_to_networkx,
    normalize_query_datetime,
    rank_claim_summaries,
    sort_claims_in_memory,
    summarize_claim,
    tokenize_search_query,
)


def _clone_layer_data(layer_data: LayerData) -> LayerData:
    return LayerData.model_validate(layer_data.model_dump())


class MemoryGraphStore:
    """Thread-safe-by-isolation in-memory store returning defensive copies."""

    def __init__(self) -> None:
        self._layers: dict[str, LayerData] = {}
        self._claim_embeddings: dict[str, tuple[str, list[str], NDArray[np.float32]]] = {}

    def save_layer(self, layer_data: LayerData, *, overwrite: bool = False) -> KnowledgeLayer:
        layer_id = layer_data.layer.layer_id
        if layer_id in self._layers and not overwrite:
            raise StorageError(f"Layer {layer_id!r} already exists (pass overwrite=True).")
        cloned = _clone_layer_data(layer_data)
        self._layers[layer_id] = cloned
        self._claim_embeddings.pop(layer_id, None)
        return KnowledgeLayer.model_validate(cloned.layer.model_dump())

    def load_layer(self, layer_id: str) -> LayerData:
        if layer_id not in self._layers:
            raise StorageError(f"Layer {layer_id!r} not found.")
        return _clone_layer_data(self._layers[layer_id])

    def layer_exists(self, layer_id: str) -> bool:
        return layer_id in self._layers

    def get_layer_manifest(self, layer_id: str) -> KnowledgeLayer:
        if layer_id not in self._layers:
            raise StorageError(f"Layer {layer_id!r} not found.")
        return KnowledgeLayer.model_validate(self._layers[layer_id].layer.model_dump())

    def list_source_hashes(self, layer_id: str) -> tuple[dict[str, str], dict[str, str]]:
        if layer_id not in self._layers:
            raise StorageError(f"Layer {layer_id!r} not found.")
        data = self._layers[layer_id]
        known_by_uri = {
            src.uri: src.content_sha256 for src in data.sources if src.uri and src.content_sha256
        }
        known_by_source_id = {
            src.source_id: src.content_sha256
            for src in data.sources
            if src.source_id and src.content_sha256
        }
        return known_by_uri, known_by_source_id

    def list_layers(self) -> list[KnowledgeLayer]:
        layers = [
            KnowledgeLayer.model_validate(data.layer.model_dump()) for data in self._layers.values()
        ]
        return sorted(layers, key=lambda item: item.created_at)

    def delete_layer(self, layer_id: str) -> None:
        if layer_id not in self._layers:
            raise StorageError(f"Layer {layer_id!r} not found.")
        del self._layers[layer_id]
        self._claim_embeddings.pop(layer_id, None)

    def list_entities(
        self,
        layer_id: str,
        *,
        entity_type: str | None = None,
        name_query: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[Entity]:
        data = self.load_layer(layer_id)
        results = data.entities
        if entity_type is not None:
            results = [e for e in results if e.entity_type == entity_type]
        if name_query is not None:
            q = name_query.lower()
            results = [
                e
                for e in results
                if q in e.canonical_name.lower() or any(q in a.lower() for a in e.aliases)
            ]
        return results[offset : offset + limit]

    def list_claims(
        self,
        layer_id: str,
        *,
        category: str | None = None,
        tag: str | None = None,
        tags_any: Sequence[str] | None = None,
        min_reliability: ReliabilityRating | None = None,
        needs_review: bool | None = None,
        text_query: str | None = None,
        recorded_after: datetime | None = None,
        recorded_before: datetime | None = None,
        published_after: datetime | None = None,
        published_before: datetime | None = None,
        subject_id: str | None = None,
        predicate: str | None = None,
        source_id: str | None = None,
        sort_by: Literal["quality_score", "reliability", "confidence", "updated_at"] | None = None,
        descending: bool = True,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[Claim]:
        if sort_by is not None and sort_by not in CLAIM_SORT_FIELDS:
            raise StorageError(f"Unsupported sort_by field {sort_by!r}.")
        data = self.load_layer(layer_id)
        if limit <= 0 or offset < 0:
            return []
        results = data.claims
        if category is not None:
            results = [c for c in results if c.category == category]
        if tag is not None:
            results = [c for c in results if tag in c.tags]
        if tags_any is not None:
            allowed_tags = set(tags_any)
            if not allowed_tags:
                return []
            results = [c for c in results if allowed_tags.intersection(c.tags)]
        if min_reliability is not None:
            results = [c for c in results if int(c.reliability) >= int(min_reliability)]
        if needs_review is not None:
            results = [c for c in results if c.needs_review is needs_review]
        if text_query is not None:
            q = text_query.lower()
            results = [
                c for c in results if q in c.statement.lower() or q in c.contextual_notes.lower()
            ]
        if recorded_after is not None:
            rec_after = normalize_query_datetime(recorded_after)
            results = [c for c in results if normalize_query_datetime(c.recorded_at) >= rec_after]
        if recorded_before is not None:
            rec_before = normalize_query_datetime(recorded_before)
            results = [c for c in results if normalize_query_datetime(c.recorded_at) <= rec_before]
        if published_after is not None:
            pub_after = normalize_query_datetime(published_after)
            results = [
                c
                for c in results
                if c.published_at is not None
                and normalize_query_datetime(c.published_at) >= pub_after
            ]
        if published_before is not None:
            pub_before = normalize_query_datetime(published_before)
            results = [
                c
                for c in results
                if c.published_at is not None
                and normalize_query_datetime(c.published_at) <= pub_before
            ]
        if subject_id is not None:
            results = [c for c in results if c.subject_id == subject_id]
        if predicate is not None:
            results = [c for c in results if c.predicate == predicate]
        if source_id is not None:
            results = [c for c in results if c.source_id == source_id]

        results = sort_claims_in_memory(results, sort_by=sort_by, descending=descending)
        return results[offset : offset + limit]

    def list_relations(
        self,
        layer_id: str,
        *,
        source_id: str | None = None,
        target_id: str | None = None,
        relation_type: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[Relation]:
        data = self.load_layer(layer_id)
        results = data.relations
        if source_id is not None:
            results = [r for r in results if r.source_id == source_id]
        if target_id is not None:
            results = [r for r in results if r.target_id == target_id]
        if relation_type is not None:
            results = [r for r in results if r.relation_type == relation_type]
        return results[offset : offset + limit]

    def list_conflicts(
        self,
        layer_id: str,
        *,
        needs_review: bool | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[ConflictRecord]:
        data = self.load_layer(layer_id)
        results = data.conflicts
        if needs_review is not None:
            results = [c for c in results if c.needs_review is needs_review]
        return results[offset : offset + limit]

    def to_networkx(self, layer_id: str) -> nx.MultiDiGraph:
        return layer_data_to_networkx(self.load_layer(layer_id))

    def list_claim_texts(self, layer_id: str) -> list[tuple[str, str]]:
        data = self.load_layer(layer_id)
        return [(c.claim_id, c.statement) for c in data.claims]

    def save_claim_embeddings(
        self,
        layer_id: str,
        claim_ids: Sequence[str],
        vectors: NDArray[np.float32],
        *,
        model_id: str,
    ) -> None:
        if layer_id not in self._layers:
            raise StorageError(f"Layer {layer_id!r} not found.")
        arr = np.asarray(vectors, dtype=np.float32)
        if len(claim_ids) > 0 and (arr.ndim != 2 or arr.shape[0] != len(claim_ids)):
            raise StorageError(
                f"Embedding count mismatch: got {len(claim_ids)} claim_ids vs shape {arr.shape}."
            )
        self._claim_embeddings[layer_id] = (model_id, list(claim_ids), arr.copy())

    def load_claim_embeddings(
        self,
        layer_id: str,
        *,
        model_id: str,
    ) -> tuple[list[str], NDArray[np.float32]] | None:
        if layer_id not in self._layers:
            raise StorageError(f"Layer {layer_id!r} not found.")
        entry = self._claim_embeddings.get(layer_id)
        if entry is None or entry[0] != model_id:
            return None
        return list(entry[1]), entry[2].copy()

    def search_claims_lexical(
        self,
        layer_id: str,
        query: str,
        *,
        min_reliability: ReliabilityRating = ReliabilityRating.UNKNOWN,
        limit: int = 200,
    ) -> list[Claim]:
        data = self.load_layer(layer_id)
        if limit <= 0:
            return []
        tokens = tokenize_search_query(query)
        candidates = [c for c in data.claims if int(c.reliability) >= int(min_reliability)]
        if tokens:
            scored = sorted(
                candidates,
                key=lambda c: (
                    -sum(1 for tok in tokens if tok in c.statement.lower()),
                    -c.quality_score,
                    c.claim_id,
                ),
            )
        else:
            scored = sorted(candidates, key=lambda c: (-c.quality_score, c.claim_id))
        return scored[:limit]

    def get_claims_by_ids(self, layer_id: str, claim_ids: Sequence[str]) -> list[Claim]:
        data = self.load_layer(layer_id)
        if not claim_ids:
            return []
        by_id = {c.claim_id: c for c in data.claims}
        return [by_id[cid] for cid in dict.fromkeys(claim_ids) if cid in by_id]

    def search_claim_summaries_lexical(
        self,
        layer_id: str,
        query: str,
        *,
        min_reliability: ReliabilityRating = ReliabilityRating.UNKNOWN,
        limit: int = 200,
    ) -> list[ClaimSummary]:
        """Return lightweight claim summaries ranked identically to ``search_claims_lexical``."""
        if layer_id not in self._layers:
            raise StorageError(f"Layer {layer_id!r} not found.")
        data = self._layers[layer_id]
        if limit <= 0:
            return []
        summaries = [summarize_claim(c) for c in data.claims]
        lower_stmts = [c.statement.lower() for c in data.claims]
        return rank_claim_summaries(
            summaries,
            lower_stmts,
            query,
            min_reliability=min_reliability,
            limit=limit,
        )

    def get_claim_summaries_by_ids(
        self, layer_id: str, claim_ids: Sequence[str]
    ) -> list[ClaimSummary]:
        """Fetch lightweight ``ClaimSummary`` projections matching *claim_ids*."""
        if layer_id not in self._layers:
            raise StorageError(f"Layer {layer_id!r} not found.")
        if not claim_ids:
            return []
        by_id = {c.claim_id: c for c in self._layers[layer_id].claims}
        return [summarize_claim(by_id[cid]) for cid in dict.fromkeys(claim_ids) if cid in by_id]

    def get_k_hop_subgraph(
        self,
        layer_id: str,
        seed_node_ids: Sequence[str],
        *,
        hops: int = 1,
    ) -> tuple[nx.MultiDiGraph, list[Entity], list[ConflictRecord]]:
        data = self.load_layer(layer_id)
        if not seed_node_ids:
            return nx.MultiDiGraph(), [], []

        visited: set[str] = set(seed_node_ids)
        frontier: set[str] = set(seed_node_ids)
        for _ in range(max(0, hops)):
            if not frontier:
                break
            next_frontier: set[str] = set()
            for rel in data.relations:
                if rel.source_id in frontier or rel.target_id in frontier:
                    next_frontier.add(rel.source_id)
                    next_frontier.add(rel.target_id)
            frontier = next_frontier - visited
            visited.update(frontier)

        sub_entities = [e for e in data.entities if e.entity_id in visited]
        sub_claims = [c for c in data.claims if c.claim_id in visited]
        surviving = {e.entity_id for e in sub_entities} | {c.claim_id for c in sub_claims}
        sub_relations = (
            [r for r in data.relations if r.source_id in surviving and r.target_id in surviving]
            if hops > 0
            else []
        )
        sub_graph = layer_data_to_networkx(
            LayerData(
                layer=data.layer,
                entities=sub_entities,
                claims=sub_claims,
                relations=sub_relations,
            )
        )
        sub_claim_ids = {c.claim_id for c in sub_claims}
        touched_conflicts = filter_matching_conflicts(data.conflicts, sub_claim_ids)
        return sub_graph, sub_entities, touched_conflicts
