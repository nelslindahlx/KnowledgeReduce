"""Offline end-to-end integration tests for KnowledgeReduce using frozen fixtures."""

from __future__ import annotations

from pathlib import Path

import httpx
import respx

from knowledgereduce.ingest import CrawlConfig
from knowledgereduce.pipeline import LocalFileSourceConfig, PipelineConfig, PipelineRunner
from knowledgereduce.reduce import IntegrityValidator
from knowledgereduce.storage import DuckDBParquetStore

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _fake_dns(_host: str, _port: int) -> list[str]:
    return ["93.184.216.34"]


def test_end_to_end_civichonors_pipeline_with_respx_and_duckdb(tmp_path: Path) -> None:
    index_html = (FIXTURES_DIR / "civichonors_index.html").read_text(encoding="utf-8")
    book_html = (FIXTURES_DIR / "civichonors_book.html").read_text(encoding="utf-8")
    about_html = (FIXTURES_DIR / "civichonors_about.html").read_text(encoding="utf-8")
    csv_path = FIXTURES_DIR / "civichonors_facts.csv"
    json_path = FIXTURES_DIR / "civichonors_notes.json"

    store_dir = tmp_path / "store"
    ckpt_dir = tmp_path / "checkpoints"

    config = PipelineConfig(
        layer_id="civichonors-e2e",
        layer_name="CivicHonors End-to-End",
        store_dir=str(store_dir),
        checkpoint_dir=str(ckpt_dir),
        web_crawl=CrawlConfig(
            seed_urls=["https://civichonors.com/"],
            allowed_domains=["civichonors.com"],
            max_depth=1,
            max_pages_per_domain=5,
            rate_limit_seconds=0.0,
            trust_weight=0.7,
        ),
        local_files=[
            LocalFileSourceConfig(path=str(csv_path), source_id="csv_curated", trust_weight=0.95),
            LocalFileSourceConfig(path=str(json_path), source_id="json_notes", trust_weight=0.9),
        ],
        mapper="deterministic",
        min_sentence_length=20,
        min_claim_length=20,
    )

    with respx.mock(assert_all_called=False) as router:
        router.get("https://civichonors.com/robots.txt").mock(
            return_value=httpx.Response(200, text="User-agent: *\nAllow: /\n")
        )
        router.get("https://civichonors.com/").mock(
            return_value=httpx.Response(200, text=index_html, headers={"content-type": "text/html"})
        )
        router.get("https://civichonors.com/p/the-book").mock(
            return_value=httpx.Response(200, text=book_html, headers={"content-type": "text/html"})
        )
        router.get("https://civichonors.com/about").mock(
            return_value=httpx.Response(200, text=about_html, headers={"content-type": "text/html"})
        )

        runner = PipelineRunner(dns_resolver=_fake_dns)
        layer_data = runner.run(config)
        assert layer_data.layer.layer_id == "civichonors-e2e"

    # Checkpoints were emitted at all 3 stages
    assert (ckpt_dir / "01_ingested.jsonl").is_file()
    assert (ckpt_dir / "02_mapped.jsonl").is_file()
    assert (ckpt_dir / "03_resolved.jsonl").is_file()

    # Persisted cleanly in DuckDB + Parquet
    store = DuckDBParquetStore(store_dir)
    assert store.layer_exists("civichonors-e2e")
    loaded = store.load_layer("civichonors-e2e")

    # Connected MultiDiGraph with >0 entities, claims, typed relations, and preserved dispute!
    assert len(loaded.sources) == 5  # 3 crawled pages + CSV + JSON
    assert len(loaded.entities) >= 6
    assert len(loaded.claims) >= 6
    assert len(loaded.relations) > 0
    assert any(r.relation_type == "MENTIONS" for r in loaded.relations)
    assert any(r.relation_type == "CONTRADICTS" for r in loaded.relations)
    assert any(cf.needs_review and cf.winning_value == "2006" for cf in loaded.conflicts)

    # Exact duplicate across index & book ("Civic Honors was published in 2006...") was reduced
    assert loaded.layer.stats["claims_after"] < loaded.layer.stats["claims_before"]

    # Integrity validation succeeds cleanly
    report = IntegrityValidator().validate(loaded, strict=True)
    assert report.valid is True
    assert report.metrics["relations"] >= 20
    # Every extracted entity is connected into the graph (only entity-less generic prose sentences may be isolates)
    connected_nodes = {r.source_id for r in loaded.relations} | {
        r.target_id for r in loaded.relations
    }
    assert {e.entity_id for e in loaded.entities}.issubset(connected_nodes)

    # Verify resume from checkpoints & parallel worker execution produce matching counts
    yaml_cfg_path = tmp_path / "pipeline.yaml"
    yaml_cfg_path.write_text(
        f"""
layer_id: civichonors-parallel
layer_name: Parallel Resume
store_dir: {store_dir}
local_files:
  - path: {csv_path}
    source_id: csv_curated
    trust_weight: 0.95
  - path: {json_path}
    source_id: json_notes
    trust_weight: 0.9
mapper: deterministic
max_workers: 2
""",
        encoding="utf-8",
    )
    loaded_cfg = PipelineConfig.from_yaml(yaml_cfg_path)
    parallel_runner = PipelineRunner(store=store)
    parallel_layer = parallel_runner.run(loaded_cfg)
    assert len(parallel_layer.claims) > 0

    resumed_cfg = loaded_cfg.model_copy(
        update={"layer_id": "civichonors-resumed", "overwrite": True}
    )
    resumed = parallel_runner.run_from_mapped_checkpoint(ckpt_dir / "02_mapped.jsonl", resumed_cfg)
    assert len(resumed.claims) == len(loaded.claims)
    assert len(resumed.conflicts) == len(loaded.conflicts)
