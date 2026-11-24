"""GraphStore protocol and shared NetworkX graph conversion helpers."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

import networkx as nx
import numpy as np
from numpy.typing import NDArray

from knowledgereduce.models import (
    Claim,
    ConflictRecord,
    Entity,
    KnowledgeLayer,
    LayerData,
    LayerDiff,
    Relation,
    ReliabilityRating,
)

_SEARCH_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


def tokenize_search_query(query: str, *, max_tokens: int = 12) -> list[str]:
    """Extract deduplicated lowercase alphanumeric search tokens from *query*."""
    seen: set[str] = set()
    tokens: list[str] = []
    for tok in _SEARCH_TOKEN_RE.findall(query.lower()):
        if tok not in seen:
            seen.add(tok)
            tokens.append(tok)
            if len(tokens) >= max_tokens:
                break
    return tokens


def filter_matching_conflicts(
    conflicts: Sequence[ConflictRecord],
    claim_ids: set[str],
) -> list[ConflictRecord]:
    """Return conflicts referencing any claim ID in *claim_ids*."""
    if not claim_ids:
        return []
    return [
        cf
        for cf in conflicts
        if cf.target_key in claim_ids
        or any(
            str(cid) in claim_ids for cand in cf.candidates for cid in (cand.get("claim_ids") or [])
        )
    ]


@runtime_checkable
class GraphStore(Protocol):
    """Unified interface satisfied by all KnowledgeReduce storage backends."""

    def save_layer(self, layer_data: LayerData, *, overwrite: bool = False) -> KnowledgeLayer:
        """Persist a knowledge layer."""
        ...

    def load_layer(self, layer_id: str) -> LayerData:
        """Load the complete payload of a persisted layer."""
        ...

    def layer_exists(self, layer_id: str) -> bool:
        """Return whether *layer_id* exists in this store."""
        ...

    def list_layers(self) -> list[KnowledgeLayer]:
        """Return metadata for all layers stored in this backend."""
        ...

    def delete_layer(self, layer_id: str) -> None:
        """Delete a layer by ID."""
        ...

    def list_entities(
        self,
        layer_id: str,
        *,
        entity_type: str | None = None,
        name_query: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[Entity]:
        """Query entities in *layer_id* with optional type and substring filters."""
        ...

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
        """Query claims in *layer_id* with structured filters."""
        ...

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
        """Query relations in *layer_id*."""
        ...

    def list_conflicts(
        self,
        layer_id: str,
        *,
        needs_review: bool | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[ConflictRecord]:
        """Query conflict records in *layer_id*."""
        ...

    def to_networkx(self, layer_id: str) -> nx.MultiDiGraph:
        """Materialize *layer_id* as a fresh NetworkX MultiDiGraph."""
        ...

    def list_claim_texts(self, layer_id: str) -> list[tuple[str, str]]:
        """Return ``(claim_id, statement)`` pairs for *layer_id* without full object parsing."""
        ...

    def save_claim_embeddings(
        self,
        layer_id: str,
        claim_ids: Sequence[str],
        vectors: NDArray[np.float32],
        *,
        model_id: str,
    ) -> None:
        """Persist precomputed claim embeddings keyed by *model_id* for *layer_id*."""
        ...

    def load_claim_embeddings(
        self,
        layer_id: str,
        *,
        model_id: str,
    ) -> tuple[list[str], NDArray[np.float32]] | None:
        """Load persisted claim embeddings matching *model_id*, or ``None`` on cache miss."""
        ...

    def search_claims_lexical(
        self,
        layer_id: str,
        query: str,
        *,
        min_reliability: ReliabilityRating = ReliabilityRating.UNKNOWN,
        limit: int = 200,
    ) -> list[Claim]:
        """Return top candidate claims ranked by lexical token matches and quality."""
        ...

    def get_claims_by_ids(self, layer_id: str, claim_ids: Sequence[str]) -> list[Claim]:
        """Fetch specific claims matching *claim_ids*."""
        ...

    def get_k_hop_subgraph(
        self,
        layer_id: str,
        seed_node_ids: Sequence[str],
        *,
        hops: int = 1,
    ) -> tuple[nx.MultiDiGraph, list[Entity], list[ConflictRecord]]:
        """Extract bounded k-hop induced subgraph, touched entities, and touched conflicts."""
        ...


def layer_data_to_networkx(layer_data: LayerData) -> nx.MultiDiGraph:
    """Convert a ``LayerData`` payload into a fresh, isolated ``nx.MultiDiGraph``."""
    graph = nx.MultiDiGraph(
        layer_id=layer_data.layer.layer_id,
        name=layer_data.layer.name,
        version=layer_data.layer.version,
        tier=str(layer_data.layer.tier),
    )

    for entity in layer_data.entities:
        graph.add_node(
            entity.entity_id,
            node_kind="entity",
            label=entity.canonical_name,
            entity_type=entity.entity_type,
            aliases=list(entity.aliases),
            attributes=dict(entity.attributes),
            external_ids=dict(entity.external_ids),
            evidence=[ev.model_dump(mode="json") for ev in entity.evidence],
        )

    for claim in layer_data.claims:
        graph.add_node(
            claim.claim_id,
            node_kind="claim",
            label=claim.statement,
            statement=claim.statement,
            category=claim.category,
            tags=list(claim.tags),
            contextual_notes=claim.contextual_notes,
            recorded_at=claim.recorded_at.isoformat(),
            updated_at=claim.updated_at.isoformat(),
            published_at=claim.published_at.isoformat() if claim.published_at else None,
            reliability=int(claim.reliability),
            reliability_name=claim.reliability.name,
            quality_score=claim.quality_score,
            confidence=claim.confidence,
            source_id=claim.source_id,
            source_title=claim.source_title,
            author_creator=claim.author_creator,
            url_reference=claim.url_reference,
            access_level=claim.access_level,
            usage_count=claim.usage_count,
            related_facts=list(claim.related_facts),
            subject_id=claim.subject_id,
            predicate=claim.predicate,
            object_id=claim.object_id,
            object_literal=claim.object_literal,
            merged_from=list(claim.merged_from),
            needs_review=claim.needs_review,
            evidence=[ev.model_dump(mode="json") for ev in claim.evidence],
        )

    for rel in layer_data.relations:
        graph.add_edge(
            rel.source_id,
            rel.target_id,
            key=rel.relation_id,
            relation_id=rel.relation_id,
            relation_type=rel.relation_type,
            confidence=rel.confidence,
            weight=rel.weight,
            attributes=dict(rel.attributes),
            evidence=[ev.model_dump(mode="json") for ev in rel.evidence],
        )

    return graph


def compute_layer_diff(left: LayerData, right: LayerData) -> LayerDiff:
    """Compute a structural diff from *left* to *right*."""
    left_entities = {e.entity_id: e for e in left.entities}
    right_entities = {e.entity_id: e for e in right.entities}

    added_entities = sorted(right_entities.keys() - left_entities.keys())
    removed_entities = sorted(left_entities.keys() - right_entities.keys())
    modified_entities = sorted(
        eid
        for eid in (left_entities.keys() & right_entities.keys())
        if left_entities[eid].model_dump(mode="json") != right_entities[eid].model_dump(mode="json")
    )

    left_claims = {c.claim_id: c for c in left.claims}
    right_claims = {c.claim_id: c for c in right.claims}

    added_claims = sorted(right_claims.keys() - left_claims.keys())
    removed_claims = sorted(left_claims.keys() - right_claims.keys())
    modified_claims = sorted(
        cid
        for cid in (left_claims.keys() & right_claims.keys())
        if left_claims[cid].model_dump(mode="json") != right_claims[cid].model_dump(mode="json")
    )

    left_rels = {r.relation_id for r in left.relations}
    right_rels = {r.relation_id for r in right.relations}

    left_conflicts = {c.conflict_id: c for c in left.conflicts}
    right_conflicts = {c.conflict_id: c for c in right.conflicts}
    added_conflicts = sorted(right_conflicts.keys() - left_conflicts.keys())
    resolved_conflicts = sorted(
        cid
        for cid, rc in right_conflicts.items()
        if cid in left_conflicts and left_conflicts[cid].needs_review and not rc.needs_review
    )

    return LayerDiff(
        left_layer_id=left.layer.layer_id,
        right_layer_id=right.layer.layer_id,
        added_entity_ids=added_entities,
        removed_entity_ids=removed_entities,
        modified_entity_ids=modified_entities,
        added_claim_ids=added_claims,
        removed_claim_ids=removed_claims,
        modified_claim_ids=modified_claims,
        added_relation_ids=sorted(right_rels - left_rels),
        removed_relation_ids=sorted(left_rels - right_rels),
        added_conflict_ids=added_conflicts,
        resolved_conflict_ids=resolved_conflicts,
    )
