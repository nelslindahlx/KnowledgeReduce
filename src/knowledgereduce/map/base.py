"""Mapper protocol, deterministic ID helpers, and batch checkpoint utilities."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from knowledgereduce.ingest.base import read_jsonl_checkpoint, write_jsonl_checkpoint
from knowledgereduce.models import MappedBatch, SourceDocument


def deterministic_id(prefix: str, *parts: str) -> str:
    """Create a stable, collision-resistant identifier from normalized components."""
    joined = "|".join(p.strip().lower() for p in parts)
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


@runtime_checkable
class Mapper(Protocol):
    """Stateless document-to-batch extractor interface."""

    name: str

    def map_document(self, doc: SourceDocument) -> MappedBatch:
        """Extract entities, claims, and relations from a single source document."""
        ...

    def map_documents(self, docs: Sequence[SourceDocument]) -> list[MappedBatch]:
        """Extract batches across a sequence of source documents."""
        ...


def save_mapped_batches(batches: Sequence[MappedBatch], path: Path | str) -> Path:
    """Write mapped batches to a resumable ``02_mapped.jsonl`` checkpoint."""
    return write_jsonl_checkpoint(batches, path)


def load_mapped_batches(path: Path | str) -> list[MappedBatch]:
    """Read mapped batches from a JSONL checkpoint."""
    return read_jsonl_checkpoint(path, MappedBatch)
