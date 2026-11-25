"""Core enumeration types for KnowledgeReduce."""

from __future__ import annotations

from enum import IntEnum, StrEnum


class ReliabilityRating(IntEnum):
    """Ordinal trust rating for extracted claims and facts."""

    UNKNOWN = 0
    UNVERIFIED = 1
    POSSIBLY_TRUE = 2
    LIKELY_TRUE = 3
    VERIFIED = 4


class SourceType(StrEnum):
    """Supported ingestion source types."""

    WEB = "web"
    CSV = "csv"
    JSON = "json"
    JSONL = "jsonl"
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"
    TEXT = "text"
    AGENT = "agent"
    UNKNOWN = "unknown"


class LayerTier(StrEnum):
    """Optional maturity tier for a knowledge layer."""

    RAW = "raw"
    REDUCED = "reduced"
    CURATED = "curated"
    STACKED = "stacked"


class ConflictStrategy(StrEnum):
    """Available policies for resolving conflicting claims or attributes."""

    PRESERVE_DISPUTE = "preserve_dispute"
    SOURCE_TRUST_PRIORITY = "source_trust_priority"
    WEIGHTED_CONSENSUS = "weighted_consensus"
    LATEST_TIMESTAMP = "latest_timestamp"


class MergeMode(StrEnum):
    """Set/composition algebra modes for stacking knowledge layers."""

    OVERLAY = "overlay"
    UNION = "union"
    INTERSECTION = "intersection"
    DIFFERENCE = "difference"
