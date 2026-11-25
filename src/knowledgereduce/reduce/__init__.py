"""Reduction engine: representative cluster merging, conflict policies, and integrity checks."""

from knowledgereduce.reduce.conflicts import (
    DEFAULT_FUNCTIONAL_PREDICATES,
    ConflictResolutionDecision,
    adjudicate_conflict,
    adjudicate_conflicts,
    is_functional_predicate,
    resolve_claim_conflicts,
)
from knowledgereduce.reduce.reducer import (
    KnowledgeReducer,
    deduplicate_and_merge_claims,
    deduplicate_relations,
    merge_claim_cluster,
)
from knowledgereduce.reduce.validator import IntegrityValidator

__all__ = [
    "DEFAULT_FUNCTIONAL_PREDICATES",
    "ConflictResolutionDecision",
    "IntegrityValidator",
    "KnowledgeReducer",
    "adjudicate_conflict",
    "adjudicate_conflicts",
    "deduplicate_and_merge_claims",
    "deduplicate_relations",
    "is_functional_predicate",
    "merge_claim_cluster",
    "resolve_claim_conflicts",
]
