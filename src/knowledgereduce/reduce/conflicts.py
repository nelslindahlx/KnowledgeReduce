"""Conflict detection and resolution policies for the KnowledgeReduce reduce phase."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Any

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

        if len(by_value) <= 1:
            final_claims.extend(group)
            continue

        # Build structured candidate summaries.
        candidates: list[dict[str, object]] = []
        for _val_low, val_claims in by_value.items():
            best_for_val = max(val_claims, key=lambda c: _claim_rank_key(c, source_trust))
            display_val = _claim_asserted_value(best_for_val) or ""
            weighted_support = sum(
                source_trust.get(c.source_id, 0.5) * c.confidence * (int(c.reliability) + 1)
                for c in val_claims
            )
            candidates.append(
                {
                    "value": display_val,
                    "claim_ids": [c.claim_id for c in val_claims],
                    "source_ids": list(
                        dict.fromkeys(c.source_id for c in val_claims if c.source_id)
                    ),
                    "weighted_support": round(weighted_support, 4),
                    "max_trust": max(source_trust.get(c.source_id, 0.5) for c in val_claims),
                    "max_reliability": max(int(c.reliability) for c in val_claims),
                    "latest_ts": max(
                        (c.published_at or c.updated_at).isoformat() for c in val_claims
                    ),
                }
            )

        if strategy == ConflictStrategy.WEIGHTED_CONSENSUS:
            winning_val_low = max(
                by_value.keys(),
                key=lambda vk: sum(
                    source_trust.get(c.source_id, 0.5) * c.confidence * (int(c.reliability) + 1)
                    for c in by_value[vk]
                ),
            )
        elif strategy == ConflictStrategy.LATEST_TIMESTAMP:
            winning_val_low = max(
                by_value.keys(),
                key=lambda vk: max(
                    (c.published_at or c.updated_at).timestamp() for c in by_value[vk]
                ),
            )
        else:
            # Both PRESERVE_DISPUTE (provisional winner) and SOURCE_TRUST_PRIORITY rank by trust/reliability.
            winning_val_low = max(
                by_value.keys(),
                key=lambda vk: max(_claim_rank_key(c, source_trust) for c in by_value[vk]),
            )

        winning_claims = by_value[winning_val_low]
        provisional_winner = max(winning_claims, key=lambda c: _claim_rank_key(c, source_trust))
        winning_display = _claim_asserted_value(provisional_winner)

        if strategy == ConflictStrategy.PRESERVE_DISPUTE:
            for clm in group:
                updated = clm.model_copy(update={"needs_review": True})
                final_claims.append(updated)
                if clm.claim_id != provisional_winner.claim_id and (
                    (_claim_asserted_value(clm) or "").strip().lower() != winning_val_low
                ):
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
                                        f"{_claim_asserted_value(clm)!r}"
                                    ),
                                    extractor_name="conflict_detector",
                                )
                            ],
                        )
                    )
        else:
            for clm in winning_claims:
                final_claims.append(clm.model_copy(update={"needs_review": False}))

        conflict_id = deterministic_id("cf", key)
        conflicts.append(
            ConflictRecord(
                conflict_id=conflict_id,
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
        )

    return final_claims, contradiction_relations, conflicts


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
    target_conflict = next(
        (cf for cf in base_data.conflicts if cf.conflict_id == conflict_id),
        None,
    )
    if target_conflict is None:
        raise ConflictResolutionError(
            f"Conflict {conflict_id!r} not found in layer {base_data.layer.layer_id!r}."
        )

    participating_claim_ids = {
        str(cid) for cand in target_conflict.candidates for cid in (cand.get("claim_ids") or [])
    }
    updated_conflict = target_conflict.model_copy(
        update={
            "winning_value": winning_value,
            "winning_source_id": winning_source_id or target_conflict.winning_source_id,
            "needs_review": False,
            "resolved_at": utc_now(),
            "resolution_notes": resolution_notes or "Adjudicated via resolve_conflict.",
        }
    )

    updated_conflicts = [
        updated_conflict if cf.conflict_id == conflict_id else cf for cf in base_data.conflicts
    ]
    updated_claims = [
        clm.model_copy(update={"needs_review": False})
        if clm.claim_id in participating_claim_ids
        else clm
        for clm in base_data.claims
    ]
    updated_relations = [
        rel
        for rel in base_data.relations
        if not (
            rel.relation_type == "CONTRADICTS"
            and rel.source_id in participating_claim_ids
            and rel.target_id in participating_claim_ids
        )
    ]

    new_layer = KnowledgeLayer(
        layer_id=target_layer_id,
        name=f"{base_data.layer.name} (Adjudicated)",
        tier=LayerTier.CURATED,
        parent_layer_ids=[base_data.layer.layer_id],
        created_at=utc_now(),
        stats={
            **base_data.layer.stats,
            "relations": len(updated_relations),
            "open_conflicts": sum(1 for cf in updated_conflicts if cf.needs_review),
            "resolved_conflict_id": conflict_id,
        },
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
    return curated, updated_conflict
