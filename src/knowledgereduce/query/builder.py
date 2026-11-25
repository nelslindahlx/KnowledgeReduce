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
        self._tags_any: tuple[str, ...] | None = None
        self._min_reliability: ReliabilityRating | None = None
        self._needs_review: bool | None = None
        self._text_query: str | None = None
        self._recorded_after: datetime | None = None
        self._recorded_before: datetime | None = None
        self._published_after: datetime | None = None
        self._published_before: datetime | None = None
        self._subject_id: str | None = None
        self._predicate: str | None = None
        self._source_id: str | None = None
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
        copied._published_after = self._published_after
        copied._published_before = self._published_before
        copied._subject_id = self._subject_id
        copied._predicate = self._predicate
        copied._source_id = self._source_id
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

    def filter_published_range(
        self,
        *,
        after: datetime | None = None,
        before: datetime | None = None,
    ) -> QueryBuilder:
        """Filter claims whose ``published_at`` falls inside ``[after, before]``."""
        q = self._clone()
        q._published_after = after
        q._published_before = before
        return q

    def filter_subject(self, subject_id: str) -> QueryBuilder:
        """Filter claims matching exact *subject_id*."""
        q = self._clone()
        q._subject_id = subject_id
        return q

    def filter_predicate(self, predicate: str) -> QueryBuilder:
        """Filter claims matching exact *predicate*."""
        q = self._clone()
        q._predicate = predicate
        return q

    def filter_source(self, source_id: str) -> QueryBuilder:
        """Filter claims emitted from *source_id*."""
        q = self._clone()
        q._source_id = source_id
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
        """Execute query with store-level filtering, sorting, and pagination pushdown."""
        single_tag = (
            self._tags_any[0] if self._tags_any is not None and len(self._tags_any) == 1 else None
        )
        multi_tags = (
            self._tags_any if self._tags_any is not None and len(self._tags_any) != 1 else None
        )
        return self._store.list_claims(
            self._layer_id,
            category=self._category,
            tag=single_tag,
            tags_any=multi_tags,
            min_reliability=self._min_reliability,
            needs_review=self._needs_review,
            text_query=self._text_query,
            recorded_after=self._recorded_after,
            recorded_before=self._recorded_before,
            published_after=self._published_after,
            published_before=self._published_before,
            subject_id=self._subject_id,
            predicate=self._predicate,
            source_id=self._source_id,
            sort_by=self._sort_by,
            descending=self._descending,
            limit=self._limit,
            offset=self._offset,
        )

    def execute_entities(self) -> list[Entity]:
        """Execute query and return matching ``Entity`` records."""
        return self._store.list_entities(
            self._layer_id,
            entity_type=self._entity_type,
            name_query=self._name_query,
            limit=self._limit,
            offset=self._offset,
        )
