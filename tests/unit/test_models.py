"""Unit tests for KnowledgeReduce Pydantic domain models and enums."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from knowledgereduce.models import (
    Claim,
    ConflictRecord,
    ConflictStrategy,
    Entity,
    Evidence,
    KnowledgeLayer,
    LayerTier,
    ReliabilityRating,
    SourceDocument,
    SourceType,
)


def test_reliability_rating_ordinal_ordering() -> None:
    assert (
        ReliabilityRating.UNKNOWN
        < ReliabilityRating.UNVERIFIED
        < ReliabilityRating.POSSIBLY_TRUE
        < ReliabilityRating.LIKELY_TRUE
        < ReliabilityRating.VERIFIED
    )


def test_source_document_hashes_and_utc_normalization() -> None:
    naive = datetime(2024, 6, 14, 12, 30, 0)
    offset = timezone(timedelta(hours=-6))
    pub = datetime(2020, 6, 14, 8, 0, 0, tzinfo=offset)

    doc = SourceDocument(
        source_id="src-1",
        uri="https://civichonors.com/",
        source_type=SourceType.WEB,
        title="Civic Honors",
        published_at=pub,
        fetched_at=naive,
        content="Graduation with Civic Honors",
        trust_weight=0.9,
    )
    assert doc.fetched_at.tzinfo == UTC
    assert doc.published_at is not None
    assert doc.published_at.tzinfo == UTC
    assert doc.published_at.hour == 14
    assert len(doc.content_sha256) == 64


def test_claim_schema_quality_score_and_roundtrip() -> None:
    claim = Claim(
        claim_id="c1",
        statement="Civic Honors began at the University of Kansas in 2002.",
        category="History",
        tags=["civic", "ku", "civic", "  education  "],
        reliability=ReliabilityRating.VERIFIED,
        source_id="src-1",
        source_title="Civic Honors",
        author_creator="Dr. Nels Lindahl",
        url_reference="https://civichonors.com/",
        usage_count=5,
        confidence=0.9,
        evidence=[Evidence(source_id="src-1", excerpt="spring semester of 2002")],
    )
    assert claim.tags == ["civic", "ku", "education"]
    # 50.0 (verified) + 22.5 (0.9 * 25) + 7.5 (5 * 1.5) + 2.0 (1 * 2) = 82.0
    assert claim.quality_score == 82.0

    dumped = claim.model_dump(mode="json")
    assert dumped["quality_score"] == 82.0
    restored = Claim.model_validate(dumped)
    assert restored == claim


def test_claim_rejects_unknown_extra_fields() -> None:
    with pytest.raises(ValidationError):
        Claim(claim_id="c1", statement="Valid statement", bogus_field="nope")  # type: ignore[call-arg]


def test_evidence_invalid_char_span() -> None:
    with pytest.raises(ValidationError, match="char_span"):
        Evidence(source_id="s1", char_span=(10, 5))


def test_entity_deduplicates_aliases() -> None:
    entity = Entity(
        entity_id="ent-ku",
        canonical_name="University of Kansas",
        entity_type="ORG",
        aliases=["KU", "University of Kansas", "KU", "  Kansas University "],
    )
    assert entity.aliases == ["KU", "University of Kansas", "Kansas University"]


def test_knowledge_layer_rejects_unsafe_layer_ids() -> None:
    for bad in ["../escape", "bad/slash", "has space", ".hidden", ""]:
        with pytest.raises(ValidationError):
            KnowledgeLayer(layer_id=bad, name="Bad")

    good = KnowledgeLayer(layer_id="civic_honors.v1-0", name="Good", tier=LayerTier.REDUCED)
    assert good.layer_id == "civic_honors.v1-0"


def test_conflict_record_defaults() -> None:
    cf = ConflictRecord(
        conflict_id="cf-1",
        target_type="claim",
        target_key="subj:pub_year",
        candidates=[{"value": "2006"}, {"value": "2020"}],
        resolution_strategy=ConflictStrategy.PRESERVE_DISPUTE,
        winning_value="2006",
    )
    assert cf.needs_review is True
    assert cf.resolved_at.tzinfo == UTC
