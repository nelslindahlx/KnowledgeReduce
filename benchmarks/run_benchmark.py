"""Offline golden-corpus quality evaluation and scaling benchmark for KnowledgeReduce."""

from __future__ import annotations

import argparse
import json
import resource
import tempfile
import time
import tracemalloc
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from knowledgereduce.map import DeterministicNLPMapper
from knowledgereduce.models import (
    Claim,
    ConflictStrategy,
    Entity,
    Evidence,
    MappedBatch,
    Relation,
    ReliabilityRating,
    SourceDocument,
    SourceType,
)
from knowledgereduce.query import HybridGraphRAGRetriever
from knowledgereduce.reduce import KnowledgeReducer
from knowledgereduce.storage import DuckDBParquetStore


@dataclass(frozen=True)
class GoldenBenchmarkMetrics:
    """Quality metrics computed on the 50-document frozen golden corpus."""

    documents: int
    entity_precision: float
    entity_recall: float
    entity_f1: float
    relation_connectivity_rate: float
    bcubed_precision: float
    bcubed_recall: float
    bcubed_f1: float
    information_retention: float
    conflict_detection_recall: float
    conflict_resolution_accuracy: float


def _norm(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _bcubed_scores(
    predicted_clusters: list[list[str]],
    gold_labels: dict[str, str],
) -> tuple[float, float, float]:
    """Compute B-cubed precision, recall, and F1 over clustered item IDs."""
    # Evaluate over original claim_ids (including merged_from) present in gold_labels.
    pred_map: dict[str, set[str]] = {}
    for cluster in predicted_clusters:
        valid = {cid for cid in cluster if cid in gold_labels}
        for cid in valid:
            pred_map[cid] = valid

    gold_groups: dict[str, set[str]] = defaultdict(set)
    for cid, label in gold_labels.items():
        if cid in pred_map:
            gold_groups[label].add(cid)

    if not pred_map:
        return 0.0, 0.0, 0.0

    precisions: list[float] = []
    recalls: list[float] = []
    for cid, p_cluster in pred_map.items():
        g_cluster = gold_groups[gold_labels[cid]]
        overlap = len(p_cluster & g_cluster)
        precisions.append(overlap / len(p_cluster))
        recalls.append(overlap / len(g_cluster))

    b_prec = sum(precisions) / len(precisions)
    b_rec = sum(recalls) / len(recalls)
    b_f1 = (2 * b_prec * b_rec / (b_prec + b_rec)) if (b_prec + b_rec) > 0 else 0.0
    return round(b_prec, 4), round(b_rec, 4), round(b_f1, 4)


def run_golden_evaluation() -> GoldenBenchmarkMetrics:
    """Evaluate entity/relation extraction, B-cubed dedup, and conflict resolution on 50 docs."""
    # 50 frozen deterministic documents across CivicHonors + multi-source domain themes:
    # - 15 distinct factual themes x 3 phrasing/punctuation variants = 45 docs (duplicate clusters)
    # - 5 contradicting authoritative vs blog variants = 5 docs (planted conflicts)
    themes: list[tuple[str, list[str], tuple[str, str, str] | None]] = [
        (
            "civic_pub",
            [
                "Civic Honors was published in 2006 to advance local student civic engagement.",
                "Civic Honors was published in 2006 to advance local student civic engagement!",
                "Civic Honors was published in 2006 to foster local student civic engagement.",
            ],
            ("Civic Honors", "PUBLISHED_IN", "2006"),
        ),
        (
            "ku_origin",
            [
                "Dr. Nels Lindahl studied at University of Kansas during the spring of 2002.",
                "Nels Lindahl studied at University of Kansas during the spring of 2002.",
                "Dr. Nels Lindahl studied at University of Kansas in the spring of 2002.",
            ],
            ("Nels Lindahl", "STUDIED_AT", "University of Kansas"),
        ),
        (
            "frederickson",
            [
                "Dr. H. George Frederickson taught Concepts of Civil Society at University of Kansas.",
                "Dr. H. George Frederickson taught Concepts of Civil Society at the University of Kansas.",
                "Prof. H. George Frederickson taught Concepts of Civil Society at University of Kansas.",
            ],
            None,
        ),
        (
            "denver_loc",
            [
                "Dr. Nels Lindahl is based in Denver, Colorado for civic research.",
                "Nels Lindahl is based in Denver, Colorado for civic research.",
                "Dr. Nels Lindahl is based in Denver, Colorado conducting civic research.",
            ],
            ("Nels Lindahl", "IS_BASED_IN", "Denver, Colorado"),
        ),
        (
            "davis_longoria",
            [
                "Dr. Raymond Davis and Dr. Thomas Longoria emphasized community collaboration.",
                "Dr. Raymond Davis and Dr. Thomas Longoria emphasized public community collaboration.",
                "Raymond Davis and Thomas Longoria emphasized community collaboration.",
            ],
            None,
        ),
        (
            "kr_framework",
            [
                "KnowledgeReduce founded in 2023 extends MapReduce for stackable knowledge graphs.",
                "KnowledgeReduce founded in 2023 extends MapReduce for building stackable knowledge graphs.",
                "KnowledgeReduce founded in 2023 extends MapReduce to build stackable knowledge graphs.",
            ],
            ("KnowledgeReduce", "FOUNDED_IN", "2023"),
        ),
        (
            "parquet_storage",
            [
                "DuckDB and Apache Parquet provide columnar persistence for immutable knowledge layers.",
                "DuckDB and Apache Parquet provide fast columnar persistence for immutable knowledge layers.",
                "DuckDB and Apache Parquet provide columnar persistence for immutable knowledge graphs.",
            ],
            None,
        ),
        (
            "civic_founded",
            [
                "Nels Lindahl founded Civic Honors to connect public administration and student service.",
                "Dr. Nels Lindahl founded Civic Honors to connect public administration and student service.",
                "Nels Lindahl founded Civic Honors connecting public administration and student service.",
            ],
            ("Nels Lindahl", "FOUNDED", "Civic Honors"),
        ),
        (
            "ku_lawrence",
            [
                "University of Kansas is located in Lawrence, Kansas.",
                "The University of Kansas is located in Lawrence, Kansas.",
                "University of Kansas is located in Lawrence, Kansas!",
            ],
            ("University of Kansas", "IS_LOCATED_IN", "Lawrence, Kansas"),
        ),
        (
            "stackable_dag",
            [
                "StackManager composes immutable layers in a directed acyclic lineage graph.",
                "StackManager composes immutable layers within a directed acyclic lineage graph.",
                "StackManager composes immutable layers using a directed acyclic lineage graph.",
            ],
            None,
        ),
        (
            "ssrf_guard",
            [
                "AsyncWebCrawler blocks private loopback IP ranges before opening HTTP sockets.",
                "AsyncWebCrawler blocks private loopback IP addresses before opening HTTP sockets.",
                "AsyncWebCrawler blocks private and loopback IP ranges before opening HTTP sockets.",
            ],
            None,
        ),
        (
            "preserve_dispute",
            [
                "PreserveDispute attaches CONTRADICTS edges while keeping dissenting source evidence.",
                "PreserveDispute attaches CONTRADICTS edges while preserving dissenting source evidence.",
                "PreserveDispute creates CONTRADICTS edges while keeping dissenting source evidence.",
            ],
            None,
        ),
        (
            "mcp_bridge",
            [
                "Antigravity submits structured batches into KnowledgeReduce through stdio MCP tools.",
                "Antigravity submits structured batches to KnowledgeReduce through stdio MCP tools.",
                "Antigravity injects structured batches into KnowledgeReduce through stdio MCP tools.",
            ],
            None,
        ),
        (
            "sharded_jsonl",
            [
                "Sharded JSONL exports preserve cross-shard relations alongside a manifest file.",
                "Sharded JSONL exports preserve all cross-shard relations alongside a manifest file.",
                "Sharded JSONL exports retain cross-shard relations alongside a manifest file.",
            ],
            None,
        ),
        (
            "graphrag_hybrid",
            [
                "HybridGraphRAGRetriever combines lexical overlap with semantic vectors and graph hops.",
                "HybridGraphRAGRetriever blends lexical overlap with semantic vectors and graph hops.",
                "HybridGraphRAGRetriever combines lexical overlap, semantic vectors, and graph hops.",
            ],
            None,
        ),
    ]

    conflict_docs: list[tuple[str, str, str, str, float]] = [
        (
            "cf_civic_pub",
            "civic_pub_conflict",
            "Civic Honors was published in 2020 to advance local student civic engagement.",
            "2006",
            0.45,
        ),
        (
            "cf_kr_founded",
            "kr_founded_conflict",
            "KnowledgeReduce founded in 2025 extends MapReduce for stackable knowledge graphs.",
            "2023",
            0.40,
        ),
        (
            "cf_ku_loc",
            "ku_loc_conflict",
            "University of Kansas is located in Topeka, Kansas.",
            "Lawrence, Kansas",
            0.40,
        ),
        (
            "cf_denver",
            "denver_conflict",
            "Dr. Nels Lindahl is based in Boulder, Colorado for civic research.",
            "Denver, Colorado",
            0.40,
        ),
        (
            "cf_ku_year",
            "ku_year_conflict",
            "Dr. Nels Lindahl studied at University of Kansas during the spring of 2004.",
            "2002",
            0.40,
        ),
    ]

    mapper = DeterministicNLPMapper(min_sentence_length=20)
    batches: list[MappedBatch] = []
    gold_cluster_labels: dict[str, str] = {}
    gold_entities = {
        "civic honors",
        "nels lindahl",
        "university of kansas",
        "h. george frederickson",
        "concepts of civil society",
        "denver",
        "colorado",
        "raymond davis",
        "thomas longoria",
        "knowledgereduce",
        "mapreduce",
        "duckdb",
        "apache parquet",
        "lawrence",
        "kansas",
        "stackmanager",
        "asyncwebcrawler",
        "preservedispute",
        "antigravity",
        "hybridgraphragretriever",
    }

    doc_counter = 0
    for theme_id, variants, _triple in themes:
        for v_idx, text in enumerate(variants):
            doc_counter += 1
            src = SourceDocument(
                source_id=f"gold_{theme_id}_{v_idx}",
                uri=f"https://civichonors.com/doc/{doc_counter}",
                source_type=SourceType.WEB,
                title=f"Doc {doc_counter}",
                content=text,
                trust_weight=0.9 if v_idx == 0 else 0.75,
            )
            batch = mapper.map_document(src)
            for clm in batch.claims:
                gold_cluster_labels[clm.claim_id] = theme_id
            batches.append(batch)

    expected_conflict_winners: set[str] = set()
    for cid, theme_key, text, expected_winner, trust in conflict_docs:
        doc_counter += 1
        src = SourceDocument(
            source_id=f"gold_{cid}",
            uri=f"https://blog.example/{doc_counter}",
            source_type=SourceType.WEB,
            title=f"Conflict Doc {doc_counter}",
            content=text,
            trust_weight=trust,
        )
        batch = mapper.map_document(src)
        for clm in batch.claims:
            gold_cluster_labels[clm.claim_id] = theme_key
        expected_conflict_winners.add(expected_winner)
        batches.append(batch)

    reducer = KnowledgeReducer(
        lexical_threshold=0.80,
        semantic_threshold=0.78,
        conflict_strategy=ConflictStrategy.PRESERVE_DISPUTE,
    )
    reduced = reducer.reduce_batches(
        batches,
        layer_id="golden-50",
        layer_name="Golden 50-Doc Evaluation",
    )

    predicted_names = {_norm(e.canonical_name) for e in reduced.entities}
    matched_entities = predicted_names & gold_entities
    ent_prec = len(matched_entities) / len(predicted_names) if predicted_names else 0.0
    ent_rec = len(matched_entities) / len(gold_entities)
    ent_f1 = (2 * ent_prec * ent_rec / (ent_prec + ent_rec)) if (ent_prec + ent_rec) > 0 else 0.0

    pred_clusters: list[list[str]] = [[clm.claim_id, *clm.merged_from] for clm in reduced.claims]
    b_prec, b_rec, b_f1 = _bcubed_scores(pred_clusters, gold_cluster_labels)

    distinct_gold_themes = set(gold_cluster_labels.values())
    covered_themes = {
        gold_cluster_labels[clm.claim_id]
        for clm in reduced.claims
        if clm.claim_id in gold_cluster_labels
    }
    retention = len(covered_themes) / len(distinct_gold_themes)

    connected_claims = {r.source_id for r in reduced.relations if r.relation_type == "MENTIONS"}
    rel_conn = len(connected_claims) / len(reduced.claims) if reduced.claims else 0.0

    detected_winners = {
        str(cf.winning_value) for cf in reduced.conflicts if cf.winning_value is not None
    }
    conflict_hits = sum(
        1
        for exp in expected_conflict_winners
        if any(exp.lower() in w.lower() for w in detected_winners)
    )
    conflict_recall = len(reduced.conflicts) / len(conflict_docs)
    conflict_acc = conflict_hits / len(conflict_docs)

    return GoldenBenchmarkMetrics(
        documents=doc_counter,
        entity_precision=round(ent_prec, 4),
        entity_recall=round(ent_rec, 4),
        entity_f1=round(ent_f1, 4),
        relation_connectivity_rate=round(rel_conn, 4),
        bcubed_precision=b_prec,
        bcubed_recall=b_rec,
        bcubed_f1=b_f1,
        information_retention=round(retention, 4),
        conflict_detection_recall=round(min(1.0, conflict_recall), 4),
        conflict_resolution_accuracy=round(conflict_acc, 4),
    )


def run_scaling_benchmark(num_facts: int) -> dict[str, float | int]:
    """Benchmark reduction, DuckDB/Parquet write, and GraphRAG retrieval at *num_facts* scale."""
    entities_pool = [
        Entity(
            entity_id=f"ent_{i}",
            canonical_name=f"Civic Entity {i}",
            entity_type="ORG" if i % 2 == 0 else "CONCEPT",
            evidence=[Evidence(source_id="scale_src", excerpt=f"Entity {i}")],
        )
        for i in range(max(20, num_facts // 25))
    ]
    source_doc = SourceDocument(
        source_id="scale_src",
        uri="https://civichonors.com/scale",
        source_type=SourceType.JSON,
        content="synthetic scaling benchmark",
        trust_weight=0.85,
    )

    claims: list[Claim] = []
    relations: list[Relation] = []
    unique_count = int(num_facts * 0.7)
    for i in range(num_facts):
        base_idx = i if i < unique_count else (i % unique_count)
        ent = entities_pool[base_idx % len(entities_pool)]
        cid = f"clm_{i}"
        stmt = (
            f"Civic Entity {base_idx % len(entities_pool)} milestone record {base_idx} "
            f"documents community engagement program details."
        )
        claims.append(
            Claim(
                claim_id=cid,
                statement=stmt,
                category="Benchmark",
                tags=["scale", f"bucket_{base_idx % 10}"],
                reliability=ReliabilityRating.LIKELY_TRUE,
                source_id="scale_src",
                evidence=[Evidence(source_id="scale_src", excerpt=stmt)],
            )
        )
        relations.append(
            Relation(
                relation_id=f"rel_{i}",
                source_id=cid,
                target_id=ent.entity_id,
                relation_type="MENTIONS",
                confidence=0.9,
            )
        )

    batch = MappedBatch(
        source_document=source_doc,
        entities=entities_pool,
        claims=claims,
        relations=relations,
    )

    tracemalloc.start()
    t0 = time.perf_counter()
    reducer = KnowledgeReducer(conflict_strategy=ConflictStrategy.PRESERVE_DISPUTE)
    reduced = reducer.reduce_batches(
        [batch],
        layer_id=f"scale-{num_facts}",
        layer_name=f"Scale {num_facts}",
    )
    t_reduce = time.perf_counter() - t0

    with tempfile.TemporaryDirectory() as tmp:
        t1 = time.perf_counter()
        store = DuckDBParquetStore(Path(tmp))
        store.save_layer(reduced)
        t_store = time.perf_counter() - t1

        retriever = HybridGraphRAGRetriever(store)
        t2 = time.perf_counter()
        ctx_cold = retriever.retrieve(
            f"scale-{num_facts}",
            "community engagement milestone record 10",
            top_k=5,
            hops=1,
        )
        t_cold = time.perf_counter() - t2
        assert len(ctx_cold.results) > 0

        t3 = time.perf_counter()
        ctx_warm = retriever.retrieve(
            f"scale-{num_facts}",
            "community engagement milestone record 10",
            top_k=5,
            hops=1,
        )
        t_warm = time.perf_counter() - t3
        assert len(ctx_warm.results) > 0
        assert ctx_warm.results[0].claim.claim_id == ctx_cold.results[0].claim.claim_id

    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    total_s = t_reduce + t_store + t_cold
    rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
    # On macOS ru_maxrss is in bytes; on Linux it's in KiB. Normalize heuristically for display.
    if rss_mb < 10.0:
        rss_mb *= 1024.0

    return {
        "input_facts": num_facts,
        "reduced_claims": len(reduced.claims),
        "relations": len(reduced.relations),
        "reduce_seconds": round(t_reduce, 3),
        "store_seconds": round(t_store, 3),
        "query_seconds": round(t_cold, 3),
        "query_cold_seconds": round(t_cold, 3),
        "query_warm_seconds": round(t_warm, 3),
        "total_seconds": round(total_s, 3),
        "peak_traced_mib": round(peak_bytes / (1024 * 1024), 2),
        "max_rss_mb": round(rss_mb, 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="KnowledgeReduce golden & scaling benchmark.")
    parser.add_argument(
        "--scale",
        nargs="*",
        type=int,
        default=[1000, 10000],
        help="Fact counts for scaling benchmark.",
    )
    args = parser.parse_args()

    golden = run_golden_evaluation()
    scaling = [run_scaling_benchmark(n) for n in args.scale]

    report = {
        "golden_50_docs": golden.__dict__,
        "scaling": scaling,
    }
    print(json.dumps(report, indent=2))

    # Enforce benchmark quality & latency SLAs
    assert golden.bcubed_f1 >= 0.85, f"B-cubed F1 below 0.85: {golden.bcubed_f1}"
    assert golden.information_retention >= 0.90, (
        f"Information retention below 0.90: {golden.information_retention}"
    )
    assert golden.conflict_detection_recall >= 0.80, (
        f"Conflict recall below 0.80: {golden.conflict_detection_recall}"
    )
    for row in scaling:
        if int(row["input_facts"]) <= 10000:
            assert float(row["total_seconds"]) < 60.0, f"10K scaling SLA exceeded: {row}"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
