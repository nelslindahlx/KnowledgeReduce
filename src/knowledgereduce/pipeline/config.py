"""Declarative pipeline configuration for KnowledgeReduce."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from knowledgereduce.ingest.web import CrawlConfig
from knowledgereduce.map.structured import StructuredMappingConfig
from knowledgereduce.models import ConflictStrategy, LayerTier, SchemaValidationError


class LocalFileSourceConfig(BaseModel):
    """Configuration for ingesting a single local structured or text file."""

    model_config = ConfigDict(extra="forbid")

    path: str
    source_id: str | None = None
    trust_weight: float = Field(default=0.8, ge=0.0, le=1.0)


class PipelineConfig(BaseModel):
    """End-to-end KnowledgeReduce pipeline configuration."""

    model_config = ConfigDict(extra="forbid")

    layer_id: str
    layer_name: str
    tier: LayerTier = LayerTier.REDUCED
    store_dir: str = ".knowledgereduce_store"
    checkpoint_dir: str | None = None
    web_crawl: CrawlConfig | None = None
    local_files: list[LocalFileSourceConfig] = Field(default_factory=list)
    mapper: Literal["deterministic", "spacy", "structured"] = "deterministic"
    spacy_model: str = "en_core_web_sm"
    structured_config: StructuredMappingConfig | None = None
    min_sentence_length: int = Field(default=25, ge=0)
    min_claim_length: int = Field(default=20, ge=0)
    lexical_threshold: float = Field(default=0.88, gt=0.0, le=1.0)
    semantic_threshold: float = Field(default=0.84, gt=0.0, le=1.0)
    use_sentence_transformers: bool = False
    embedding_model: str = "all-MiniLM-L6-v2"
    conflict_strategy: ConflictStrategy = ConflictStrategy.PRESERVE_DISPUTE
    max_workers: int = Field(default=1, ge=1, le=32)
    overwrite: bool = False

    def config_sha256(self) -> str:
        """Compute a deterministic hash of this configuration."""
        return hashlib.sha256(self.model_dump_json().encode("utf-8")).hexdigest()[:16]

    @classmethod
    def from_yaml(cls, path: Path | str) -> PipelineConfig:
        """Load and validate a ``PipelineConfig`` from a YAML file."""
        src = Path(path)
        if not src.is_file():
            raise SchemaValidationError(f"Pipeline config file not found: {src}")
        raw = yaml.safe_load(src.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise SchemaValidationError(f"Pipeline config in {src} must be a YAML mapping.")
        return cls.model_validate(raw)
