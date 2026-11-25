"""Unit and integration tests for incremental ingestion and pre-warmed GraphRAG indexing."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from knowledgereduce.ingest import CrawlConfig
from knowledgereduce.models import StorageError
from knowledgereduce.pipeline import LocalFileSourceConfig, PipelineConfig, PipelineRunner
from knowledgereduce.query import HybridGraphRAGRetriever
from knowledgereduce.reduce import IntegrityValidator
from knowledgereduce.resolve import HashingEmbeddingProvider
from knowledgereduce.stack import StackManager
from knowledgereduce.storage import DuckDBParquetStore, MemoryGraphStore


def _fake_dns(_host: str, _port: int) -> list[str]:
    return ["93.184.216.34"]


def test_pipeline_prewarms_stateless_claim_embeddings_across_stores(tmp_path: Path) -> None:
    note = tmp_path / "notes.md"
    note.write_text(
        "Civic Honors was published in 2006 to advance local student civic engagement.\n"
        "Dr. Nels Lindahl founded Civic Honors while studying at the University of Kansas.\n",
        encoding="utf-8",
    )

    duck = DuckDBParquetStore(tmp_path / "duck_store")
    cfg_warm = PipelineConfig(
        layer_id="warm-duck",
        layer_name="Warm DuckDB Layer",
        local_files=[LocalFileSourceConfig(path=str(note), source_id="notes_md", trust_weight=0.9)],
        min_sentence_length=20,
        min_claim_length=20,
    )
    assert cfg_warm.build_embeddings_index is True

    layer = PipelineRunner(store=duck).run(cfg_warm)
    model_id = HashingEmbeddingProvider().model_id
    loaded = duck.load_claim_embeddings("warm-duck", model_id=model_id)
    assert loaded is not None
    ids, vecs = loaded
    assert len(ids) == len(layer.claims)
    assert vecs.shape[0] == len(layer.claims)
    assert (tmp_path / "duck_store" / "layers" / "warm-duck" / "claim_embeddings.parquet").is_file()

    # In-memory store also pre-warms cleanly.
    mem = MemoryGraphStore()
    cfg_mem = cfg_warm.model_copy(update={"layer_id": "warm-mem"})
    mem_layer = PipelineRunner(store=mem).run(cfg_mem)
    mem_loaded = mem.load_claim_embeddings("warm-mem", model_id=model_id)
    assert mem_loaded is not None
    assert len(mem_loaded[0]) == len(mem_layer.claims)

    # Disabling build_embeddings_index defers indexing until query time.
    cfg_cold = cfg_warm.model_copy(
        update={"layer_id": "cold-duck", "build_embeddings_index": False}
    )
    PipelineRunner(store=duck).run(cfg_cold)
    assert duck.load_claim_embeddings("cold-duck", model_id=model_id) is None

    ctx = HybridGraphRAGRetriever(duck).retrieve("warm-duck", "Civic Honors 2006", top_k=2)
    assert ctx.results


def test_incremental_local_file_refresh_skips_unchanged_and_records_lineage(tmp_path: Path) -> None:
    file_a = tmp_path / "a_unchanged.md"
    file_b = tmp_path / "b_evolving.txt"
    file_c = tmp_path / "c_added.txt"

    file_a.write_text(
        "Dr. H. George Frederickson taught Concepts of Civil Society at University of Kansas.\n",
        encoding="utf-8",
    )
    file_b.write_text(
        "Johnson County Community College launched the Civic Honors pilot program in 2004.\n",
        encoding="utf-8",
    )

    store = DuckDBParquetStore(tmp_path / "store")
    runner = PipelineRunner(store=store)

    base_cfg = PipelineConfig(
        layer_id="base-v1",
        layer_name="Base V1",
        local_files=[
            LocalFileSourceConfig(path=str(file_a), source_id="src_a", trust_weight=0.9),
            LocalFileSourceConfig(path=str(file_b), source_id="src_b", trust_weight=0.9),
        ],
        min_sentence_length=20,
        min_claim_length=20,
    )
    base_layer = runner.run(base_cfg)
    assert len(base_layer.sources) == 2

    # Unchanged run produces a valid empty delta layer with parent lineage preserved.
    noop_cfg = base_cfg.model_copy(
        update={
            "layer_id": "delta-noop",
            "layer_name": "Delta Noop",
            "incremental_from_layer": "base-v1",
        }
    )
    noop_layer = runner.run(noop_cfg)
    assert noop_layer.sources == []
    assert noop_layer.claims == []
    assert noop_layer.layer.parent_layer_ids == ["base-v1"]
    assert IntegrityValidator().validate(noop_layer, strict=True).valid is True

    # Modify file_b and introduce file_c while keeping file_a unchanged.
    file_b.write_text(
        "Johnson County Community College graduated four Civic Honors students in May 2005.\n",
        encoding="utf-8",
    )
    file_c.write_text(
        "Robert Putnam authored Bowling Alone about American civic participation in 2000.\n",
        encoding="utf-8",
    )

    delta_cfg = PipelineConfig(
        layer_id="delta-v2",
        layer_name="Delta V2",
        local_files=[
            LocalFileSourceConfig(path=str(file_a), source_id="src_a", trust_weight=0.9),
            LocalFileSourceConfig(path=str(file_b), source_id="src_b", trust_weight=0.9),
            LocalFileSourceConfig(path=str(file_c), source_id="src_c", trust_weight=0.9),
        ],
        incremental_from_layer="base-v1",
        min_sentence_length=20,
        min_claim_length=20,
    )
    delta_layer = runner.run(delta_cfg)
    assert {s.source_id for s in delta_layer.sources} == {"src_b", "src_c"}
    assert delta_layer.layer.parent_layer_ids == ["base-v1"]

    mgr = StackManager(store)
    assert mgr.get_ancestors("delta-v2") == ["base-v1"]
    merged = mgr.stack_overlay(
        "base-v1",
        "delta-v2",
        target_layer_id="merged-v2",
        reconcile=True,
    )
    assert IntegrityValidator().validate(merged, strict=True).valid is True
    assert any("Robert Putnam" in c.statement for c in merged.claims)
    assert any("Concepts of Civil Society" in c.statement for c in merged.claims)


def test_incremental_web_crawl_auto_seeds_known_hashes(tmp_path: Path) -> None:
    pages = {
        "/robots.txt": "User-agent: *\nAllow: /\n",
        "/p/one": "<html><body><p>Civic Honors inspires student volunteers in local communities.</p></body></html>",
        "/p/two": "<html><body><p>University of Kansas hosted civic honors workshops in 2002.</p></body></html>",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        body = pages.get(request.url.path)
        if body is None:
            return httpx.Response(404)
        ctype = "text/plain" if request.url.path == "/robots.txt" else "text/html"
        return httpx.Response(200, text=body, headers={"content-type": ctype})

    store = MemoryGraphStore()
    runner = PipelineRunner(
        store=store,
        web_transport=httpx.MockTransport(handler),
        dns_resolver=_fake_dns,
    )
    crawl_cfg = CrawlConfig(
        seed_urls=["https://example.org/p/one", "https://example.org/p/two"],
        allowed_domains=["example.org"],
        max_depth=0,
        rate_limit_seconds=0.0,
    )

    v1 = runner.run(
        PipelineConfig(
            layer_id="web-v1",
            layer_name="Web V1",
            web_crawl=crawl_cfg,
            min_sentence_length=20,
            min_claim_length=20,
        )
    )
    assert {s.uri for s in v1.sources} == {
        "https://example.org/p/one",
        "https://example.org/p/two",
    }

    # Change only /p/two; /p/one must be skipped via auto-seeded known_hashes.
    pages["/p/two"] = (
        "<html><body><p>Johnson County Community College piloted graduation with civic honors in 2004.</p></body></html>"
    )
    v2 = runner.run(
        PipelineConfig(
            layer_id="web-v2",
            layer_name="Web V2",
            web_crawl=crawl_cfg,
            incremental_from_layer="web-v1",
            min_sentence_length=20,
            min_claim_length=20,
        )
    )
    assert [s.uri for s in v2.sources] == ["https://example.org/p/two"]
    assert v2.layer.parent_layer_ids == ["web-v1"]


def test_incremental_config_validation_missing_base_layer_and_yaml(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        PipelineConfig(
            layer_id="bad-parent",
            layer_name="Bad Parent",
            incremental_from_layer="../escape",
        )

    store = MemoryGraphStore()
    cfg = PipelineConfig(
        layer_id="delta-missing",
        layer_name="Delta Missing",
        incremental_from_layer="nonexistent-base",
    )
    with pytest.raises(StorageError, match="does not exist"):
        PipelineRunner(store=store).ingest(cfg)

    yaml_path = tmp_path / "inc.yaml"
    yaml_path.write_text(
        """
layer_id: yaml-inc
layer_name: YAML Incremental
incremental_from_layer: base-v1
build_embeddings_index: false
""",
        encoding="utf-8",
    )
    parsed = PipelineConfig.from_yaml(yaml_path)
    assert parsed.incremental_from_layer == "base-v1"
    assert parsed.build_embeddings_index is False


def test_pipeline_parallel_worker_config_parity_and_store_lifecycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from knowledgereduce.map.structured import StructuredMappingConfig

    doc_one = tmp_path / "doc1.md"
    doc_two = tmp_path / "doc2.md"
    doc_one.write_text(
        "Chapter Overview\nWhat makes community engagement succeed?\n"
        "Nels Lindahl founded Civic Honors in 2006 to inspire civic participation.\n",
        encoding="utf-8",
    )
    doc_two.write_text(
        "Program Origins\nWhy did the program expand in Kansas?\n"
        "The University of Kansas hosted early student seminars on civil society.\n",
        encoding="utf-8",
    )

    csv_a = tmp_path / "people_a.csv"
    csv_b = tmp_path / "people_b.csv"
    csv_a.write_text("name,role\nNels Lindahl,Founder\n", encoding="utf-8")
    csv_b.write_text("name,role\nCharles Carlsen,Advisor\n", encoding="utf-8")

    # Verify max_workers=2 matches max_workers=1 for skip_headings/skip_questions and structured_config.
    files = [
        LocalFileSourceConfig(path=str(doc_one), source_id="d1"),
        LocalFileSourceConfig(path=str(doc_two), source_id="d2"),
        LocalFileSourceConfig(path=str(csv_a), source_id="c1"),
        LocalFileSourceConfig(path=str(csv_b), source_id="c2"),
    ]
    base_cfg = PipelineConfig(
        layer_id="par-1",
        layer_name="Parallel 1",
        store_dir=str(tmp_path / "par_store"),
        local_files=files,
        skip_headings=False,
        skip_questions=False,
        min_sentence_length=15,
        min_claim_length=15,
        structured_config=StructuredMappingConfig(statement_template="{name} serves as {role}."),
        max_workers=1,
    )
    runner_1 = PipelineRunner()
    docs = runner_1.ingest(base_cfg)
    b1 = runner_1.map_documents(docs, base_cfg)
    b2 = runner_1.map_documents(docs, base_cfg.model_copy(update={"max_workers": 2}))

    assert [c.statement for b in b1 for c in b.claims] == [
        c.statement for b in b2 for c in b.claims
    ]
    all_stmts = [c.statement for b in b2 for c in b.claims]
    assert any("Chapter Overview" in s for s in all_stmts)
    assert any("What makes community engagement succeed?" in s for s in all_stmts)
    assert any("Nels Lindahl serves as Founder." in s for s in all_stmts)

    # Verify internal stores opened by PipelineRunner are closed cleanly after run().
    closed_stores: list[str] = []
    real_close = DuckDBParquetStore.close

    def _spy_close(self_store: DuckDBParquetStore) -> None:
        closed_stores.append(str(self_store.root_dir))
        real_close(self_store)

    monkeypatch.setattr(DuckDBParquetStore, "close", _spy_close)
    PipelineRunner().run(base_cfg)
    assert len(closed_stores) >= 1

    # Explicit store supplied by caller must NOT be closed automatically by PipelineRunner.
    explicit = DuckDBParquetStore(tmp_path / "explicit_store")
    before = len(closed_stores)
    PipelineRunner(store=explicit).run(
        base_cfg.model_copy(update={"layer_id": "par-exp", "incremental_from_layer": None})
    )
    assert len(closed_stores) == before
    explicit.close()
