"""Unit tests for MemoryGraphStore and DuckDBParquetStore."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from knowledgereduce.models import (
    Claim,
    ConflictRecord,
    ConflictStrategy,
    Entity,
    Evidence,
    KnowledgeLayer,
    LayerData,
    LayerTier,
    Relation,
    ReliabilityRating,
    SourceDocument,
    SourceType,
    StorageError,
)
from knowledgereduce.storage import DuckDBParquetStore, GraphStore, MemoryGraphStore


def _make_sample_layer(layer_id: str = "layer-1") -> LayerData:
    src = SourceDocument(
        source_id="src-civic",
        uri="https://civichonors.com/",
        source_type=SourceType.WEB,
        title="Civic Honors",
        content="Dr. Nels Lindahl founded Civic Honors in 2006.",
        trust_weight=0.9,
    )
    e1 = Entity(
        entity_id="ent-nels",
        canonical_name="Nels Lindahl",
        entity_type="PERSON",
        aliases=["Dr. Nels Lindahl"],
        evidence=[Evidence(source_id="src-civic", excerpt="Dr. Nels Lindahl")],
    )
    e2 = Entity(
        entity_id="ent-ch",
        canonical_name="Civic Honors",
        entity_type="ORG",
        evidence=[Evidence(source_id="src-civic", excerpt="Civic Honors")],
    )
    c1 = Claim(
        claim_id="clm-1",
        statement="Civic Honors was published in 2006.",
        category="Publication",
        tags=["earth", "civic"],
        reliability=ReliabilityRating.VERIFIED,
        source_id="src-civic",
        subject_id="ent-ch",
        predicate="PUBLISHED_IN",
        object_literal="2006",
        evidence=[Evidence(source_id="src-civic", excerpt="published in 2006")],
    )
    c2 = Claim(
        claim_id="clm-2",
        statement="The moon orbits Earth.",
        category="Science",
        tags=["art"],
        reliability=ReliabilityRating.POSSIBLY_TRUE,
        source_id="src-civic",
        needs_review=True,
    )
    r1 = Relation(
        relation_id="rel-1",
        source_id="ent-nels",
        target_id="ent-ch",
        relation_type="AUTHORED",
        confidence=0.95,
        evidence=[Evidence(source_id="src-civic", excerpt="Dr. Nels Lindahl ... Civic Honors")],
    )
    r2 = Relation(
        relation_id="rel-2",
        source_id="ent-nels",
        target_id="ent-ch",
        relation_type="FOUNDED",
        confidence=0.9,
    )
    cf = ConflictRecord(
        conflict_id="cf-1",
        target_type="claim",
        target_key="clm-2",
        candidates=[{"val": "a"}, {"val": "b"}],
        resolution_strategy=ConflictStrategy.PRESERVE_DISPUTE,
        winning_value="a",
        needs_review=True,
    )
    layer = KnowledgeLayer(
        layer_id=layer_id,
        name="Civic Honors Sample",
        tier=LayerTier.REDUCED,
        stats={"entities": 2, "claims": 2, "relations": 2},
    )
    return LayerData(
        layer=layer,
        sources=[src],
        entities=[e1, e2],
        claims=[c1, c2],
        relations=[r1, r2],
        conflicts=[cf],
    )


@pytest.fixture(params=["memory", "duckdb"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> GraphStore:
    if request.param == "memory":
        return MemoryGraphStore()
    return DuckDBParquetStore(tmp_path / "db")


def test_store_roundtrip_and_overwrite_rules(store: GraphStore) -> None:
    sample = _make_sample_layer("civic-v1")
    saved = store.save_layer(sample)
    assert saved.layer_id == "civic-v1"
    assert store.layer_exists("civic-v1")

    with pytest.raises(StorageError, match="already exists"):
        store.save_layer(sample)

    loaded = store.load_layer("civic-v1")
    assert loaded.layer.layer_id == "civic-v1"
    assert len(loaded.sources) == 1
    assert len(loaded.entities) == 2
    assert len(loaded.claims) == 2
    assert len(loaded.relations) == 2
    assert len(loaded.conflicts) == 1
    assert loaded.claims[0].quality_score == sample.claims[0].quality_score

    # Overwrite succeeds cleanly
    store.save_layer(sample, overwrite=True)
    assert [layer.layer_id for layer in store.list_layers()] == ["civic-v1"]

    store.delete_layer("civic-v1")
    assert not store.layer_exists("civic-v1")


def test_store_empty_layer_preserves_parquet_schemas(store: GraphStore) -> None:
    empty = LayerData(layer=KnowledgeLayer(layer_id="empty-layer", name="Empty"))
    store.save_layer(empty)
    loaded = store.load_layer("empty-layer")
    assert loaded.sources == []
    assert loaded.entities == []
    assert loaded.claims == []
    assert loaded.relations == []
    assert loaded.conflicts == []


def test_store_queries_and_exact_tag_matching(store: GraphStore) -> None:
    store.save_layer(_make_sample_layer("q-layer"))

    people = store.list_entities("q-layer", entity_type="PERSON", name_query="lindahl")
    assert [e.entity_id for e in people] == ["ent-nels"]

    # Exact tag check: "art" must match clm-2 (tag="art") and NOT clm-1 (tag="earth")
    art_claims = store.list_claims("q-layer", tag="art")
    assert [c.claim_id for c in art_claims] == ["clm-2"]

    verified = store.list_claims("q-layer", min_reliability=ReliabilityRating.VERIFIED)
    assert [c.claim_id for c in verified] == ["clm-1"]

    reviewed = store.list_claims("q-layer", needs_review=True)
    assert [c.claim_id for c in reviewed] == ["clm-2"]

    authored = store.list_relations("q-layer", source_id="ent-nels", relation_type="AUTHORED")
    assert len(authored) == 1

    conflicts = store.list_conflicts("q-layer", needs_review=True)
    assert [cf.conflict_id for cf in conflicts] == ["cf-1"]


def test_store_to_networkx_preserves_parallel_edges(store: GraphStore) -> None:
    store.save_layer(_make_sample_layer("nx-layer"))
    graph = store.to_networkx("nx-layer")
    assert graph.number_of_nodes() == 4
    assert graph.number_of_edges() == 2
    assert graph.has_edge("ent-nels", "ent-ch", key="rel-1")
    assert graph.has_edge("ent-nels", "ent-ch", key="rel-2")

    # Mutating returned graph must not mutate stored layer
    graph.remove_node("ent-nels")
    assert len(store.load_layer("nx-layer").entities) == 2


def test_duckdb_store_writes_manifest_and_rejects_bad_layer_id(tmp_path: Path) -> None:
    store = DuckDBParquetStore(tmp_path)
    store.save_layer(_make_sample_layer("manifest-layer"))
    manifest = json.loads(
        (tmp_path / "layers" / "manifest-layer" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["schema_version"] == "1.0"
    assert manifest["files"]["claims.parquet"]["rows"] == 2
    assert len(manifest["files"]["claims.parquet"]["sha256"]) == 64

    with pytest.raises(StorageError):
        store.load_layer("../escape")


def test_store_embeddings_lexical_ids_and_k_hop_subgraph(store: GraphStore) -> None:
    sample = _make_sample_layer("vec-layer")
    store.save_layer(sample)

    texts = store.list_claim_texts("vec-layer")
    assert dict(texts) == {
        "clm-1": "Civic Honors was published in 2006.",
        "clm-2": "The moon orbits Earth.",
    }
    assert store.load_claim_embeddings("vec-layer", model_id="h1") is None

    vecs = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]], dtype=np.float32)
    store.save_claim_embeddings("vec-layer", ["clm-1", "clm-2"], vecs, model_id="h1")
    loaded = store.load_claim_embeddings("vec-layer", model_id="h1")
    assert loaded is not None
    assert loaded[0] == ["clm-1", "clm-2"]
    assert np.allclose(loaded[1], vecs)
    assert store.load_claim_embeddings("vec-layer", model_id="different-model") is None

    with pytest.raises(StorageError, match="mismatch"):
        store.save_claim_embeddings("vec-layer", ["clm-1"], vecs, model_id="h1")

    lex_hits = store.search_claims_lexical("vec-layer", "published 2006", limit=10)
    assert [c.claim_id for c in lex_hits] == ["clm-1", "clm-2"]

    verified_hits = store.search_claims_lexical(
        "vec-layer", "moon", min_reliability=ReliabilityRating.VERIFIED
    )
    assert [c.claim_id for c in verified_hits] == ["clm-1"]

    by_ids = store.get_claims_by_ids("vec-layer", ["clm-2", "missing", "clm-1"])
    assert [c.claim_id for c in by_ids] == ["clm-2", "clm-1"]
    assert store.get_claims_by_ids("vec-layer", []) == []

    sub_g, sub_ents, _ = store.get_k_hop_subgraph("vec-layer", ["ent-nels"], hops=1)
    assert {e.entity_id for e in sub_ents} == {"ent-nels", "ent-ch"}
    assert sub_g.number_of_edges() == 2

    zero_g, zero_ents, zero_cfs = store.get_k_hop_subgraph("vec-layer", ["clm-2"], hops=0)
    assert zero_g.number_of_edges() == 0
    assert zero_ents == []
    assert [cf.conflict_id for cf in zero_cfs] == ["cf-1"]

    empty_g, _, _ = store.get_k_hop_subgraph("vec-layer", [], hops=1)
    assert empty_g.number_of_nodes() == 0


def test_duckdb_embedding_parquet_lifecycle(tmp_path: Path) -> None:
    store = DuckDBParquetStore(tmp_path)
    sample = _make_sample_layer("emb-life")
    store.save_layer(sample)
    vecs = np.array([[0.6, 0.8], [0.8, 0.6]], dtype=np.float32)
    store.save_claim_embeddings("emb-life", ["clm-1", "clm-2"], vecs, model_id="m1")
    emb_pq = tmp_path / "layers" / "emb-life" / "claim_embeddings.parquet"
    assert emb_pq.is_file()

    # Re-saving layer cleanly removes stale embeddings index.
    store.save_layer(sample, overwrite=True)
    assert not emb_pq.is_file()
    assert store.load_claim_embeddings("emb-life", model_id="m1") is None
