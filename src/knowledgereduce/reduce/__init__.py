"""Reduction engine: representative cluster merging, conflict policies, and integrity checks."""

from knowledgereduce.reduce.conflicts import (
    DEFAULT_FUNCTIONAL_PREDICATES,
    is_functional_predicate,
    resolve_claim_conflicts,
)
from knowledgereduce.reduce.reducer import KnowledgeReducer
from knowledgereduce.reduce.validator import IntegrityValidator

__all__ = [
    "DEFAULT_FUNCTIONAL_PREDICATES",
    "IntegrityValidator",
    "KnowledgeReducer",
    "is_functional_predicate",
    "resolve_claim_conflicts",
]
