"""Pydantic v2 domain models for KnowledgeReduce."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from knowledgereduce.models.enums import (
    ConflictStrategy,
    LayerTier,
    MergeMode,
    ReliabilityRating,
    SourceType,
)

LAYER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(tz=UTC)


def _normalize_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _validate_non_empty(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must be a non-empty string.")
    return cleaned


def validate_layer_id(layer_id: str) -> str:
    """Validate that a layer ID is safe for filesystem paths and queries."""
    if not LAYER_ID_PATTERN.fullmatch(layer_id):
        raise ValueError(
            f"layer_id must match ^[a-zA-Z0-9][a-zA-Z0-9._-]{{0,127}}$ (got {layer_id!r})."
        )
    return layer_id


class Evidence(BaseModel):
    """Provenance record tying an entity, claim, or relation to a source excerpt."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    uri: str | None = None
    excerpt: str = ""
    char_span: tuple[int, int] | None = None
    extractor_name: str = "unknown"
    extracted_at: datetime = Field(default_factory=utc_now)
    extraction_confidence: float = Field(default=0.8, ge=0.0, le=1.0)

    @field_validator("source_id")
    @classmethod
    def _check_source_id(cls, value: str) -> str:
        return _validate_non_empty(value, "source_id")

    @field_validator("extracted_at")
    @classmethod
    def _check_extracted_at(cls, value: datetime) -> datetime:
        return _normalize_utc(value)

    @field_validator("char_span")
    @classmethod
    def _check_char_span(cls, value: tuple[int, int] | None) -> tuple[int, int] | None:
        if value is not None:
            start, end = value
            if start < 0 or end < start:
                raise ValueError(f"char_span must satisfy 0 <= start <= end (got {value!r}).")
        return value


class SourceDocument(BaseModel):
    """Ingested document or structured source metadata and content."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    uri: str
    source_type: SourceType = SourceType.UNKNOWN
    title: str = ""
    author: str | None = None
    published_at: datetime | None = None
    fetched_at: datetime = Field(default_factory=utc_now)
    content: str = ""
    content_sha256: str = ""
    trust_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_id", "uri")
    @classmethod
    def _check_non_empty(cls, value: str, info: Any) -> str:
        return _validate_non_empty(value, str(info.field_name))

    @field_validator("fetched_at")
    @classmethod
    def _check_fetched_at(cls, value: datetime) -> datetime:
        return _normalize_utc(value)

    @field_validator("published_at")
    @classmethod
    def _check_published_at(cls, value: datetime | None) -> datetime | None:
        return _normalize_utc(value) if value is not None else None

    @model_validator(mode="after")
    def _populate_sha256(self) -> SourceDocument:
        if not self.content_sha256:
            self.content_sha256 = hashlib.sha256(self.content.encode("utf-8")).hexdigest()
        return self


class Entity(BaseModel):
    """Canonical entity node extracted from one or more sources."""

    model_config = ConfigDict(extra="forbid")

    entity_id: str
    canonical_name: str
    entity_type: str = "CONCEPT"
    aliases: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)
    external_ids: dict[str, str] = Field(default_factory=dict)

    @field_validator("entity_id", "canonical_name", "entity_type")
    @classmethod
    def _check_non_empty(cls, value: str, info: Any) -> str:
        return _validate_non_empty(value, str(info.field_name))

    @field_validator("aliases")
    @classmethod
    def _dedup_aliases(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        for alias in value:
            norm = alias.strip()
            if norm and norm not in seen:
                seen.add(norm)
                cleaned.append(norm)
        return cleaned


class Claim(BaseModel):
    """Structured fact/claim preserving the 16-field KnowledgeReduce schema and provenance."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    statement: str
    category: str = "General"
    tags: list[str] = Field(default_factory=list)
    contextual_notes: str = ""
    recorded_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    published_at: datetime | None = None
    reliability: ReliabilityRating = ReliabilityRating.UNVERIFIED
    source_id: str = ""
    source_title: str = ""
    author_creator: str | None = None
    url_reference: str | None = None
    access_level: str = "public"
    usage_count: int = Field(default=0, ge=0)
    related_facts: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    subject_id: str | None = None
    predicate: str | None = None
    object_id: str | None = None
    object_literal: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    merged_from: list[str] = Field(default_factory=list)
    needs_review: bool = False

    @model_validator(mode="before")
    @classmethod
    def _strip_computed_quality_score(cls, data: Any) -> Any:
        if isinstance(data, dict) and "quality_score" in data:
            copied = dict(data)
            copied.pop("quality_score", None)
            return copied
        return data

    @field_validator("claim_id", "statement", "category", "access_level")
    @classmethod
    def _check_non_empty(cls, value: str, info: Any) -> str:
        return _validate_non_empty(value, str(info.field_name))

    @field_validator("tags", "related_facts", "merged_from")
    @classmethod
    def _dedup_str_list(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in value:
            norm = item.strip()
            if norm and norm not in seen:
                seen.add(norm)
                result.append(norm)
        return result

    @field_validator("recorded_at", "updated_at")
    @classmethod
    def _check_utc_required(cls, value: datetime) -> datetime:
        return _normalize_utc(value)

    @field_validator("published_at")
    @classmethod
    def _check_utc_optional(cls, value: datetime | None) -> datetime | None:
        return _normalize_utc(value) if value is not None else None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def quality_score(self) -> float:
        """Return bounded deterministic quality score in [0.0, 100.0]."""
        reliability_pts = (int(self.reliability) / 4.0) * 50.0
        confidence_pts = self.confidence * 25.0
        usage_pts = min(self.usage_count, 10) * 1.5
        evidence_pts = min(len(self.evidence), 5) * 2.0
        score = reliability_pts + confidence_pts + usage_pts + evidence_pts
        return round(min(100.0, max(0.0, score)), 2)


class Relation(BaseModel):
    """Typed directed edge connecting entities or claims in the knowledge graph."""

    model_config = ConfigDict(extra="forbid")

    relation_id: str
    source_id: str
    target_id: str
    relation_type: str
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    weight: float = Field(default=1.0, ge=0.0)
    evidence: list[Evidence] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("relation_id", "source_id", "target_id", "relation_type")
    @classmethod
    def _check_non_empty(cls, value: str, info: Any) -> str:
        return _validate_non_empty(value, str(info.field_name))


class ConflictRecord(BaseModel):
    """Structured record of conflicting assertions and how they were resolved or preserved."""

    model_config = ConfigDict(extra="forbid")

    conflict_id: str
    target_type: Literal["entity_attribute", "relation", "claim"]
    target_key: str
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    resolution_strategy: ConflictStrategy = ConflictStrategy.PRESERVE_DISPUTE
    winning_value: Any = None
    winning_source_id: str | None = None
    resolved_at: datetime = Field(default_factory=utc_now)
    needs_review: bool = True
    resolution_notes: str = ""

    @field_validator("conflict_id", "target_key")
    @classmethod
    def _check_non_empty(cls, value: str, info: Any) -> str:
        return _validate_non_empty(value, str(info.field_name))

    @field_validator("resolved_at")
    @classmethod
    def _check_resolved_at(cls, value: datetime) -> datetime:
        return _normalize_utc(value)


class KnowledgeLayer(BaseModel):
    """Metadata describing an immutable knowledge graph layer in the stack lineage DAG."""

    model_config = ConfigDict(extra="forbid")

    layer_id: str
    name: str
    version: str = "1.0.0"
    tier: LayerTier = LayerTier.REDUCED
    parent_layer_ids: list[str] = Field(default_factory=list)
    merge_mode: MergeMode | None = None
    created_at: datetime = Field(default_factory=utc_now)
    pipeline_config_hash: str = ""
    stats: dict[str, Any] = Field(default_factory=dict)
    description: str = ""

    @field_validator("layer_id")
    @classmethod
    def _check_layer_id(cls, value: str) -> str:
        return validate_layer_id(value)

    @field_validator("parent_layer_ids")
    @classmethod
    def _check_parent_ids(cls, value: list[str]) -> list[str]:
        return [validate_layer_id(pid) for pid in value]

    @field_validator("name", "version")
    @classmethod
    def _check_non_empty(cls, value: str, info: Any) -> str:
        return _validate_non_empty(value, str(info.field_name))

    @field_validator("created_at")
    @classmethod
    def _check_created_at(cls, value: datetime) -> datetime:
        return _normalize_utc(value)


class MappedBatch(BaseModel):
    """Output emitted by a Mapper for a single document or agent submission."""

    model_config = ConfigDict(extra="forbid")

    source_document: SourceDocument | None = None
    entities: list[Entity] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)


class LayerData(BaseModel):
    """Complete materialized payload of a knowledge layer."""

    model_config = ConfigDict(extra="forbid")

    layer: KnowledgeLayer
    sources: list[SourceDocument] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    conflicts: list[ConflictRecord] = Field(default_factory=list)


class LayerDiff(BaseModel):
    """Structural diff between two immutable knowledge layers."""

    model_config = ConfigDict(extra="forbid")

    left_layer_id: str
    right_layer_id: str
    added_entity_ids: list[str] = Field(default_factory=list)
    removed_entity_ids: list[str] = Field(default_factory=list)
    modified_entity_ids: list[str] = Field(default_factory=list)
    added_claim_ids: list[str] = Field(default_factory=list)
    removed_claim_ids: list[str] = Field(default_factory=list)
    modified_claim_ids: list[str] = Field(default_factory=list)
    added_relation_ids: list[str] = Field(default_factory=list)
    removed_relation_ids: list[str] = Field(default_factory=list)
    added_conflict_ids: list[str] = Field(default_factory=list)
    resolved_conflict_ids: list[str] = Field(default_factory=list)


class ValidationReport(BaseModel):
    """Post-reduction and layer integrity validation report."""

    model_config = ConfigDict(extra="forbid")

    layer_id: str
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
