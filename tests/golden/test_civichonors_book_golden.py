"""Golden regression tests for the offline 'Civic Honors: The Book' benchmark corpus."""

from __future__ import annotations

import dataclasses

import pytest

from benchmarks.civichonors_book_benchmark import (
    SOURCE_DOC_PATH,
    BookEvaluationResult,
    compare_against_baseline,
    evaluate_civichonors_book,
    load_baseline,
    load_book_corpus,
    load_gold_annotations,
)
from knowledgereduce.map import DeterministicNLPMapper
from knowledgereduce.models import ConflictStrategy
from knowledgereduce.reduce import IntegrityValidator, KnowledgeReducer


@pytest.fixture(scope="module")
def book_eval() -> BookEvaluationResult:
    """Evaluate the frozen Civic Honors book corpus once per test module."""
    return evaluate_civichonors_book()


def test_golden_corpus_snapshot_integrity() -> None:
    raw_text = SOURCE_DOC_PATH.read_text(encoding="utf-8")
    assert "/Users/" not in raw_text
    assert "file://" not in raw_text

    doc = load_book_corpus()
    gold = load_gold_annotations()
    assert doc.uri == gold["source_url"]
    assert doc.content_sha256 == gold["content_sha256"]
    assert doc.title == "The Book - by Dr. Nels Lindahl - Civic Honors"
    assert doc.author == "Dr. Nels Lindahl"
    assert len(doc.content) == 139_596
    assert len(doc.content.split()) == 21_765


def test_civichonors_book_strict_integrity_and_graph_invariants(
    book_eval: BookEvaluationResult,
) -> None:
    layer = book_eval.layer
    report = IntegrityValidator().validate(layer, strict=True)
    assert report.valid is True
    assert report.errors == []
    assert report.warnings == []

    # Every extracted entity must participate in at least one graph relation.
    connected_nodes = {r.source_id for r in layer.relations} | {
        r.target_id for r in layer.relations
    }
    assert {e.entity_id for e in layer.entities}.issubset(connected_nodes)
    assert book_eval.metrics.semantic_relations >= 0


def test_civichonors_book_meets_v1_1_0_baseline_floors(
    book_eval: BookEvaluationResult,
) -> None:
    baseline = load_baseline()
    comparison = compare_against_baseline(book_eval.metrics, baseline)
    assert comparison["baseline_version"] == "1.1.0"
    assert comparison["passed_floors"] is True, comparison["floor_failures"]
    assert comparison["floor_failures"] == []
    assert book_eval.warm_query_top1_matches_cold is True


def test_civichonors_book_deterministic_reproducibility(
    book_eval: BookEvaluationResult,
) -> None:
    doc = load_book_corpus()
    batch = DeterministicNLPMapper(min_sentence_length=25).map_document(doc)
    reproduced = KnowledgeReducer(
        conflict_strategy=ConflictStrategy.PRESERVE_DISPUTE
    ).reduce_batches(
        [batch],
        layer_id="civichonors-book",
        layer_name="Civic Honors: The Book",
    )

    first = book_eval.layer
    assert [
        (e.entity_id, e.canonical_name, e.entity_type, tuple(e.aliases))
        for e in reproduced.entities
    ] == [(e.entity_id, e.canonical_name, e.entity_type, tuple(e.aliases)) for e in first.entities]
    assert [(c.claim_id, c.statement, tuple(c.merged_from)) for c in reproduced.claims] == [
        (c.claim_id, c.statement, tuple(c.merged_from)) for c in first.claims
    ]
    assert sorted(
        (r.source_id, r.relation_type, r.target_id) for r in reproduced.relations
    ) == sorted((r.source_id, r.relation_type, r.target_id) for r in first.relations)


def test_baseline_comparison_detects_regressions_and_improvements(
    book_eval: BookEvaluationResult,
) -> None:
    baseline = load_baseline()

    improved = dataclasses.replace(
        book_eval.metrics,
        core_entity_typed_recall=0.95,
        heading_noise_fp_count=0,
        heading_noise_fp_rate=0.0,
    )
    imp_cmp = compare_against_baseline(improved, baseline)
    assert imp_cmp["passed_floors"] is True
    assert imp_cmp["deltas"]["core_entity_typed_recall"]["status"] == "improved"
    assert imp_cmp["deltas"]["heading_noise_fp_count"]["status"] == "improved"

    regressed = dataclasses.replace(
        book_eval.metrics,
        core_fact_retention=0.50,
        heading_noise_fp_count=20,
    )
    reg_cmp = compare_against_baseline(regressed, baseline)
    assert reg_cmp["passed_floors"] is False
    assert reg_cmp["deltas"]["core_fact_retention"]["status"] == "regressed"
    assert reg_cmp["deltas"]["heading_noise_fp_count"]["status"] == "regressed"
    assert any("core_fact_retention" in msg for msg in reg_cmp["floor_failures"])
    assert any("heading_noise_fp_count" in msg for msg in reg_cmp["floor_failures"])
