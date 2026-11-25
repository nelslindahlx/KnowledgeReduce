"""Offline multi-source, incremental, stacked, and conflict-aware golden benchmark."""

from __future__ import annotations

import argparse
import dataclasses
import json
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from knowledgereduce.export import render_layer_markdown
from knowledgereduce.mcp.server import build_graph_analytics_payload
from knowledgereduce.models import (
    ConflictStrategy,
    LayerData,
    MergeMode,
)
from knowledgereduce.pipeline import LocalFileSourceConfig, PipelineConfig, PipelineRunner
from knowledgereduce.query import HybridGraphRAGRetriever
from knowledgereduce.reduce import IntegrityValidator
from knowledgereduce.stack import StackManager
from knowledgereduce.storage import DuckDBParquetStore

DEFAULT_MULTISOURCE_FLOORS: dict[str, dict[str, float | int]] = {
    "min": {
        "skipped_unchanged": 1,
        "conflict_detection_recall": 1.0,
        "conflict_resolution_accuracy": 1.0,
        "contradicts_edges": 3,
        "retrieval_hit_at_1": 1.0,
        "disputed_conflict_surfacing_rate": 1.0,
        "mean_quality_score": 65.0,
    },
    "max": {
        "validation_errors": 0,
        "validation_warnings": 0,
        "isolated_entities": 0,
        "total_seconds": 5.0,
    },
}


@dataclass(frozen=True)
class MultiSourceStackMetrics:
    """Quantitative quality, lineage, conflict, and latency metrics for multi-source stacking."""

    base_sources: int
    delta_sources: int
    skipped_unchanged: int
    disputed_sources: int
    stacked_sources: int
    stacked_entities: int
    stacked_claims: int
    stacked_relations: int
    contradicts_edges: int
    conflicts_detected: int
    conflict_detection_recall: float
    conflict_resolution_accuracy: float
    isolated_entities: int
    validation_errors: int
    validation_warnings: int
    mean_quality_score: float
    retrieval_hit_at_1: float
    disputed_conflict_surfacing_rate: float
    graph_nodes: int
    graph_edges: int
    community_count: int
    markdown_chars: int
    total_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class MultiSourceStackResult:
    """Complete artifacts and metrics returned by ``evaluate_multisource_stack``."""

    metrics: MultiSourceStackMetrics
    delta_parent_layer_ids: list[str]
    stacked_parent_layer_ids: list[str]
    stacked_layer: LayerData
    markdown_brief: str
    analytics: dict[str, Any]
    embeddings_present: dict[str, bool]
    passed_floors: bool
    floor_failures: list[str]


def _check_floors(metrics: MultiSourceStackMetrics) -> tuple[bool, list[str]]:
    payload = metrics.to_dict()
    failures: list[str] = []
    for k, min_v in DEFAULT_MULTISOURCE_FLOORS["min"].items():
        if float(payload[k]) < float(min_v):
            failures.append(f"{k}={payload[k]} < min {min_v}")
    for k, max_v in DEFAULT_MULTISOURCE_FLOORS["max"].items():
        if float(payload[k]) > float(max_v):
            failures.append(f"{k}={payload[k]} > max {max_v}")
    return len(failures) == 0, failures


def evaluate_multisource_stack() -> MultiSourceStackResult:
    """Run the offline HTML + Markdown incremental delta + conflicting overlay golden benchmark."""
    t_start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="kr_multisource_golden_") as tmp:
        root = Path(tmp)
        docs_dir = root / "corpus"
        docs_dir.mkdir(parents=True, exist_ok=True)
        store_dir = root / "store"

        overview_html = docs_dir / "overview.html"
        overview_html.write_text(
            "<html><head><title>Civic Honors Overview</title></head><body><main>\n"
            "<h1>Program History</h1>\n"
            "<p>Civic Honors was published in 2006 to inspire student civic engagement.</p>\n"
            "<p>University of Kansas is located in Lawrence, Kansas.</p>\n"
            "<p>Dr. Nels Lindahl studied at University of Kansas during the spring of 2002.</p>\n"
            "</main></body></html>\n",
            encoding="utf-8",
        )

        curriculum_md = docs_dir / "curriculum.md"
        curriculum_md.write_text(
            "---\ntitle: Curriculum Notes\nauthor: Dr. H. George Frederickson\n---\n\n"
            "# Civil Society Seminar\n\n"
            "Concepts of Civil Society was taught by Dr. H. George Frederickson at the University of Kansas.\n",
            encoding="utf-8",
        )

        with DuckDBParquetStore(store_dir) as store:
            runner = PipelineRunner(store=store)

            base_layer = runner.run(
                PipelineConfig(
                    layer_id="ms-base",
                    layer_name="Multi-Source Base",
                    store_dir=str(store_dir),
                    local_files=[
                        LocalFileSourceConfig(
                            path=str(overview_html),
                            source_id="src_overview_html",
                            trust_weight=0.90,
                        ),
                        LocalFileSourceConfig(
                            path=str(curriculum_md),
                            source_id="src_curriculum_md",
                            trust_weight=0.90,
                        ),
                    ],
                    mapper="deterministic",
                    min_sentence_length=20,
                    min_claim_length=20,
                    build_embeddings_index=True,
                )
            )

            # Update curriculum.md & add extensions.html while leaving overview.html byte-identical.
            curriculum_md.write_text(
                "---\ntitle: Curriculum Notes\nauthor: Dr. H. George Frederickson\n---\n\n"
                "# Civil Society Seminar\n\n"
                "Concepts of Civil Society was taught by Dr. H. George Frederickson at the University of Kansas.\n"
                "Dr. Charles J. Carlsen supported the Civic Honors Program at Johnson County Community College.\n",
                encoding="utf-8",
            )
            extensions_html = docs_dir / "extensions.html"
            extensions_html.write_text(
                "<html><head><title>Scholarly Influences</title></head><body><main>\n"
                "<p>Robert Putnam authored Bowling Alone in 2000 on community civic engagement.</p>\n"
                "</main></body></html>\n",
                encoding="utf-8",
            )

            delta_inputs = [
                LocalFileSourceConfig(
                    path=str(overview_html),
                    source_id="src_overview_html",
                    trust_weight=0.90,
                ),
                LocalFileSourceConfig(
                    path=str(curriculum_md),
                    source_id="src_curriculum_md",
                    trust_weight=0.90,
                ),
                LocalFileSourceConfig(
                    path=str(extensions_html),
                    source_id="src_extensions_html",
                    trust_weight=0.90,
                ),
            ]
            delta_layer = runner.run(
                PipelineConfig(
                    layer_id="ms-delta",
                    layer_name="Multi-Source Incremental Delta",
                    store_dir=str(store_dir),
                    incremental_from_layer="ms-base",
                    local_files=delta_inputs,
                    mapper="deterministic",
                    min_sentence_length=20,
                    min_claim_length=20,
                    build_embeddings_index=True,
                )
            )
            skipped_unchanged = len(delta_inputs) - len(delta_layer.sources)

            disputed_md = docs_dir / "disputed_blog.md"
            disputed_md.write_text(
                "---\ntitle: Unverified Commentary\n---\n\n"
                "Civic Honors was published in 2020 to confuse regional readers.\n"
                "University of Kansas is located in Topeka, Kansas.\n"
                "Dr. Nels Lindahl studied at University of Kansas during the spring of 2004.\n",
                encoding="utf-8",
            )
            disputed_layer = runner.run(
                PipelineConfig(
                    layer_id="ms-disputed",
                    layer_name="Disputed Overlay",
                    store_dir=str(store_dir),
                    local_files=[
                        LocalFileSourceConfig(
                            path=str(disputed_md),
                            source_id="src_disputed_md",
                            trust_weight=0.45,
                        )
                    ],
                    mapper="deterministic",
                    min_sentence_length=20,
                    min_claim_length=20,
                    build_embeddings_index=True,
                )
            )

            stacked = StackManager(store).merge_layers(
                ["ms-base", "ms-delta", "ms-disputed"],
                target_layer_id="ms-stacked",
                target_name="Multi-Source Stacked Golden",
                mode=MergeMode.UNION,
                conflict_strategy=ConflictStrategy.PRESERVE_DISPUTE,
                reconcile=True,
            )
            retriever = HybridGraphRAGRetriever(store)
            retriever.build_index("ms-stacked")

            report = IntegrityValidator().validate(stacked, strict=True)
            connected_nodes = {r.source_id for r in stacked.relations} | {
                r.target_id for r in stacked.relations
            }
            isolated_entities = sum(
                1 for e in stacked.entities if e.entity_id not in connected_nodes
            )
            contradicts_edges = sum(
                1 for r in stacked.relations if r.relation_type == "CONTRADICTS"
            )

            expected_winners = ("2006", "Lawrence, Kansas", "2002")
            winners = [
                str(cf.winning_value) for cf in stacked.conflicts if cf.winning_value is not None
            ]
            winner_hits = sum(
                1 for exp in expected_winners if any(exp.lower() in w.lower() for w in winners)
            )
            conflict_detection_recall = min(1.0, len(stacked.conflicts) / len(expected_winners))
            conflict_resolution_accuracy = winner_hits / len(expected_winners)

            queries: list[tuple[str, str, bool]] = [
                ("When was Civic Honors published?", "2006", True),
                ("Where is University of Kansas located?", "Lawrence, Kansas", True),
                ("When did Nels Lindahl study at University of Kansas?", "2002", True),
                ("Who authored Bowling Alone?", "Robert Putnam", False),
            ]
            hit1_count = 0
            disputed_queries = 0
            disputed_surfaced = 0
            for query_text, expected_sub, expect_conflict in queries:
                ctx = retriever.retrieve("ms-stacked", query_text, top_k=3, hops=1)
                if ctx.results and expected_sub.lower() in ctx.results[0].claim.statement.lower():
                    hit1_count += 1
                if expect_conflict:
                    disputed_queries += 1
                    if ctx.conflicts:
                        disputed_surfaced += 1

            markdown_brief = render_layer_markdown(stacked)
            analytics = build_graph_analytics_payload(store, "ms-stacked", metric="pagerank")
            layers_dir = store_dir / "layers"
            embeddings_present = {
                lid: (layers_dir / lid / "claim_embeddings.parquet").is_file()
                for lid in ("ms-base", "ms-delta", "ms-disputed", "ms-stacked")
            }

            metrics = MultiSourceStackMetrics(
                base_sources=len(base_layer.sources),
                delta_sources=len(delta_layer.sources),
                skipped_unchanged=skipped_unchanged,
                disputed_sources=len(disputed_layer.sources),
                stacked_sources=len(stacked.sources),
                stacked_entities=len(stacked.entities),
                stacked_claims=len(stacked.claims),
                stacked_relations=len(stacked.relations),
                contradicts_edges=contradicts_edges,
                conflicts_detected=len(stacked.conflicts),
                conflict_detection_recall=round(conflict_detection_recall, 4),
                conflict_resolution_accuracy=round(conflict_resolution_accuracy, 4),
                isolated_entities=isolated_entities,
                validation_errors=len(report.errors),
                validation_warnings=len(report.warnings),
                mean_quality_score=float(report.metrics["mean_quality_score"]),
                retrieval_hit_at_1=round(hit1_count / len(queries), 4),
                disputed_conflict_surfacing_rate=round(
                    disputed_surfaced / max(1, disputed_queries), 4
                ),
                graph_nodes=int(analytics["node_count"]),
                graph_edges=int(analytics["edge_count"]),
                community_count=int(analytics["community_count"]),
                markdown_chars=len(markdown_brief),
                total_seconds=round(time.perf_counter() - t_start, 3),
            )
            passed_floors, floor_failures = _check_floors(metrics)
            return MultiSourceStackResult(
                metrics=metrics,
                delta_parent_layer_ids=list(delta_layer.layer.parent_layer_ids),
                stacked_parent_layer_ids=list(stacked.layer.parent_layer_ids),
                stacked_layer=stacked,
                markdown_brief=markdown_brief,
                analytics=analytics,
                embeddings_present=embeddings_present,
                passed_floors=passed_floors,
                floor_failures=floor_failures,
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the offline multi-source stacked & incremental golden benchmark."
    )
    parser.add_argument(
        "--strict-regression",
        action="store_true",
        help="Exit non-zero if any multi-source golden floor fails.",
    )
    args = parser.parse_args()

    result = evaluate_multisource_stack()
    payload = {
        "metrics": result.metrics.to_dict(),
        "delta_parent_layer_ids": result.delta_parent_layer_ids,
        "stacked_parent_layer_ids": result.stacked_parent_layer_ids,
        "embeddings_present": result.embeddings_present,
        "passed_floors": result.passed_floors,
        "floor_failures": result.floor_failures,
    }
    print(json.dumps(payload, indent=2))
    if args.strict_regression and not result.passed_floors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
