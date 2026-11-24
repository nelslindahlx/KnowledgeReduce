"""Hypothesis property-based tests for core KnowledgeReduce invariants."""

from __future__ import annotations

from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from knowledgereduce.export import (
    export_layer_json,
    export_layer_sharded,
    import_layer_json,
    import_layer_sharded,
)
from knowledgereduce.models import (
    Claim,
    Entity,
    Evidence,
    KnowledgeLayer,
    LayerData,
    MergeMode,
    Relation,
    ReliabilityRating,
)
from knowledgereduce.stack import StackManager
from knowledgereduce.storage import DuckDBParquetStore, MemoryGraphStore

_safe_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "Zs"), min_codepoint=32, max_codepoint=126
    ),
    min_size=1,
    max_size=40,
).filter(lambda s: bool(s.strip()))

_safe_id = st.from_regex(r"[a-z][a-z0-9_-]{1,12}", fullmatch=True)


@st.composite
def _layer_strategy(draw: st.DrawFn, layer_id: str = "prop-layer") -> LayerData:
    n_entities = draw(st.integers(min_value=1, max_value=6))
    n_claims = draw(st.integers(min_value=1, max_value=6))

    entities = [
        Entity(
            entity_id=f"e{i}",
            canonical_name=draw(_safe_text),
            entity_type=draw(st.sampled_from(["PERSON", "ORG", "CONCEPT", "GPE"])),
            aliases=draw(st.lists(_safe_text, max_size=3)),
        )
        for i in range(n_entities)
    ]
    claims = [
        Claim(
            claim_id=f"c{i}",
            statement=draw(_safe_text),
            tags=draw(st.lists(_safe_id, max_size=4)),
            reliability=draw(st.sampled_from(list(ReliabilityRating))),
            usage_count=draw(st.integers(min_value=0, max_value=25)),
            confidence=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
            evidence=[Evidence(source_id="s1", excerpt="excerpt")],
        )
        for i in range(n_claims)
    ]
    relations = [
        Relation(
            relation_id=f"r{i}",
            source_id=f"c{i % n_claims}",
            target_id=f"e{i % n_entities}",
            relation_type="MENTIONS",
            confidence=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
        )
        for i in range(max(n_entities, n_claims))
    ]
    return LayerData(
        layer=KnowledgeLayer(layer_id=layer_id, name="Property Layer"),
        entities=entities,
        claims=claims,
        relations=relations,
    )


@given(layer_data=_layer_strategy())
@settings(max_examples=25, deadline=None)
def test_quality_score_always_bounded_and_json_roundtrip(layer_data: LayerData) -> None:
    for claim in layer_data.claims:
        assert 0.0 <= claim.quality_score <= 100.0

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        json_file = export_layer_json(layer_data, tmp_path / "layer.json")
        restored_json = import_layer_json(json_file)
        assert restored_json.model_dump(mode="json") == layer_data.model_dump(mode="json")

        shard_dir = export_layer_sharded(layer_data, tmp_path / "shards", shard_size=2)
        restored_sharded = import_layer_sharded(shard_dir)
        assert restored_sharded.model_dump(mode="json") == layer_data.model_dump(mode="json")


@given(layer_data=_layer_strategy())
@settings(max_examples=15, deadline=None)
def test_duckdb_store_roundtrip_invariant(layer_data: LayerData) -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        store = DuckDBParquetStore(Path(tmp))
        store.save_layer(layer_data)
        restored = store.load_layer(layer_data.layer.layer_id)
        assert restored.model_dump(mode="json") == layer_data.model_dump(mode="json")


@given(left=_layer_strategy("left-layer"), right=_layer_strategy("right-layer"))
@settings(max_examples=20, deadline=None)
def test_stack_algebra_never_leaves_dangling_edges_or_mutates_inputs(
    left: LayerData,
    right: LayerData,
) -> None:
    store = MemoryGraphStore()
    store.save_layer(left)
    store.save_layer(right)
    left_before = store.load_layer("left-layer").model_dump(mode="json")
    right_before = store.load_layer("right-layer").model_dump(mode="json")

    mgr = StackManager(store)
    for mode in (MergeMode.UNION, MergeMode.INTERSECTION, MergeMode.DIFFERENCE):
        merged = mgr.merge_layers(
            ["left-layer", "right-layer"],
            target_layer_id=f"merged-{mode.value}",
            mode=mode,
        )
        node_ids = {e.entity_id for e in merged.entities} | {c.claim_id for c in merged.claims}
        for rel in merged.relations:
            assert rel.source_id in node_ids
            assert rel.target_id in node_ids

    assert store.load_layer("left-layer").model_dump(mode="json") == left_before
    assert store.load_layer("right-layer").model_dump(mode="json") == right_before
