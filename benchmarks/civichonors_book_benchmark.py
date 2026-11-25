"""Offline real-world golden evaluation benchmark for 'Civic Honors: The Book'."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import sys
import tempfile
import time
import tracemalloc
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from knowledgereduce.map import DeterministicNLPMapper, SpacyNLPMapper
from knowledgereduce.models import ConflictStrategy, LayerData, SourceDocument
from knowledgereduce.query import HybridGraphRAGRetriever
from knowledgereduce.reduce import IntegrityValidator, KnowledgeReducer
from knowledgereduce.storage import DuckDBParquetStore

DATASET_DIR = Path(__file__).resolve().parent / "datasets" / "civichonors_book"
SOURCE_DOC_PATH = DATASET_DIR / "source_document.jsonl"
GOLD_ANNOTATIONS_PATH = DATASET_DIR / "gold_annotations.json"
BASELINE_PATH = DATASET_DIR / "baseline_v1_1_0.json"
BASELINE_V13_PATH = DATASET_DIR / "baseline_v1_3_0.json"
BASELINE_V14_PATH = DATASET_DIR / "baseline_v1_4_0.json"

DEFAULT_REGRESSION_FLOORS: dict[str, dict[str, float | int]] = {
    "min": {
        "core_entity_name_recall": 0.99,
        "core_entity_typed_recall": 0.98,
        "core_entity_type_accuracy": 0.98,
        "alias_merge_recall": 0.98,
        "core_fact_retention": 0.99,
        "retrieval_hit_at_1": 0.98,
        "retrieval_hit_at_5": 0.98,
        "retrieval_mrr_at_5": 0.98,
        "claim_connectivity_rate": 0.50,
        "grounded_triple_rate": 0.26,
        "mean_quality_score": 59.0,
    },
    "max": {
        "cross_type_duplicate_count": 0,
        "heading_noise_fp_count": 0,
        "isolated_node_ratio": 0.45,
        "total_seconds": 8.0,
    },
}

_HIGHER_IS_BETTER: tuple[str, ...] = (
    "core_entity_name_recall",
    "core_entity_typed_recall",
    "core_entity_type_accuracy",
    "alias_merge_recall",
    "core_fact_retention",
    "retrieval_hit_at_1",
    "retrieval_hit_at_3",
    "retrieval_hit_at_5",
    "retrieval_mrr_at_5",
    "claim_connectivity_rate",
    "grounded_triple_rate",
    "mean_quality_score",
    "semantic_relations",
)

_LOWER_IS_BETTER: tuple[str, ...] = (
    "cross_type_duplicate_count",
    "heading_noise_fp_count",
    "heading_noise_fp_rate",
    "isolated_nodes",
    "isolated_node_ratio",
)


def _norm(text: str) -> str:
    return " ".join(text.strip().lower().split())


@dataclass(frozen=True)
class BookGoldenMetrics:
    """Comprehensive baseline & regression metrics on the frozen Civic Honors book."""

    corpus_id: str
    mapper: str
    min_sentence_length: int
    source_chars: int
    source_words: int
    content_sha256: str
    valid: bool
    validation_errors: int
    validation_warnings: int
    entities: int
    claims_before: int
    claims_after: int
    compression_ratio: float
    relations: int
    mentions_relations: int
    co_occurs_relations: int
    semantic_relations: int
    isolated_nodes: int
    isolated_node_ratio: float
    connected_components: int
    edge_density: float
    claim_connectivity_rate: float
    grounded_triple_rate: float
    mean_quality_score: float
    core_entity_name_recall: float
    core_entity_typed_recall: float
    core_entity_type_accuracy: float
    alias_merge_recall: float
    cross_type_duplicate_count: int
    heading_noise_fp_count: int
    heading_noise_fp_rate: float
    core_fact_retention: float
    retrieval_hit_at_1: float
    retrieval_hit_at_3: float
    retrieval_hit_at_5: float
    retrieval_mrr_at_5: float
    query_ranks: dict[str, int | None]
    missing_core_entities: list[str]
    mistyped_core_entities: list[dict[str, Any]]
    cross_type_duplicate_names: list[str]
    missing_reference_facts: list[str]
    map_seconds: float
    reduce_seconds: float
    validate_seconds: float
    store_seconds: float
    query_cold_seconds: float
    query_warm_avg_seconds: float
    total_seconds: float
    peak_traced_mib: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize metrics to a JSON-compatible dictionary."""
        return dataclasses.asdict(self)


@dataclass
class BookEvaluationResult:
    """Full evaluation output bundling metrics, reduced layer data, and integrity flags."""

    metrics: BookGoldenMetrics
    layer: LayerData
    validation_valid: bool
    warm_query_top1_matches_cold: bool


def load_book_corpus(path: Path = SOURCE_DOC_PATH) -> SourceDocument:
    """Load the frozen single-document book corpus and verify its content SHA-256."""
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if len(lines) != 1:
        raise ValueError(f"Expected 1 SourceDocument line in {path}, found {len(lines)}.")
    doc = SourceDocument.model_validate_json(lines[0])
    computed_sha = hashlib.sha256(doc.content.encode("utf-8")).hexdigest()
    if doc.content_sha256 and computed_sha != doc.content_sha256:
        raise ValueError(
            f"SHA-256 mismatch for {path}: expected {doc.content_sha256}, got {computed_sha}."
        )
    return doc


def load_gold_annotations(path: Path = GOLD_ANNOTATIONS_PATH) -> dict[str, Any]:
    """Load curated entities, noise canaries, reference facts, and QA retrieval queries."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}.")
    return data


def load_baseline(path: Path = BASELINE_PATH) -> dict[str, Any]:
    """Load the locked v1.1.0 baseline snapshot and regression floors."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}.")
    return data


def evaluate_civichonors_book(
    *,
    mapper: str = "deterministic",
    min_sentence_length: int = 25,
    top_k: int = 5,
    hops: int = 1,
) -> BookEvaluationResult:
    """Run Map -> Reduce -> Validate -> DuckDB Store -> GraphRAG on the frozen book corpus."""
    doc = load_book_corpus()
    gold = load_gold_annotations()

    nlp_mapper: DeterministicNLPMapper | SpacyNLPMapper
    if mapper == "deterministic":
        nlp_mapper = DeterministicNLPMapper(min_sentence_length=min_sentence_length)
    elif mapper == "spacy":
        nlp_mapper = SpacyNLPMapper(min_sentence_length=min_sentence_length)
    else:
        raise ValueError(f"Unsupported mapper {mapper!r}; choose 'deterministic' or 'spacy'.")

    started_here = not tracemalloc.is_tracing()
    if started_here:
        tracemalloc.start()

    try:
        t0 = time.perf_counter()
        batch = nlp_mapper.map_document(doc)
        t_map = time.perf_counter() - t0

        t1 = time.perf_counter()
        reducer = KnowledgeReducer(conflict_strategy=ConflictStrategy.PRESERVE_DISPUTE)
        layer = reducer.reduce_batches(
            [batch],
            layer_id="civichonors-book",
            layer_name="Civic Honors: The Book",
        )
        t_reduce = time.perf_counter() - t1

        t2 = time.perf_counter()
        report = IntegrityValidator().validate(layer, strict=True)
        t_validate = time.perf_counter() - t2

        queries: list[dict[str, Any]] = list(gold.get("retrieval_queries", []))
        if not queries:
            raise ValueError("Gold annotations contain no retrieval_queries.")

        query_ranks: dict[str, int | None] = {}
        warm_durations: list[float] = []
        warm_query_top1_matches_cold = True

        with tempfile.TemporaryDirectory() as tmp_dir:
            t3 = time.perf_counter()
            store = DuckDBParquetStore(Path(tmp_dir))
            store.save_layer(layer)
            t_store = time.perf_counter() - t3

            retriever = HybridGraphRAGRetriever(store)
            first_query = str(queries[0]["query"])
            t4 = time.perf_counter()
            cold_ctx = retriever.retrieve("civichonors-book", first_query, top_k=top_k, hops=hops)
            t_cold = time.perf_counter() - t4
            cold_top1_id = cold_ctx.results[0].claim.claim_id if cold_ctx.results else None

            for idx_q, q_spec in enumerate(queries):
                q_id = str(q_spec["query_id"])
                q_text = str(q_spec["query"])
                expected_terms = [
                    str(term).lower() for term in q_spec["required_evidence_substrings"]
                ]
                t_q0 = time.perf_counter()
                ctx = retriever.retrieve("civichonors-book", q_text, top_k=top_k, hops=hops)
                warm_durations.append(time.perf_counter() - t_q0)

                if idx_q == 0:
                    warm_top1_id = ctx.results[0].claim.claim_id if ctx.results else None
                    warm_query_top1_matches_cold = warm_top1_id == cold_top1_id

                rank: int | None = None
                for pos, hit in enumerate(ctx.results, start=1):
                    stmt_lower = hit.claim.statement.lower()
                    if all(term in stmt_lower for term in expected_terms):
                        rank = pos
                        break
                query_ranks[q_id] = rank

        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        if started_here and tracemalloc.is_tracing():
            tracemalloc.stop()

    t_warm_avg = sum(warm_durations) / len(warm_durations)
    total_s = t_map + t_reduce + t_validate + t_store + t_cold

    # Entity quality & disambiguation analysis
    pred_types_by_name: dict[str, set[str]] = {}
    pred_entities_by_name: dict[str, list[Any]] = {}
    for ent in layer.entities:
        norm_name = _norm(ent.canonical_name)
        pred_types_by_name.setdefault(norm_name, set()).add(ent.entity_type)
        pred_entities_by_name.setdefault(norm_name, []).append(ent)

    expected_entities: list[dict[str, Any]] = list(gold.get("expected_entities", []))
    total_expected = len(expected_entities)
    name_hits = 0
    typed_hits = 0
    missing_core: list[str] = []
    mistyped_core: list[dict[str, Any]] = []
    alias_expected_count = 0
    alias_hits = 0

    for spec in expected_entities:
        cname = str(spec["canonical_name"])
        norm_cname = _norm(cname)
        expected_type = str(spec["expected_type"])
        expected_aliases = [_norm(str(a)) for a in spec.get("expected_aliases", [])]

        matched_types = pred_types_by_name.get(norm_cname, set())
        if matched_types:
            name_hits += 1
            if expected_type in matched_types:
                typed_hits += 1
            else:
                mistyped_core.append(
                    {
                        "canonical_name": cname,
                        "expected_type": expected_type,
                        "predicted_types": sorted(matched_types),
                    }
                )
        else:
            missing_core.append(cname)

        if expected_aliases:
            alias_expected_count += 1
            ent_matches = pred_entities_by_name.get(norm_cname, [])
            merged_aliases = {_norm(a) for ent in ent_matches for a in ent.aliases}
            if all(alias in merged_aliases for alias in expected_aliases):
                alias_hits += 1

    cross_type_duplicate_names = sorted(
        name for name, types in pred_types_by_name.items() if len(types) > 1
    )

    noise_candidates: list[str] = list(gold.get("known_heading_noise_entities", []))
    heading_noise_fps = [name for name in noise_candidates if _norm(name) in pred_types_by_name]

    # Reference fact retention across reduced claims
    reference_facts: list[dict[str, Any]] = list(gold.get("reference_facts", []))
    retained_fact_count = 0
    missing_facts: list[str] = []
    claim_statements_lower = [c.statement.lower() for c in layer.claims]
    for fact in reference_facts:
        fid = str(fact["fact_id"])
        req_terms = [str(term).lower() for term in fact["required_substrings"]]
        if any(all(term in stmt for term in req_terms) for stmt in claim_statements_lower):
            retained_fact_count += 1
        else:
            missing_facts.append(fid)

    # Graph connectivity & structural ratios
    mentions_count = sum(1 for r in layer.relations if r.relation_type == "MENTIONS")
    co_occurs_count = sum(1 for r in layer.relations if r.relation_type == "CO_OCCURS_WITH")
    semantic_count = len(layer.relations) - mentions_count - co_occurs_count
    connected_claims = {r.source_id for r in layer.relations if r.relation_type == "MENTIONS"}
    grounded_triples = sum(
        1
        for c in layer.claims
        if c.subject_id and c.predicate and (c.object_id or c.object_literal)
    )

    total_nodes = len(layer.entities) + len(layer.claims)
    isolated_nodes = int(report.metrics.get("isolated_nodes", 0))
    claims_before = len(batch.claims)
    claims_after = len(layer.claims)
    compression_ratio = float(
        layer.layer.stats.get(
            "compression_ratio",
            round(1.0 - claims_after / max(1, claims_before), 4),
        )
    )

    num_queries = len(queries)
    hit_at_1 = sum(1 for rank in query_ranks.values() if rank == 1) / num_queries
    hit_at_3 = (
        sum(1 for rank in query_ranks.values() if rank is not None and rank <= 3) / num_queries
    )
    hit_at_5 = (
        sum(1 for rank in query_ranks.values() if rank is not None and rank <= 5) / num_queries
    )
    mrr_at_5 = sum((1.0 / rank) for rank in query_ranks.values() if rank is not None) / num_queries

    metrics = BookGoldenMetrics(
        corpus_id=str(gold.get("corpus_id", "civichonors-book-v1")),
        mapper=mapper,
        min_sentence_length=min_sentence_length,
        source_chars=len(doc.content),
        source_words=len(doc.content.split()),
        content_sha256=doc.content_sha256,
        valid=report.valid,
        validation_errors=len(report.errors),
        validation_warnings=len(report.warnings),
        entities=len(layer.entities),
        claims_before=claims_before,
        claims_after=claims_after,
        compression_ratio=round(compression_ratio, 4),
        relations=len(layer.relations),
        mentions_relations=mentions_count,
        co_occurs_relations=co_occurs_count,
        semantic_relations=semantic_count,
        isolated_nodes=isolated_nodes,
        isolated_node_ratio=round(isolated_nodes / max(1, total_nodes), 4),
        connected_components=int(report.metrics.get("connected_components", 0)),
        edge_density=float(report.metrics.get("edge_density", 0.0)),
        claim_connectivity_rate=round(len(connected_claims) / max(1, claims_after), 4),
        grounded_triple_rate=round(grounded_triples / max(1, claims_after), 4),
        mean_quality_score=float(report.metrics.get("mean_quality_score", 0.0)),
        core_entity_name_recall=round(name_hits / max(1, total_expected), 4),
        core_entity_typed_recall=round(typed_hits / max(1, total_expected), 4),
        core_entity_type_accuracy=round(typed_hits / max(1, name_hits), 4) if name_hits else 0.0,
        alias_merge_recall=(
            round(alias_hits / alias_expected_count, 4) if alias_expected_count else 1.0
        ),
        cross_type_duplicate_count=len(cross_type_duplicate_names),
        heading_noise_fp_count=len(heading_noise_fps),
        heading_noise_fp_rate=round(len(heading_noise_fps) / max(1, len(noise_candidates)), 4),
        core_fact_retention=round(retained_fact_count / max(1, len(reference_facts)), 4),
        retrieval_hit_at_1=round(hit_at_1, 4),
        retrieval_hit_at_3=round(hit_at_3, 4),
        retrieval_hit_at_5=round(hit_at_5, 4),
        retrieval_mrr_at_5=round(mrr_at_5, 4),
        query_ranks=query_ranks,
        missing_core_entities=sorted(missing_core),
        mistyped_core_entities=sorted(mistyped_core, key=lambda item: str(item["canonical_name"])),
        cross_type_duplicate_names=cross_type_duplicate_names,
        missing_reference_facts=sorted(missing_facts),
        map_seconds=round(t_map, 3),
        reduce_seconds=round(t_reduce, 3),
        validate_seconds=round(t_validate, 3),
        store_seconds=round(t_store, 3),
        query_cold_seconds=round(t_cold, 3),
        query_warm_avg_seconds=round(t_warm_avg, 3),
        total_seconds=round(total_s, 3),
        peak_traced_mib=round(peak_bytes / (1024 * 1024), 2),
    )

    return BookEvaluationResult(
        metrics=metrics,
        layer=layer,
        validation_valid=report.valid,
        warm_query_top1_matches_cold=warm_query_top1_matches_cold,
    )


def _is_coverage_active() -> bool:
    """Return True when Python tracing or sys.monitoring coverage instrumentation is active."""
    if sys.gettrace() is not None:
        return True
    monitoring = getattr(sys, "monitoring", None)
    if monitoring is not None:
        cov_id = getattr(monitoring, "COVERAGE_ID", None)
        if cov_id is not None and monitoring.get_tool(cov_id) is not None:
            return True
    return False


def compare_against_baseline(
    current: BookGoldenMetrics,
    baseline: dict[str, Any],
    *,
    enforce_default_floors: bool = True,
    timing_multiplier: float | None = None,
) -> dict[str, Any]:
    """Compare *current* metrics against a locked baseline snapshot and regression floors."""
    cur_dict = current.to_dict()
    base_metrics: dict[str, Any] = dict(baseline.get("metrics", baseline))

    deltas: dict[str, dict[str, Any]] = {}
    for key in _HIGHER_IS_BETTER:
        if key in base_metrics and key in cur_dict:
            base_val = float(base_metrics[key])
            cur_val = float(cur_dict[key])
            diff = round(cur_val - base_val, 4)
            status = "improved" if diff > 0 else ("regressed" if diff < 0 else "unchanged")
            deltas[key] = {
                "baseline": base_val,
                "current": cur_val,
                "delta": diff,
                "status": status,
            }

    for key in _LOWER_IS_BETTER:
        if key in base_metrics and key in cur_dict:
            base_val = float(base_metrics[key])
            cur_val = float(cur_dict[key])
            diff = round(cur_val - base_val, 4)
            status = "improved" if diff < 0 else ("regressed" if diff > 0 else "unchanged")
            deltas[key] = {
                "baseline": base_val,
                "current": cur_val,
                "delta": diff,
                "status": status,
            }

    floors: dict[str, Any] = dict(baseline.get("regression_floors", {}))
    min_floors: dict[str, float] = {k: float(v) for k, v in dict(floors.get("min", {})).items()}
    max_floors: dict[str, float] = {k: float(v) for k, v in dict(floors.get("max", {})).items()}
    if enforce_default_floors:
        for k, v in DEFAULT_REGRESSION_FLOORS["min"].items():
            prev = min_floors.get(k)
            min_floors[k] = float(v) if prev is None else max(prev, float(v))
        for k, v in DEFAULT_REGRESSION_FLOORS["max"].items():
            prev = max_floors.get(k)
            max_floors[k] = float(v) if prev is None else min(prev, float(v))

    floor_failures: list[str] = []

    for metric_name, min_val in min_floors.items():
        if metric_name not in cur_dict:
            floor_failures.append(f"Missing metric {metric_name!r} for min floor check.")
            continue
        cur_num = float(cur_dict[metric_name])
        if cur_num < float(min_val):
            floor_failures.append(f"{metric_name}={cur_num} < min floor {min_val}")

    mult = (
        timing_multiplier
        if timing_multiplier is not None
        else (3.0 if _is_coverage_active() else 1.0)
    )
    for metric_name, max_val in max_floors.items():
        if metric_name not in cur_dict:
            floor_failures.append(f"Missing metric {metric_name!r} for max floor check.")
            continue
        cur_num = float(cur_dict[metric_name])
        effective_max = float(max_val) * mult if metric_name == "total_seconds" else float(max_val)
        if cur_num > effective_max:
            floor_failures.append(f"{metric_name}={cur_num} > max ceiling {effective_max}")

    return {
        "baseline_version": baseline.get("baseline_version", "unknown"),
        "passed_floors": len(floor_failures) == 0,
        "floor_failures": floor_failures,
        "deltas": deltas,
    }


def _build_baseline_payload(metrics: BookGoldenMetrics) -> dict[str, Any]:
    return {
        "baseline_version": "1.1.0",
        "corpus_id": metrics.corpus_id,
        "source_url": "https://www.civichonors.com/p/the-book",
        "metrics": metrics.to_dict(),
        "regression_floors": DEFAULT_REGRESSION_FLOORS,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the offline Civic Honors book golden evaluation benchmark."
    )
    parser.add_argument(
        "--mapper",
        default="deterministic",
        choices=("deterministic", "spacy"),
        help="Mapper backend to evaluate.",
    )
    parser.add_argument(
        "--min-sentence-length",
        type=int,
        default=25,
        help="Minimum sentence character length passed to the NLP mapper.",
    )
    parser.add_argument(
        "--no-compare-baseline",
        action="store_true",
        help="Skip comparing metrics against baseline_v1_1_0.json.",
    )
    parser.add_argument(
        "--strict-regression",
        action="store_true",
        help="Exit non-zero if any regression floor fails.",
    )
    parser.add_argument(
        "--write-baseline",
        type=Path,
        default=None,
        help="Optional path to write a baseline JSON snapshot from this run.",
    )
    args = parser.parse_args()

    result = evaluate_civichonors_book(
        mapper=args.mapper,
        min_sentence_length=args.min_sentence_length,
    )
    report: dict[str, Any] = {"metrics": result.metrics.to_dict()}

    if args.write_baseline is not None:
        args.write_baseline.parent.mkdir(parents=True, exist_ok=True)
        payload = _build_baseline_payload(result.metrics)
        args.write_baseline.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    comparison: dict[str, Any] | None = None
    if not args.no_compare_baseline and BASELINE_PATH.is_file():
        comparison = compare_against_baseline(result.metrics, load_baseline())
        report["baseline_comparison"] = comparison

    print(json.dumps(report, indent=2))

    if not result.validation_valid:
        return 1
    if args.strict_regression and comparison is not None and not comparison["passed_floors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
