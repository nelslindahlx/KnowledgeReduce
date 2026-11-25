"""Golden regression tests for offline multi-source incremental & stacked evaluation."""

from __future__ import annotations

import pytest

from benchmarks.multisource_stack_benchmark import (
    MultiSourceStackResult,
    evaluate_multisource_stack,
)
from knowledgereduce.reduce import IntegrityValidator


@pytest.fixture(scope="module")
def multisource_eval() -> MultiSourceStackResult:
    """Evaluate the deterministic multi-source stacked scenario once per test module."""
    return evaluate_multisource_stack()


def test_multisource_incremental_lineage_and_prewarmed_embeddings(
    multisource_eval: MultiSourceStackResult,
) -> None:
    m = multisource_eval.metrics
    assert m.base_sources == 2
    assert m.delta_sources == 2
    assert m.skipped_unchanged == 1
    assert multisource_eval.delta_parent_layer_ids == ["ms-base"]
    assert multisource_eval.stacked_parent_layer_ids == ["ms-base", "ms-delta", "ms-disputed"]
    assert all(multisource_eval.embeddings_present.values())


def test_multisource_strict_integrity_conflicts_and_retrieval(
    multisource_eval: MultiSourceStackResult,
) -> None:
    report = IntegrityValidator().validate(multisource_eval.stacked_layer, strict=True)
    assert report.valid is True
    assert report.errors == []
    assert report.warnings == []

    m = multisource_eval.metrics
    assert m.isolated_entities == 0
    assert m.conflicts_detected >= 3
    assert m.contradicts_edges >= 3
    assert m.conflict_detection_recall == 1.0
    assert m.conflict_resolution_accuracy == 1.0
    assert m.retrieval_hit_at_1 == 1.0
    assert m.disputed_conflict_surfacing_rate == 1.0
    assert multisource_eval.passed_floors is True, multisource_eval.floor_failures


def test_multisource_analytics_markdown_and_reproducibility(
    multisource_eval: MultiSourceStackResult,
) -> None:
    analytics = multisource_eval.analytics
    assert analytics["node_count"] > 0
    assert analytics["edge_count"] > 0
    assert analytics["community_count"] >= 1
    assert len(analytics["central_nodes"]) >= 1

    md = multisource_eval.markdown_brief
    assert "## Layer Summary" in md
    assert "## Conflicts" in md
    assert "## Sources" in md
    assert "`Open`" in md
    assert "/Users/" not in md

    reproduced = evaluate_multisource_stack()
    assert [(c.claim_id, c.statement) for c in reproduced.stacked_layer.claims] == [
        (c.claim_id, c.statement) for c in multisource_eval.stacked_layer.claims
    ]
    assert [(cf.conflict_id, cf.winning_value) for cf in reproduced.stacked_layer.conflicts] == [
        (cf.conflict_id, cf.winning_value) for cf in multisource_eval.stacked_layer.conflicts
    ]
