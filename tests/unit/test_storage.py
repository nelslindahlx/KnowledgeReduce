"""Unit tests for MemoryGraphStore and DuckDBParquetStore."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
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
from knowledgereduce.storage import (
    ClaimSummary,
    DuckDBParquetStore,
    GraphStore,
    MemoryGraphStore,
)


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


def test_duckdb_fixed_size_embeddings_cache_and_legacy_fallback(tmp_path: Path) -> None:
    store = DuckDBParquetStore(tmp_path)
    sample = _make_sample_layer("emb-cache")
    store.save_layer(sample)

    vecs = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)
    store.save_claim_embeddings("emb-cache", ["clm-1", "clm-2"], vecs, model_id="m1")

    emb_pq = tmp_path / "layers" / "emb-cache" / "claim_embeddings.parquet"
    emb_schema = pq.read_schema(emb_pq)
    assert pa.types.is_fixed_size_list(emb_schema.field("embedding").type)

    first = store.load_claim_embeddings("emb-cache", model_id="m1")
    second = store.load_claim_embeddings("emb-cache", model_id="m1")
    assert first is not None and second is not None
    assert first[1] is second[1]
    assert first[1].flags.writeable is False
    # Returned claim IDs list is a fresh copy so caller mutation cannot corrupt cache.
    first[0].append("mutated")
    third = store.load_claim_embeddings("emb-cache", model_id="m1")
    assert third is not None and third[0] == ["clm-1", "clm-2"]

    # Updating embeddings invalidates cache cleanly.
    vecs_updated = np.array([[0.0, 0.0, 1.0], [0.5, 0.5, 0.0]], dtype=np.float32)
    store.save_claim_embeddings("emb-cache", ["clm-1", "clm-2"], vecs_updated, model_id="m1")
    reloaded = store.load_claim_embeddings("emb-cache", model_id="m1")
    assert reloaded is not None and np.allclose(reloaded[1], vecs_updated)

    # Backward-compatible read of legacy variable-size list<float32> Parquet files.
    legacy_schema = pa.schema(
        [
            ("claim_id", pa.string()),
            ("model_id", pa.string()),
            ("embedding", pa.list_(pa.float32())),
        ]
    )
    legacy_table = pa.table(
        {
            "claim_id": pa.array(["clm-1", "clm-2"], type=pa.string()),
            "model_id": pa.array(["m-legacy", "m-legacy"], type=pa.string()),
            "embedding": pa.array(
                [[0.25, 0.75, 0.0], [0.0, 0.25, 0.75]], type=pa.list_(pa.float32())
            ),
        },
        schema=legacy_schema,
    )
    pq.write_table(legacy_table, emb_pq)
    legacy_loaded = store.load_claim_embeddings("emb-cache", model_id="m-legacy")
    assert legacy_loaded is not None
    assert np.allclose(
        legacy_loaded[1], np.array([[0.25, 0.75, 0.0], [0.0, 0.25, 0.75]], dtype=np.float32)
    )

    # Empty and zero-width edge cases + delete eviction.
    store.save_claim_embeddings("emb-cache", [], np.empty((0, 0), dtype=np.float32), model_id="m1")
    assert store.load_claim_embeddings("emb-cache", model_id="m1") is None

    store.save_claim_embeddings(
        "emb-cache", ["clm-1", "clm-2"], np.empty((2, 0), dtype=np.float32), model_id="m0"
    )
    zero_dim = store.load_claim_embeddings("emb-cache", model_id="m0")
    assert zero_dim is not None and zero_dim[1].shape == (2, 0)

    store.delete_layer("emb-cache")
    assert ("emb-cache", "m0") not in store._embedding_cache


def test_claim_summary_projection_and_persistent_duckdb_session(tmp_path: Path) -> None:
    sample = _make_sample_layer("summary-layer")
    mem = MemoryGraphStore()
    mem.save_layer(sample)

    mem_summaries = mem.search_claim_summaries_lexical("summary-layer", "published 2006")
    assert [s.claim_id for s in mem_summaries] == ["clm-1", "clm-2"]
    assert all(isinstance(s, ClaimSummary) for s in mem_summaries)
    assert mem.search_claim_summaries_lexical("summary-layer", "published", limit=0) == []
    assert [s.claim_id for s in mem.get_claim_summaries_by_ids("summary-layer", ["clm-2"])] == [
        "clm-2"
    ]
    assert mem.get_claim_summaries_by_ids("summary-layer", []) == []

    with DuckDBParquetStore(tmp_path) as duck:
        duck.save_layer(sample)
        # First query initializes persistent in-memory DuckDB read connection.
        assert [c.claim_id for c in duck.list_claims("summary-layer")] == ["clm-1", "clm-2"]
        first_con = duck._read_con
        assert first_con is not None

        # Subsequent queries reuse the exact same DuckDB read connection.
        assert duck.list_claim_texts("summary-layer")
        assert duck._read_con is first_con

        # Summary search matches full lexical search order and populates mtime/size cache.
        duck_summaries = duck.search_claim_summaries_lexical("summary-layer", "published 2006")
        duck_full = duck.search_claims_lexical("summary-layer", "published 2006")
        assert [s.claim_id for s in duck_summaries] == [c.claim_id for c in duck_full]
        assert (
            duck.search_claim_summaries_lexical("summary-layer", "", limit=1)[0].claim_id == "clm-1"
        )
        assert duck.search_claim_summaries_lexical("summary-layer", "published", limit=0) == []
        assert "summary-layer" in duck._claim_summary_cache
        assert [
            s.claim_id for s in duck.get_claim_summaries_by_ids("summary-layer", ["clm-2", "clm-1"])
        ] == ["clm-2", "clm-1"]
        assert duck.get_claim_summaries_by_ids("summary-layer", []) == []

        # Overwrite and delete cleanly evict summary and graph caches.
        duck.save_layer(sample, overwrite=True)
        assert "summary-layer" not in duck._claim_summary_cache
        duck.search_claim_summaries_lexical("summary-layer", "2006")
        assert "summary-layer" in duck._claim_summary_cache

        cached_g, cached_ents, cached_cfs = duck.get_k_hop_subgraph(
            "summary-layer", ["clm-1"], hops=1
        )
        assert "summary-layer" in duck._layer_graph_cache

        # Uncached DuckDB SQL fallback matches cached k-hop output identically.
        with DuckDBParquetStore(tmp_path, graph_cache_max_rows=0) as uncached:
            sql_g, sql_ents, sql_cfs = uncached.get_k_hop_subgraph(
                "summary-layer", ["clm-1"], hops=1
            )
        assert set(cached_g.nodes) == set(sql_g.nodes)
        assert sorted(cached_g.edges) == sorted(sql_g.edges)
        assert {e.entity_id for e in cached_ents} == {e.entity_id for e in sql_ents}
        assert [c.conflict_id for c in cached_cfs] == [c.conflict_id for c in sql_cfs]

        duck.delete_layer("summary-layer")
        assert "summary-layer" not in duck._claim_summary_cache
        assert "summary-layer" not in duck._layer_graph_cache

    assert duck._read_con is None
    assert duck._claim_summary_cache == {}


def test_store_metadata_only_manifest_and_source_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from knowledgereduce.pipeline import load_layer_source_hashes

    sample = _make_sample_layer("meta-layer")
    mem = MemoryGraphStore()
    mem.save_layer(sample)
    duck = DuckDBParquetStore(tmp_path)
    duck.save_layer(sample)

    for backend in (mem, duck):
        manifest = backend.get_layer_manifest("meta-layer")
        assert manifest.layer_id == "meta-layer"
        assert manifest.name == "Civic Honors Sample"
        by_uri, by_id = backend.list_source_hashes("meta-layer")
        assert by_uri == {"https://civichonors.com/": sample.sources[0].content_sha256}
        assert by_id == {"src-civic": sample.sources[0].content_sha256}
        with pytest.raises(StorageError, match="not found"):
            backend.get_layer_manifest("missing-layer")
        with pytest.raises(StorageError, match="not found"):
            backend.list_source_hashes("missing-layer")

    # Verify load_layer_source_hashes never falls back to full load_layer() on DuckDB.
    def _boom(_layer_id: str) -> LayerData:
        raise AssertionError("load_layer should not be called")

    monkeypatch.setattr(duck, "load_layer", _boom)
    assert load_layer_source_hashes(duck, "meta-layer") == (
        {"https://civichonors.com/": sample.sources[0].content_sha256},
        {"src-civic": sample.sources[0].content_sha256},
    )
    duck.close()


def test_duckdb_save_layer_atomic_overwrite_rollback_and_filter_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample = _make_sample_layer("atomic-v1")
    with DuckDBParquetStore(tmp_path) as duck:
        duck.save_layer(sample)
        assert duck.list_claims("atomic-v1", limit=0) == []
        assert duck.list_claims("atomic-v1", tags_any=[]) == []
        with pytest.raises(StorageError, match="Unsupported sort_by"):
            duck.list_claims("atomic-v1", sort_by="invalid_col")  # type: ignore[arg-type]

        real_rename = Path.rename
        rename_calls = 0

        def _failing_staging_rename(self_path: Path, target: Path) -> Path:
            nonlocal rename_calls
            if target == duck.layers_dir / "atomic-v1" and self_path.name.startswith(".staging_"):
                rename_calls += 1
                raise OSError("Simulated swap failure")
            return real_rename(self_path, target)

        monkeypatch.setattr(Path, "rename", _failing_staging_rename)
        modified = sample.model_copy(
            update={"layer": sample.layer.model_copy(update={"name": "Broken Update"})}
        )
        with pytest.raises(OSError, match="Simulated swap failure"):
            duck.save_layer(modified, overwrite=True)

        assert rename_calls == 1
        # Original layer was cleanly restored and no .staging_/.backup_ dirs leaked into list_layers.
        restored = duck.load_layer("atomic-v1")
        assert restored.layer.name == "Civic Honors Sample"
        assert [layer.layer_id for layer in duck.list_layers()] == ["atomic-v1"]
        leftover_tmp = [p for p in duck.layers_dir.iterdir() if p.name.startswith(".staging_")]
        assert leftover_tmp == []


def test_duckdb_save_layer_serializes_raw_date_objects_in_metadata_and_attributes(
    tmp_path: Path,
) -> None:
    from datetime import UTC, date, datetime

    sample = _make_sample_layer("raw-dates")
    sample.sources[0].metadata["raw_date"] = date(2024, 6, 15)
    sample.sources[0].metadata["raw_dt"] = datetime(2025, 1, 10, 12, 0, tzinfo=UTC)
    sample.entities[0].attributes["created_on"] = date(2006, 1, 1)
    sample.relations[0].attributes["verified_on"] = date(2025, 3, 1)

    with DuckDBParquetStore(tmp_path) as duck:
        duck.save_layer(sample)
        reloaded = duck.load_layer("raw-dates")
        assert reloaded.sources[0].metadata["raw_date"] == "2024-06-15"
        assert reloaded.entities[0].attributes["created_on"] == "2006-01-01"
        assert reloaded.relations[0].attributes["verified_on"] == "2025-03-01"
