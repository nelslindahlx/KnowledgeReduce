"""Fluent QueryBuilder for structured KnowledgeReduce layer queries."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Literal

from knowledgereduce.models import Claim, Entity, ReliabilityRating
from knowledgereduce.storage.base import GraphStore


class QueryBuilder:
    """Immutable-chain fluent query builder over any ``GraphStore`` backend."""

    def __init__(self, store: GraphStore, layer_id: str) -> None:
        self._store = store
        self._layer_id = layer_id
        self._category: str | None = None
        self._tags_any: tuple[str, ...] = ()
        self._min_reliability: ReliabilityRating | None = None
        self._needs_review: bool | None = None
        self._text_query: str | None = None
        self._recorded_after: datetime | None = None
        self._recorded_before: datetime | None = None
        self._entity_type: str | None = None
        self._name_query: str | None = None
        self._sort_by: Literal["quality_score", "reliability", "confidence", "updated_at"] = (
            "quality_score"
        )
        self._descending: bool = True
        self._limit: int = 1000
        self._offset: int = 0

    def _clone(self) -> QueryBuilder:
        copied = QueryBuilder(self._store, self._layer_id)
        copied._category = self._category
        copied._tags_any = self._tags_any
        copied._min_reliability = self._min_reliability
        copied._needs_review = self._needs_review
        copied._text_query = self._text_query
        copied._recorded_after = self._recorded_after
        copied._recorded_before = self._recorded_before
        copied._entity_type = self._entity_type
        copied._name_query = self._name_query
        copied._sort_by = self._sort_by
        copied._descending = self._descending
        copied._limit = self._limit
        copied._offset = self._offset
        return copied

    def filter_category(self, category: str) -> QueryBuilder:
        """Filter claims matching exact *category*."""
        q = self._clone()
        q._category = category
        return q

    def filter_tag(self, tag: str) -> QueryBuilder:
        """Filter claims containing exact *tag*."""
        q = self._clone()
        q._tags_any = (tag,)
        return q

    def filter_tags_any(self, tags: Sequence[str]) -> QueryBuilder:
        """Filter claims matching at least one tag in *tags*."""
        q = self._clone()
        q._tags_any = tuple(tags)
        return q

    def filter_min_reliability(self, min_reliability: ReliabilityRating) -> QueryBuilder:
        """Filter claims with reliability >= *min_reliability*."""
        q = self._clone()
        q._min_reliability = min_reliability
        return q

    def filter_needs_review(self, needs_review: bool) -> QueryBuilder:
        """Filter claims by review flag."""
        q = self._clone()
        q._needs_review = needs_review
        return q

    def filter_text(self, query: str) -> QueryBuilder:
        """Filter claims/entities by case-insensitive substring match."""
        q = self._clone()
        q._text_query = query
        q._name_query = query
        return q

    def filter_date_range(
        self,
        *,
        after: datetime | None = None,
        before: datetime | None = None,
    ) -> QueryBuilder:
        """Filter claims whose ``recorded_at`` falls inside ``[after, before]``."""
        q = self._clone()
        q._recorded_after = after
        q._recorded_before = before
        return q

    def filter_entity_type(self, entity_type: str) -> QueryBuilder:
        """Filter entities matching *entity_type*."""
        q = self._clone()
        q._entity_type = entity_type
        return q

    def sort_claims(
        self,
        *,
        by: Literal["quality_score", "reliability", "confidence", "updated_at"] = "quality_score",
        descending: bool = True,
    ) -> QueryBuilder:
        """Specify claim ordering."""
        q = self._clone()
        q._sort_by = by
        q._descending = descending
        return q

    def limit(self, limit: int, *, offset: int = 0) -> QueryBuilder:
        """Limit and offset returned records."""
        q = self._clone()
        q._limit = max(0, limit)
        q._offset = max(0, offset)
        return q

    def execute_claims(self) -> list[Claim]:
        """Execute query and return matching sorted ``Claim`` records."""
        claims = self._store.list_claims(
            self._layer_id,
            category=self._category,
            tag=self._tags_any[0] if len(self._tags_any) == 1 else None,
            min_reliability=self._min_reliability,
            needs_review=self._needs_review,
            text_query=self._text_query,
            limit=100_000,
            offset=0,
        )
        if len(self._tags_any) > 1:
            allowed_tags = set(self._tags_any)
            claims = [c for c in claims if allowed_tags.intersection(c.tags)]
        if self._recorded_after is not None:
            claims = [c for c in claims if c.recorded_at >= self._recorded_after]
        if self._recorded_before is not None:
            claims = [c for c in claims if c.recorded_at <= self._recorded_before]

        def _sort_key(claim: Claim) -> float:
            if self._sort_by == "reliability":
                return float(int(claim.reliability))
            if self._sort_by == "confidence":
                return claim.confidence
            if self._sort_by == "updated_at":
                return claim.updated_at.timestamp()
            return claim.quality_score

        claims_sorted = sorted(claims, key=_sort_key, reverse=self._descending)
        return claims_sorted[self._offset : self._offset + self._limit]

    def execute_entities(self) -> list[Entity]:
        """Execute query and return matching ``Entity`` records."""
        return self._store.list_entities(
            self._layer_id,
            entity_type=self._entity_type,
            name_query=self._name_query,
            limit=self._limit,
            offset=self._offset,
        )
