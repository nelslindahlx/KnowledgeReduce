"""Declarative mapper for structured CSV, JSON, and JSONL documents."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from knowledgereduce.map.base import deterministic_id
from knowledgereduce.models import (
    Claim,
    Entity,
    Evidence,
    ExtractionError,
    MappedBatch,
    Relation,
    ReliabilityRating,
    SourceDocument,
    SourceType,
)


class EntityMappingRule(BaseModel):
    """Declarative rule extracting an entity from a structured record."""

    model_config = ConfigDict(extra="forbid")

    name_field: str
    entity_type: str = "CONCEPT"
    id_field: str | None = None
    alias_fields: list[str] = Field(default_factory=list)
    attribute_fields: list[str] = Field(default_factory=list)


class RelationMappingRule(BaseModel):
    """Declarative rule connecting two entities within a structured record."""

    model_config = ConfigDict(extra="forbid")

    source_name_field: str
    source_type: str = "CONCEPT"
    target_name_field: str
    target_type: str = "CONCEPT"
    relation_type: str = "RELATED_TO"


class StructuredMappingConfig(BaseModel):
    """Configuration controlling how structured records map to graph primitives."""

    model_config = ConfigDict(extra="forbid")

    entities: list[EntityMappingRule] = Field(default_factory=list)
    relations: list[RelationMappingRule] = Field(default_factory=list)
    statement_template: str | None = None
    statement_field: str | None = None
    category_field: str | None = None
    default_category: str = "Structured"
    tags_field: str | None = None
    reliability_field: str | None = None
    subject_field: str | None = None
    predicate_field: str | None = None
    object_field: str | None = None


def _parse_reliability(raw: Any, fallback_trust: float) -> ReliabilityRating:
    if isinstance(raw, int) and not isinstance(raw, bool):
        return ReliabilityRating(max(0, min(4, raw)))
    if isinstance(raw, str):
        norm = raw.strip().upper()
        for member in ReliabilityRating:
            if member.name == norm:
                return member
        if norm.isdigit():
            return ReliabilityRating(max(0, min(4, int(norm))))
    if fallback_trust >= 0.85:
        return ReliabilityRating.VERIFIED
    if fallback_trust >= 0.65:
        return ReliabilityRating.LIKELY_TRUE
    if fallback_trust >= 0.4:
        return ReliabilityRating.POSSIBLY_TRUE
    return ReliabilityRating.UNVERIFIED


def _parse_tags(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    return []


def _parse_records(doc: SourceDocument) -> list[dict[str, Any]]:
    if doc.source_type == SourceType.CSV:
        reader = csv.DictReader(io.StringIO(doc.content))
        return [dict(row) for row in reader]
    if doc.source_type in {SourceType.JSON, SourceType.JSONL}:
        try:
            parsed = json.loads(doc.content) if doc.content.strip() else []
        except json.JSONDecodeError as exc:
            raise ExtractionError(
                f"Failed to parse structured JSON content for {doc.source_id!r}: {exc}"
            ) from exc
        if isinstance(parsed, dict):
            return [parsed]
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
    raise ExtractionError(
        f"StructuredMapper requires CSV, JSON, or JSONL source_type (got {doc.source_type!r})."
    )


class StructuredMapper:
    """Maps structured CSV/JSON/JSONL rows into grounded entities, claims, and relations."""

    name: str = "structured_mapper"

    def __init__(self, config: StructuredMappingConfig | None = None) -> None:
        self.config = config

    def _effective_config(self, sample_row: dict[str, Any]) -> StructuredMappingConfig:
        if self.config is not None:
            return self.config
        entities: list[EntityMappingRule] = []
        if "subject" in sample_row:
            entities.append(
                EntityMappingRule(
                    name_field="subject",
                    entity_type=str(sample_row.get("subject_type") or "CONCEPT"),
                )
            )
        if "object" in sample_row and sample_row.get("object_is_entity", True):
            entities.append(
                EntityMappingRule(
                    name_field="object",
                    entity_type=str(sample_row.get("object_type") or "CONCEPT"),
                )
            )
        relations: list[RelationMappingRule] = []
        if "subject" in sample_row and "object" in sample_row and "predicate" in sample_row:
            relations.append(
                RelationMappingRule(
                    source_name_field="subject",
                    source_type=str(sample_row.get("subject_type") or "CONCEPT"),
                    target_name_field="object",
                    target_type=str(sample_row.get("object_type") or "CONCEPT"),
                    relation_type=str(sample_row.get("predicate") or "RELATED_TO").upper(),
                )
            )
        return StructuredMappingConfig(
            entities=entities,
            relations=relations,
            statement_field="statement" if "statement" in sample_row else None,
            category_field="category" if "category" in sample_row else None,
            tags_field="tags" if "tags" in sample_row else None,
            reliability_field="reliability" if "reliability" in sample_row else None,
            subject_field="subject" if "subject" in sample_row else None,
            predicate_field="predicate" if "predicate" in sample_row else None,
            object_field="object" if "object" in sample_row else None,
        )

    def map_document(self, doc: SourceDocument) -> MappedBatch:
        """Map all records in *doc* into a single ``MappedBatch``."""
        rows = _parse_records(doc)
        if not rows:
            return MappedBatch(source_document=doc)

        cfg = self._effective_config(rows[0])
        entities_by_id: dict[str, Entity] = {}
        claims: list[Claim] = []
        relations_by_id: dict[str, Relation] = {}

        for idx, row in enumerate(rows):
            row_excerpt = json.dumps(row, ensure_ascii=False)[:300]
            evidence = Evidence(
                source_id=doc.source_id,
                uri=doc.uri,
                excerpt=row_excerpt,
                extractor_name=self.name,
                extraction_confidence=min(1.0, max(0.3, doc.trust_weight + 0.15)),
            )

            row_entity_ids: list[str] = []
            field_to_entity_id: dict[str, str] = {}

            for rule in cfg.entities:
                raw_name = str(row.get(rule.name_field) or "").strip()
                if not raw_name:
                    continue
                if rule.id_field and row.get(rule.id_field):
                    ent_id = str(row[rule.id_field]).strip()
                else:
                    ent_id = deterministic_id("ent", rule.entity_type, raw_name)

                aliases = [
                    str(row[af]).strip()
                    for af in rule.alias_fields
                    if row.get(af) and str(row[af]).strip()
                ]
                attrs = {
                    af: row[af]
                    for af in rule.attribute_fields
                    if af in row and row[af] not in (None, "")
                }

                if ent_id not in entities_by_id:
                    entities_by_id[ent_id] = Entity(
                        entity_id=ent_id,
                        canonical_name=raw_name,
                        entity_type=rule.entity_type,
                        aliases=aliases,
                        attributes=attrs,
                        evidence=[evidence],
                    )
                else:
                    existing = entities_by_id[ent_id]
                    existing.aliases = list(dict.fromkeys([*existing.aliases, *aliases]))
                    existing.attributes.update(attrs)
                    existing.evidence.append(evidence)

                row_entity_ids.append(ent_id)
                field_to_entity_id[rule.name_field] = ent_id

            for rel_rule in cfg.relations:
                src_name = str(row.get(rel_rule.source_name_field) or "").strip()
                dst_name = str(row.get(rel_rule.target_name_field) or "").strip()
                if not src_name or not dst_name:
                    continue
                src_id = field_to_entity_id.get(
                    rel_rule.source_name_field,
                    deterministic_id("ent", rel_rule.source_type, src_name),
                )
                dst_id = field_to_entity_id.get(
                    rel_rule.target_name_field,
                    deterministic_id("ent", rel_rule.target_type, dst_name),
                )
                if src_id not in entities_by_id:
                    entities_by_id[src_id] = Entity(
                        entity_id=src_id,
                        canonical_name=src_name,
                        entity_type=rel_rule.source_type,
                        evidence=[evidence],
                    )
                if dst_id not in entities_by_id:
                    entities_by_id[dst_id] = Entity(
                        entity_id=dst_id,
                        canonical_name=dst_name,
                        entity_type=rel_rule.target_type,
                        evidence=[evidence],
                    )
                rel_type = (
                    str(row.get("predicate") or rel_rule.relation_type).strip().upper()
                    if rel_rule.relation_type == "RELATED_TO" and row.get("predicate")
                    else rel_rule.relation_type
                )
                rel_id = deterministic_id("rel", src_id, rel_type, dst_id)
                if rel_id not in relations_by_id:
                    relations_by_id[rel_id] = Relation(
                        relation_id=rel_id,
                        source_id=src_id,
                        target_id=dst_id,
                        relation_type=rel_type,
                        confidence=min(1.0, max(0.5, doc.trust_weight)),
                        evidence=[evidence],
                    )

            # Build statement for Claim
            if cfg.statement_template:
                try:
                    statement = cfg.statement_template.format(**row).strip()
                except KeyError as exc:
                    raise ExtractionError(
                        f"Missing column {exc} for statement_template in {doc.source_id!r}."
                    ) from exc
            elif cfg.statement_field and row.get(cfg.statement_field):
                statement = str(row[cfg.statement_field]).strip()
            else:
                parts = [f"{k}={v}" for k, v in row.items() if v not in (None, "")]
                statement = "; ".join(parts)

            if not statement:
                continue

            subj_id: str | None = None
            if cfg.subject_field and row.get(cfg.subject_field):
                subj_val = str(row[cfg.subject_field]).strip()
                subj_id = field_to_entity_id.get(
                    cfg.subject_field, deterministic_id("ent", "CONCEPT", subj_val)
                )

            pred_val = (
                str(row[cfg.predicate_field]).strip().upper()
                if cfg.predicate_field and row.get(cfg.predicate_field)
                else None
            )
            obj_lit = (
                str(row[cfg.object_field]).strip()
                if cfg.object_field and row.get(cfg.object_field) is not None
                else None
            )
            obj_id = (
                field_to_entity_id.get(cfg.object_field)
                if cfg.object_field and cfg.object_field in field_to_entity_id
                else None
            )

            category = (
                str(row.get(cfg.category_field) or cfg.default_category).strip()
                if cfg.category_field
                else cfg.default_category
            )
            tags = _parse_tags(row.get(cfg.tags_field)) if cfg.tags_field else []
            reliability = _parse_reliability(
                row.get(cfg.reliability_field) if cfg.reliability_field else None,
                doc.trust_weight,
            )

            claim_id = deterministic_id("clm", doc.source_id, str(idx), statement)
            claims.append(
                Claim(
                    claim_id=claim_id,
                    statement=statement,
                    category=category or cfg.default_category,
                    tags=tags,
                    reliability=reliability,
                    source_id=doc.source_id,
                    source_title=doc.title,
                    author_creator=doc.author,
                    url_reference=doc.uri,
                    published_at=doc.published_at,
                    confidence=min(1.0, max(0.5, doc.trust_weight + 0.1)),
                    subject_id=subj_id,
                    predicate=pred_val,
                    object_id=obj_id,
                    object_literal=obj_lit,
                    evidence=[evidence],
                )
            )

            for ent_id in dict.fromkeys(row_entity_ids):
                m_rel_id = deterministic_id("rel", claim_id, "MENTIONS", ent_id)
                relations_by_id[m_rel_id] = Relation(
                    relation_id=m_rel_id,
                    source_id=claim_id,
                    target_id=ent_id,
                    relation_type="MENTIONS",
                    confidence=1.0,
                    evidence=[evidence],
                )

        return MappedBatch(
            source_document=doc,
            entities=list(entities_by_id.values()),
            claims=claims,
            relations=list(relations_by_id.values()),
        )

    def map_documents(self, docs: Sequence[SourceDocument]) -> list[MappedBatch]:
        """Map multiple structured documents."""
        return [self.map_document(doc) for doc in docs]
