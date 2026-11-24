"""Unit tests for StackManager layer algebra, conflict handling, and lineage DAG."""

from __future__ import annotations

import pytest

from knowledgereduce.models import (
    Claim,
    ConflictStrategy,
    Entity,
    Evidence,
    KnowledgeLayer,
    LayerData,
    LayerTier,
    MergeMode,
    Relation,
    ReliabilityRating,
    SourceDocument,
    StackError,
)
from knowledgereduce.stack import StackManager
from knowledgereduce.storage import MemoryGraphStore


def _build_base_and_overlay(store: MemoryGraphStore) -> tuple[LayerData, LayerData]:
    base = LayerData(
        layer=KnowledgeLayer(layer_id="base", name="Base", tier=LayerTier.REDUCED),
        entities=[
            Entity(
                entity_id="e1",
                canonical_name="Civic Honors",
                entity_type="ORG",
                evidence=[Evidence(source_id="s1", excerpt="Civic Honors")],
            ),
            Entity(entity_id="e2", canonical_name="University of Kansas", entity_type="ORG"),
        ],
        claims=[
            Claim(
                claim_id="c1",
                statement="Civic Honors was published in 2006.",
                tags=["civic"],
                reliability=ReliabilityRating.LIKELY_TRUE,
                source_id="s1",
            ),
            Claim(
                claim_id="c2",
                statement="Kansas is in the US.",
                tags=["geo"],
                reliability=ReliabilityRating.VERIFIED,
                source_id="s1",
            ),
        ],
        relations=[
            Relation(relation_id="r1", source_id="e1", target_id="e2", relation_type="LOCATED_AT"),
            Relation(relation_id="r2", source_id="c2", target_id="e2", relation_type="MENTIONS"),
        ],
    )
    overlay = LayerData(
        layer=KnowledgeLayer(layer_id="overlay", name="Overlay", tier=LayerTier.CURATED),
        entities=[
            Entity(
                entity_id="e1",
                canonical_name="Graduation with Civic Honors",
                entity_type="ORG",
                aliases=["Civic Honors"],
                evidence=[Evidence(source_id="s2", excerpt="Graduation with Civic Honors")],
            ),
            Entity(entity_id="e3", canonical_name="Nels Lindahl", entity_type="PERSON"),
        ],
        claims=[
            Claim(
                claim_id="c1",
                statement="Civic Honors was updated online in 2020.",
                tags=["update"],
                reliability=ReliabilityRating.VERIFIED,
                source_id="s2",
            )
        ],
        relations=[
            Relation(relation_id="r3", source_id="e3", target_id="e1", relation_type="AUTHORED")
        ],
    )
    store.save_layer(base)
    store.save_layer(overlay)
    return base, overlay


def test_stack_overlay_preserves_disputes_and_lineage() -> None:
    store = MemoryGraphStore()
    _build_base_and_overlay(store)
    mgr = StackManager(store)

    stacked = mgr.stack_overlay(
        "base",
        "overlay",
        target_layer_id="stacked-v1",
        conflict_strategy=ConflictStrategy.PRESERVE_DISPUTE,
    )
    assert stacked.layer.parent_layer_ids == ["base", "overlay"]
    assert stacked.layer.merge_mode == MergeMode.OVERLAY
    assert len(stacked.entities) == 3
    assert len(stacked.relations) == 3
    # Conflicting canonical_name & statement both logged as disputes
    assert len(stacked.conflicts) == 2
    assert all(cf.needs_review for cf in stacked.conflicts)

    e1 = next(e for e in stacked.entities if e.entity_id == "e1")
    assert e1.canonical_name == "Graduation with Civic Honors"
    assert "Civic Honors" in e1.aliases
    assert {ev.source_id for ev in e1.evidence} == {"s1", "s2"}

    # Base layer remained completely unmutated
    assert len(store.load_layer("base").entities) == 2
    assert mgr.get_ancestors("stacked-v1") == ["base", "overlay"]
    assert mgr.get_descendants("base") == ["stacked-v1"]


def test_merge_intersection_difference_and_diff() -> None:
    store = MemoryGraphStore()
    _build_base_and_overlay(store)
    mgr = StackManager(store)

    inter = mgr.merge_layers(
        ["base", "overlay"],
        target_layer_id="inter-1",
        mode=MergeMode.INTERSECTION,
    )
    assert [e.entity_id for e in inter.entities] == ["e1"]
    assert [c.claim_id for c in inter.claims] == ["c1"]
    assert inter.relations == []  # r1/r2/r3 don't exist in both layers

    diff_layer = mgr.merge_layers(
        ["base", "overlay"],
        target_layer_id="diff-1",
        mode=MergeMode.DIFFERENCE,
    )
    # e1 removed because present in overlay; r1 removed because e1 no longer survives!
    assert [e.entity_id for e in diff_layer.entities] == ["e2"]
    assert [c.claim_id for c in diff_layer.claims] == ["c2"]
    assert [r.relation_id for r in diff_layer.relations] == ["r2"]

    structural_diff = mgr.diff_layers("base", "overlay")
    assert structural_diff.added_entity_ids == ["e3"]
    assert structural_diff.removed_entity_ids == ["e2"]
    assert structural_diff.modified_entity_ids == ["e1"]
    assert structural_diff.modified_claim_ids == ["c1"]


def test_stack_errors_on_missing_or_single_layer() -> None:
    store = MemoryGraphStore()
    _build_base_and_overlay(store)
    mgr = StackManager(store)

    with pytest.raises(StackError):
        mgr.merge_layers([], target_layer_id="x")
    with pytest.raises(StackError):
        mgr.merge_layers(["base"], target_layer_id="x", mode=MergeMode.DIFFERENCE)
    with pytest.raises(StackError):
        mgr.merge_layers(["missing", "base"], target_layer_id="x")
    with pytest.raises(StackError):
        mgr.get_ancestors("missing")
    with pytest.raises(StackError, match="reconcile=True"):
        mgr.merge_layers(
            ["base", "overlay"],
            target_layer_id="bad-rec",
            mode=MergeMode.DIFFERENCE,
            reconcile=True,
        )


def test_stack_reconcile_merges_distinct_entity_ids_and_detects_conflicts() -> None:
    store = MemoryGraphStore()
    layer_a = LayerData(
        layer=KnowledgeLayer(layer_id="layer-a", name="Layer A", tier=LayerTier.REDUCED),
        sources=[SourceDocument(source_id="src_a", uri="https://a.example", trust_weight=0.95)],
        entities=[
            Entity(
                entity_id="ent_a_nels",
                canonical_name="Dr. Nels Lindahl",
                entity_type="PERSON",
                evidence=[Evidence(source_id="src_a", excerpt="Dr. Nels Lindahl")],
            ),
            Entity(
                entity_id="ent_a_ch",
                canonical_name="Civic Honors",
                entity_type="ORG",
                evidence=[Evidence(source_id="src_a", excerpt="Civic Honors")],
            ),
        ],
        claims=[
            Claim(
                claim_id="clm_a_1",
                statement="Civic Honors was published in 2006.",
                source_id="src_a",
                reliability=ReliabilityRating.VERIFIED,
                subject_id="ent_a_ch",
                predicate="PUBLISHED_IN",
                object_literal="2006",
                evidence=[Evidence(source_id="src_a", excerpt="published in 2006")],
            )
        ],
        relations=[
            Relation(
                relation_id="rel_a_1",
                source_id="clm_a_1",
                target_id="ent_a_nels",
                relation_type="MENTIONS",
            ),
            Relation(
                relation_id="rel_a_2",
                source_id="clm_a_1",
                target_id="ent_a_ch",
                relation_type="MENTIONS",
            ),
        ],
    )
    layer_b = LayerData(
        layer=KnowledgeLayer(layer_id="layer-b", name="Layer B", tier=LayerTier.REDUCED),
        sources=[SourceDocument(source_id="src_b", uri="https://b.example", trust_weight=0.45)],
        entities=[
            Entity(
                entity_id="ent_b_nels",
                canonical_name="Nels Lindahl",
                entity_type="PERSON",
                evidence=[Evidence(source_id="src_b", excerpt="Nels Lindahl")],
            ),
            Entity(
                entity_id="ent_b_ch",
                canonical_name="Civic Honors",
                entity_type="ORG",
                evidence=[Evidence(source_id="src_b", excerpt="Civic Honors")],
            ),
        ],
        claims=[
            Claim(
                claim_id="clm_b_1",
                statement="Civic Honors was published in 2020.",
                source_id="src_b",
                reliability=ReliabilityRating.POSSIBLY_TRUE,
                subject_id="ent_b_ch",
                predicate="PUBLISHED_IN",
                object_literal="2020",
                evidence=[Evidence(source_id="src_b", excerpt="published in 2020")],
            )
        ],
        relations=[
            Relation(
                relation_id="rel_b_1",
                source_id="clm_b_1",
                target_id="ent_b_nels",
                relation_type="MENTIONS",
            ),
            Relation(
                relation_id="rel_b_2",
                source_id="clm_b_1",
                target_id="ent_b_ch",
                relation_type="MENTIONS",
            ),
        ],
    )
    store.save_layer(layer_a)
    store.save_layer(layer_b)
    mgr = StackManager(store)

    unreconciled = mgr.merge_layers(
        ["layer-a", "layer-b"],
        target_layer_id="union-raw",
        mode=MergeMode.UNION,
        reconcile=False,
    )
    assert len(unreconciled.entities) == 4
    assert unreconciled.conflicts == []

    reconciled = mgr.merge_layers(
        ["layer-a", "layer-b"],
        target_layer_id="union-reconciled",
        mode=MergeMode.UNION,
        reconcile=True,
    )
    assert len(reconciled.entities) == 2
    assert len(reconciled.conflicts) == 1
    assert reconciled.conflicts[0].winning_value == "2006"
    assert any(r.relation_type == "CONTRADICTS" for r in reconciled.relations)
    valid_eids = {e.entity_id for e in reconciled.entities}
    assert all(c.subject_id in valid_eids for c in reconciled.claims)
