"""Conflict detection and resolution policies for the KnowledgeReduce reduce phase."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict

from knowledgereduce.map.base import deterministic_id
from knowledgereduce.models import (
    Claim,
    ConflictRecord,
    ConflictResolutionError,
    ConflictStrategy,
    Evidence,
    KnowledgeLayer,
    LayerData,
    LayerTier,
    Relation,
    utc_now,
)
from knowledgereduce.reduce.validator import IntegrityValidator

DEFAULT_FUNCTIONAL_PREDICATES: frozenset[str] = frozenset(
    {
        "PUBLISHED_IN",
        "FOUNDED_IN",
        "CREATED_IN",
        "ESTABLISHED_IN",
        "LAUNCHED_IN",
        "RELEASED_IN",
        "BORN_IN",
        "BORN_ON",
        "HEADQUARTERED_IN",
        "LOCATED_IN",
        "LOCATED_AT",
        "WORKS_AT",
        "WORKS_FOR",
        "AFFILIATED_WITH",
        "PUBLICATION_YEAR",
        "FOUNDING_YEAR",
        "BIRTH_YEAR",
        "CAPITAL_OF",
        "CEO_OF",
        "STATUS",
        "ROLE",
        "POPULATION",
    }
)


_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")


def is_functional_predicate(
    predicate: str,
    functional_predicates: frozenset[str] | None = None,
) -> bool:
    """Return whether *predicate* expects a single canonical value per subject."""
    norm = predicate.strip().upper()
    vocab = (
        functional_predicates
        if functional_predicates is not None
        else DEFAULT_FUNCTIONAL_PREDICATES
    )
    if norm in vocab:
        return True
    return norm.endswith(("_IN", "_AT", "_ON", "_YEAR", "_DATE"))


def _claim_asserted_value(claim: Claim) -> str | None:
    if claim.object_literal is not None and claim.object_literal.strip():
        return claim.object_literal.strip()
    if claim.object_id:
        return claim.object_id
    return None


def _claim_rank_key(
    claim: Claim,
    source_trust: dict[str, float],
) -> tuple[float, int, float, float, str]:
    trust = source_trust.get(claim.source_id, 0.5)
    ts = (claim.published_at or claim.updated_at).timestamp()
    return (trust, int(claim.reliability), claim.confidence, ts, claim.claim_id)


def _resolve_bucket_conflict(
    key: str,
    group: list[Claim],
    by_bucket: dict[str, list[Claim]],
    source_trust: dict[str, float],
    strategy: ConflictStrategy,
    *,
    bucket_value_fn: Callable[[Claim], str],
    display_value_fn: Callable[[str, list[Claim]], str | None],
) -> tuple[list[Claim], list[Relation], ConflictRecord]:
    """Resolve one multi-valued or temporal-year conflict group cleanly."""
    candidates: list[dict[str, object]] = []
    for bucket_key, bucket_claims in by_bucket.items():
        display_val = display_value_fn(bucket_key, bucket_claims) or ""
        weighted_support = sum(
            source_trust.get(c.source_id, 0.5) * c.confidence * (int(c.reliability) + 1)
            for c in bucket_claims
        )
        candidates.append(
            {
                "value": display_val,
                "claim_ids": [c.claim_id for c in bucket_claims],
                "source_ids": list(
                    dict.fromkeys(c.source_id for c in bucket_claims if c.source_id)
                ),
                "weighted_support": round(weighted_support, 4),
                "max_trust": max(source_trust.get(c.source_id, 0.5) for c in bucket_claims),
                "max_reliability": max(int(c.reliability) for c in bucket_claims),
                "latest_ts": max(
                    (c.published_at or c.updated_at).isoformat() for c in bucket_claims
                ),
            }
        )

    if strategy == ConflictStrategy.WEIGHTED_CONSENSUS:
        winning_key = max(
            by_bucket.keys(),
            key=lambda bk: sum(
                source_trust.get(c.source_id, 0.5) * c.confidence * (int(c.reliability) + 1)
                for c in by_bucket[bk]
            ),
        )
    elif strategy == ConflictStrategy.LATEST_TIMESTAMP:
        winning_key = max(
            by_bucket.keys(),
            key=lambda bk: max((c.published_at or c.updated_at).timestamp() for c in by_bucket[bk]),
        )
    else:
        # Both PRESERVE_DISPUTE (provisional winner) and SOURCE_TRUST_PRIORITY rank by trust/reliability.
        winning_key = max(
            by_bucket.keys(),
            key=lambda bk: max(_claim_rank_key(c, source_trust) for c in by_bucket[bk]),
        )

    winning_claims = by_bucket[winning_key]
    provisional_winner = max(winning_claims, key=lambda c: _claim_rank_key(c, source_trust))
    winning_display = display_value_fn(winning_key, winning_claims)

    emitted_claims: list[Claim] = []
    contradiction_relations: list[Relation] = []
    if strategy == ConflictStrategy.PRESERVE_DISPUTE:
        for clm in group:
            updated = clm.model_copy(update={"needs_review": True})
            emitted_claims.append(updated)
            clm_bucket = bucket_value_fn(clm)
            if clm.claim_id != provisional_winner.claim_id and clm_bucket != winning_key:
                rel_id = deterministic_id(
                    "rel", provisional_winner.claim_id, "CONTRADICTS", clm.claim_id
                )
                contradiction_relations.append(
                    Relation(
                        relation_id=rel_id,
                        source_id=provisional_winner.claim_id,
                        target_id=clm.claim_id,
                        relation_type="CONTRADICTS",
                        confidence=1.0,
                        evidence=[
                            Evidence(
                                source_id=provisional_winner.source_id or "conflict_detector",
                                excerpt=(
                                    f"Conflict on {key}: {winning_display!r} vs "
                                    f"{display_value_fn(clm_bucket, [clm])!r}"
                                ),
                                extractor_name="conflict_detector",
                            )
                        ],
                    )
                )
    else:
        for clm in winning_claims:
            emitted_claims.append(clm.model_copy(update={"needs_review": False}))

    record = ConflictRecord(
        conflict_id=deterministic_id("cf", key),
        target_type="claim",
        target_key=key,
        candidates=candidates,
        resolution_strategy=strategy,
        winning_value=winning_display,
        winning_source_id=provisional_winner.source_id or None,
        needs_review=(strategy == ConflictStrategy.PRESERVE_DISPUTE),
        resolution_notes=(
            "Preserved competing claims with CONTRADICTS edges for review."
            if strategy == ConflictStrategy.PRESERVE_DISPUTE
            else f"Automatically resolved via {strategy.value}."
        ),
    )
    return emitted_claims, contradiction_relations, record


def resolve_claim_conflicts(
    claims: Sequence[Claim],
    source_trust: dict[str, float],
    *,
    strategy: ConflictStrategy = ConflictStrategy.PRESERVE_DISPUTE,
    functional_predicates: frozenset[str] | None = None,
) -> tuple[list[Claim], list[Relation], list[ConflictRecord]]:
    """Detect and resolve conflicts among claims asserting functional triples.

    Returns ``(resulting_claims, contradiction_relations, conflict_records)``.
    """
    groups: dict[str, list[Claim]] = defaultdict(list)
    passthrough: list[Claim] = []

    for clm in claims:
        if (
            clm.subject_id
            and clm.predicate
            and is_functional_predicate(clm.predicate, functional_predicates)
        ):
            val = _claim_asserted_value(clm)
            if val is not None:
                key = f"{clm.subject_id}::{clm.predicate.strip().upper()}"
                groups[key].append(clm)
                continue
        passthrough.append(clm)

    final_claims: list[Claim] = list(passthrough)
    contradiction_relations: list[Relation] = []
    conflicts: list[ConflictRecord] = []

    for key, group in sorted(groups.items()):
        by_value: dict[str, list[Claim]] = defaultdict(list)
        for clm in group:
            val = (_claim_asserted_value(clm) or "").strip()
            by_value[val.lower()].append(clm)

        if len(by_value) > 1:
            emitted, rels, record = _resolve_bucket_conflict(
                key,
                group,
                by_value,
                source_trust,
                strategy,
                bucket_value_fn=lambda c: (_claim_asserted_value(c) or "").strip().lower(),
                display_value_fn=lambda _bk, bclaims: _claim_asserted_value(
                    max(bclaims, key=lambda c: _claim_rank_key(c, source_trust))
                ),
            )
            final_claims.extend(emitted)
            contradiction_relations.extend(rels)
            conflicts.append(record)
            continue

        # Even when object_id/literal matches, catch mutually exclusive single-year assertions.
        by_year: dict[str, list[Claim]] = defaultdict(list)
        undated: list[Claim] = []
        for clm in group:
            years = sorted(set(_YEAR_RE.findall(clm.statement)))
            if len(years) == 1:
                by_year[years[0]].append(clm)
            else:
                undated.append(clm)

        if len(by_year) > 1:
            dated_group = [clm for yclaims in by_year.values() for clm in yclaims]
            emitted, rels, record = _resolve_bucket_conflict(
                f"{key}::year",
                dated_group,
                by_year,
                source_trust,
                strategy,
                bucket_value_fn=lambda c: sorted(set(_YEAR_RE.findall(c.statement)))[0],
                display_value_fn=lambda bk, _bclaims: bk,
            )
            final_claims.extend(undated)
            final_claims.extend(emitted)
            contradiction_relations.extend(rels)
            conflicts.append(record)
            continue

        final_claims.extend(group)

    return final_claims, contradiction_relations, conflicts


class ConflictResolutionDecision(BaseModel):
    """Single conflict resolution item for atomic batch adjudication."""

    model_config = ConfigDict(extra="forbid")

    conflict_id: str
    winning_value: Any
    winning_source_id: str | None = None
    resolution_notes: str = ""


def _participating_claim_ids(conflict: ConflictRecord) -> set[str]:
    return {str(cid) for cand in conflict.candidates for cid in (cand.get("claim_ids") or [])}


def adjudicate_conflicts(
    base_data: LayerData,
    *,
    decisions: Sequence[ConflictResolutionDecision],
    target_layer_id: str,
    default_notes: str = "",
) -> tuple[LayerData, list[ConflictRecord]]:
    """Atomically adjudicate one or more conflicts into a single ``CURATED`` child layer."""
    if not decisions:
        raise ConflictResolutionError("Provide at least one conflict resolution decision.")

    conflicts_by_id = {cf.conflict_id: cf for cf in base_data.conflicts}
    seen_ids: set[str] = set()
    for decision in decisions:
        if decision.conflict_id in seen_ids:
            raise ConflictResolutionError(
                f"Duplicate conflict_id in batch resolution: {decision.conflict_id!r}."
            )
        seen_ids.add(decision.conflict_id)
        if decision.conflict_id not in conflicts_by_id:
            raise ConflictResolutionError(
                f"Conflict {decision.conflict_id!r} not found in layer {base_data.layer.layer_id!r}."
            )

    now = utc_now()
    resolved_by_id: dict[str, ConflictRecord] = {}
    resolved_records: list[ConflictRecord] = []
    resolved_claim_sets: list[set[str]] = []
    all_resolved_claim_ids: set[str] = set()

    for decision in decisions:
        target_conflict = conflicts_by_id[decision.conflict_id]
        updated_conflict = target_conflict.model_copy(
            update={
                "winning_value": decision.winning_value,
                "winning_source_id": decision.winning_source_id
                or target_conflict.winning_source_id,
                "needs_review": False,
                "resolved_at": now,
                "resolution_notes": decision.resolution_notes
                or default_notes
                or "Adjudicated via resolve_conflicts.",
            }
        )
        resolved_by_id[decision.conflict_id] = updated_conflict
        resolved_records.append(updated_conflict)
        cset = _participating_claim_ids(target_conflict)
        resolved_claim_sets.append(cset)
        all_resolved_claim_ids.update(cset)

    updated_conflicts = [resolved_by_id.get(cf.conflict_id, cf) for cf in base_data.conflicts]
    remaining_unresolved_claim_sets = [
        _participating_claim_ids(cf) for cf in updated_conflicts if cf.needs_review
    ]
    unresolved_claim_ids: set[str] = set().union(*remaining_unresolved_claim_sets)

    updated_claims = [
        clm.model_copy(update={"needs_review": False})
        if clm.claim_id in all_resolved_claim_ids and clm.claim_id not in unresolved_claim_ids
        else clm
        for clm in base_data.claims
    ]

    def _should_remove_contradicts(rel: Relation) -> bool:
        if rel.relation_type != "CONTRADICTS":
            return False
        in_resolved = any(
            rel.source_id in cset and rel.target_id in cset for cset in resolved_claim_sets
        )
        still_unresolved = any(
            rel.source_id in uset and rel.target_id in uset
            for uset in remaining_unresolved_claim_sets
        )
        return in_resolved and not still_unresolved

    updated_relations = [rel for rel in base_data.relations if not _should_remove_contradicts(rel)]

    layer_stats: dict[str, Any] = {
        **base_data.layer.stats,
        "relations": len(updated_relations),
        "open_conflicts": sum(1 for cf in updated_conflicts if cf.needs_review),
        "resolved_conflict_ids": [d.conflict_id for d in decisions],
    }
    if len(decisions) == 1:
        layer_stats["resolved_conflict_id"] = decisions[0].conflict_id

    new_layer = KnowledgeLayer(
        layer_id=target_layer_id,
        name=f"{base_data.layer.name} (Adjudicated)",
        tier=LayerTier.CURATED,
        parent_layer_ids=[base_data.layer.layer_id],
        created_at=now,
        stats=layer_stats,
    )
    curated = LayerData(
        layer=new_layer,
        sources=base_data.sources,
        entities=base_data.entities,
        claims=updated_claims,
        relations=updated_relations,
        conflicts=updated_conflicts,
    )
    IntegrityValidator().validate(curated, strict=True)
    return curated, resolved_records


def adjudicate_conflict(
    base_data: LayerData,
    *,
    conflict_id: str,
    target_layer_id: str,
    winning_value: Any,
    winning_source_id: str | None = None,
    resolution_notes: str = "",
) -> tuple[LayerData, ConflictRecord]:
    """Adjudicate *conflict_id* non-destructively into a new ``CURATED`` child layer."""
    curated, resolved = adjudicate_conflicts(
        base_data,
        decisions=[
            ConflictResolutionDecision(
                conflict_id=conflict_id,
                winning_value=winning_value,
                winning_source_id=winning_source_id,
                resolution_notes=resolution_notes or "Adjudicated via resolve_conflict.",
            )
        ],
        target_layer_id=target_layer_id,
    )
    return curated, resolved[0]
