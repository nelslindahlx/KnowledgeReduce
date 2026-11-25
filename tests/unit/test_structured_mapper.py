"""Dedicated branch coverage tests for StructuredMapper and mapping rules."""

from __future__ import annotations

import json

import pytest

from knowledgereduce.map import (
    EntityMappingRule,
    RelationMappingRule,
    StructuredMapper,
    StructuredMappingConfig,
)
from knowledgereduce.map.structured import _parse_reliability, _row_object_is_entity
from knowledgereduce.models import ExtractionError, ReliabilityRating, SourceDocument, SourceType


def test_structured_helpers_reliability_and_object_entity_flags() -> None:
    assert _parse_reliability(3, 0.2) == ReliabilityRating.LIKELY_TRUE
    assert _parse_reliability(99, 0.2) == ReliabilityRating.VERIFIED
    assert _parse_reliability(-5, 0.9) == ReliabilityRating.UNKNOWN
    assert _parse_reliability("2", 0.2) == ReliabilityRating.POSSIBLY_TRUE
    assert _parse_reliability("verified", 0.2) == ReliabilityRating.VERIFIED
    assert _parse_reliability("unrecognized", 0.70) == ReliabilityRating.LIKELY_TRUE
    assert _parse_reliability(None, 0.45) == ReliabilityRating.POSSIBLY_TRUE
    assert _parse_reliability(None, 0.10) == ReliabilityRating.UNVERIFIED

    assert _row_object_is_entity({}) is True
    assert _row_object_is_entity({"object_is_entity": False}) is False
    assert _row_object_is_entity({"object_is_entity": 0}) is False
    assert _row_object_is_entity({"object_is_entity": "FALSE"}) is False
    assert _row_object_is_entity({"object_is_entity": "0"}) is False
    assert _row_object_is_entity({"object_is_entity": ["truthy"]}) is True


def test_structured_mapper_explicit_rules_templates_and_errors() -> None:
    # Empty records & single JSON dict parsing + map_documents
    empty_doc = SourceDocument(
        source_id="empty-json",
        uri="https://example.org/empty.json",
        source_type=SourceType.JSON,
        content="   ",
    )
    single_dict_doc = SourceDocument(
        source_id="dict-json",
        uri="https://example.org/item.json",
        source_type=SourceType.JSON,
        content=json.dumps(
            {
                "subject": "University of Kansas",
                "predicate": "LOCATED_IN",
                "object": "Lawrence, Kansas",
                "statement": "University of Kansas is in Lawrence, Kansas.",
            }
        ),
        trust_weight=0.90,
    )
    batches = StructuredMapper().map_documents([empty_doc, single_dict_doc])
    assert len(batches) == 2
    assert batches[0].claims == []
    assert len(batches[1].claims) == 1
    assert batches[1].relations[0].relation_type == "MENTIONS" or any(
        r.relation_type == "LOCATED_IN" for r in batches[1].relations
    )

    # Bad JSON & unsupported SourceType errors
    bad_json = empty_doc.model_copy(update={"source_id": "bad", "content": "{not valid"})
    with pytest.raises(ExtractionError, match="Failed to parse structured JSON"):
        StructuredMapper().map_document(bad_json)

    bad_type = empty_doc.model_copy(
        update={"source_id": "bad-type", "source_type": SourceType.WEB, "content": "<html></html>"}
    )
    with pytest.raises(ExtractionError, match="requires CSV, JSON, or JSONL"):
        StructuredMapper().map_document(bad_type)

    # Explicit config exercising id_field, aliases, attributes, duplicate entity merge,
    # relation_type_field, statement_template, fallback key=val, and skipped rows.
    cfg = StructuredMappingConfig(
        entities=[
            EntityMappingRule(
                name_field="org",
                entity_type="ORG",
                id_field="org_id",
                alias_fields=["org_alias"],
                attribute_fields=["city"],
            )
        ],
        relations=[
            RelationMappingRule(
                source_name_field="org",
                source_type="ORG",
                target_name_field="partner",
                target_type="CONCEPT",
                relation_type_field="rel_kind",
            )
        ],
        statement_template="{org} collaborates with {partner}",
        subject_field="org",
        predicate_field="rel_kind",
        object_field="partner",
    )
    records = [
        {
            "org": "University of Kansas",
            "org_id": "ent-ku",
            "org_alias": "KU",
            "city": "Lawrence",
            "partner": "Civic Honors",
            "rel_kind": "supports",
        },
        {
            "org": "University of Kansas",
            "org_id": "ent-ku",
            "org_alias": "Kansas Univ",
            "city": "Lawrence, KS",
            "partner": "Public Service",
            "rel_kind": "fosters",
        },
        {
            "org": "",
            "partner": "",
        },
    ]
    explicit_doc = SourceDocument(
        source_id="explicit-json",
        uri="https://example.org/explicit.json",
        source_type=SourceType.JSON,
        content=json.dumps(records[:2]),
        trust_weight=0.85,
    )
    explicit_batch = StructuredMapper(cfg).map_document(explicit_doc)
    ku_ent = next(e for e in explicit_batch.entities if e.entity_id == "ent-ku")
    assert set(ku_ent.aliases) == {"KU", "Kansas Univ"}
    assert ku_ent.attributes["city"] == "Lawrence, KS"
    assert any(r.relation_type == "SUPPORTS" for r in explicit_batch.relations)

    # Missing template variable raises ExtractionError
    bad_tmpl_doc = explicit_doc.model_copy(
        update={"source_id": "bad-tmpl", "content": json.dumps([{"org": "KU"}])}
    )
    with pytest.raises(ExtractionError, match="Missing column"):
        StructuredMapper(cfg).map_document(bad_tmpl_doc)

    # Explicit config without statement_template uses key=val fallback and skips blank rows.
    no_tmpl_cfg = StructuredMappingConfig(
        entities=[EntityMappingRule(name_field="org", entity_type="ORG")],
        relations=[
            RelationMappingRule(
                source_name_field="org",
                source_type="ORG",
                target_name_field="partner",
                target_type="ORG",
                relation_type="AFFILIATED_WITH",
            )
        ],
    )
    fallback_doc = SourceDocument(
        source_id="fallback-json",
        uri="https://example.org/fallback.json",
        source_type=SourceType.JSON,
        content=json.dumps([{"org": "JCCC", "partner": "KU"}, {"org": "", "partner": ""}]),
    )
    fallback_batch = StructuredMapper(no_tmpl_cfg).map_document(fallback_doc)
    assert len(fallback_batch.claims) == 1
    assert "org=JCCC" in fallback_batch.claims[0].statement
    assert any(r.relation_type == "AFFILIATED_WITH" for r in fallback_batch.relations)
