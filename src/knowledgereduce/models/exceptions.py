"""Typed domain exceptions for KnowledgeReduce."""

from __future__ import annotations


class KnowledgeReduceError(Exception):
    """Base exception for all KnowledgeReduce errors."""


class SchemaValidationError(KnowledgeReduceError):
    """Raised when input data fails schema or identifier validation."""


class IngestionError(KnowledgeReduceError):
    """Raised when reading or crawling a data source fails."""


class SSRFError(IngestionError):
    """Raised when a URL fails SSRF scheme or IP address validation."""


class ExtractionError(KnowledgeReduceError):
    """Raised when mapping or NLP extraction fails."""


class StorageError(KnowledgeReduceError):
    """Raised when reading or writing a graph store or Parquet layer fails."""


class StackError(KnowledgeReduceError):
    """Raised when layer stacking or lineage operations fail."""


class ConflictResolutionError(KnowledgeReduceError):
    """Raised when conflict detection or resolution encounters an invalid state."""


class IntegrityValidationError(KnowledgeReduceError):
    """Raised when post-reduction graph integrity checks fail."""


class PathSecurityError(KnowledgeReduceError):
    """Raised when a file path escapes an allowed workspace directory."""
