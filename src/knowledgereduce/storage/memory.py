"""In-memory GraphStore backend backed by NetworkX MultiDiGraph."""

from __future__ import annotations

import networkx as nx

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
from knowledgereduce.storage.base import layer_data_to_networkx


def _clone_layer_data(layer_data: LayerData) -> LayerData:
    return LayerData.model_validate(layer_data.model_dump())


class MemoryGraphStore:
    """Thread-safe-by-isolation in-memory store returning defensive copies."""

    def __init__(self) -> None:
        self._layers: dict[str, LayerData] = {}

    def save_layer(self, layer_data: LayerData, *, overwrite: bool = False) -> KnowledgeLayer:
        layer_id = layer_data.layer.layer_id
        if layer_id in self._layers and not overwrite:
            raise StorageError(f"Layer {layer_id!r} already exists (pass overwrite=True).")
        cloned = _clone_layer_data(layer_data)
        self._layers[layer_id] = cloned
        return KnowledgeLayer.model_validate(cloned.layer.model_dump())

    def load_layer(self, layer_id: str) -> LayerData:
        if layer_id not in self._layers:
            raise StorageError(f"Layer {layer_id!r} not found.")
        return _clone_layer_data(self._layers[layer_id])

    def layer_exists(self, layer_id: str) -> bool:
        return layer_id in self._layers

    def list_layers(self) -> list[KnowledgeLayer]:
        layers = [
            KnowledgeLayer.model_validate(data.layer.model_dump()) for data in self._layers.values()
        ]
        return sorted(layers, key=lambda item: item.created_at)

    def delete_layer(self, layer_id: str) -> None:
        if layer_id not in self._layers:
            raise StorageError(f"Layer {layer_id!r} not found.")
        del self._layers[layer_id]

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
        min_reliability: ReliabilityRating | None = None,
        needs_review: bool | None = None,
        text_query: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[Claim]:
        data = self.load_layer(layer_id)
        results = data.claims
        if category is not None:
            results = [c for c in results if c.category == category]
        if tag is not None:
            results = [c for c in results if tag in c.tags]
        if min_reliability is not None:
            results = [c for c in results if int(c.reliability) >= int(min_reliability)]
        if needs_review is not None:
            results = [c for c in results if c.needs_review is needs_review]
        if text_query is not None:
            q = text_query.lower()
            results = [
                c for c in results if q in c.statement.lower() or q in c.contextual_notes.lower()
            ]
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
