"""Representative-preserving knowledge reducer uniting entity resolution, clustering, and conflicts."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from knowledgereduce.models import (
    Claim,
    ConflictStrategy,
    Evidence,
    KnowledgeLayer,
    LayerData,
    LayerTier,
    MappedBatch,
    Relation,
    utc_now,
)
from knowledgereduce.reduce.conflicts import resolve_claim_conflicts
from knowledgereduce.reduce.validator import IntegrityValidator
from knowledgereduce.resolve import EmbeddingProvider, cluster_claims, resolve_entities_and_remap


def _dedup_evidence(items: Sequence[Evidence]) -> list[Evidence]:
    seen: set[tuple[str, str | None, str, tuple[int, int] | None, str]] = set()
    result: list[Evidence] = []
    for ev in items:
        key = (ev.source_id, ev.uri, ev.excerpt, ev.char_span, ev.extractor_name)
        if key not in seen:
            seen.add(key)
            result.append(ev)
    return result


def _claim_importance(
    claim: Claim,
    source_trust: dict[str, float],
    degree_map: dict[str, int],
    max_degree: int,
) -> tuple[float, int, str]:
    rel_norm = int(claim.reliability) / 4.0
    trust_norm = source_trust.get(claim.source_id, 0.5)
    spec_norm = min(len(claim.statement.strip()) / 200.0, 1.0)
    conn_norm = degree_map.get(claim.claim_id, 0) / max(max_degree, 1)
    score = 0.35 * rel_norm + 0.25 * trust_norm + 0.20 * spec_norm + 0.20 * conn_norm
    return (round(score, 6), len(claim.evidence), claim.claim_id)


def _merge_claim_cluster(
    cluster: Sequence[Claim],
    source_trust: dict[str, float],
    degree_map: dict[str, int],
    max_degree: int,
) -> tuple[Claim, dict[str, str]]:
    ordered = sorted(
        cluster,
        key=lambda c: _claim_importance(c, source_trust, degree_map, max_degree),
        reverse=True,
    )
    winner = ordered[0]
    id_map: dict[str, str] = {c.claim_id: winner.claim_id for c in cluster}

    all_evidence = _dedup_evidence([ev for c in ordered for ev in c.evidence])
    all_tags = list(dict.fromkeys(tag for c in ordered for tag in c.tags))
    all_related = list(dict.fromkeys(rf for c in ordered for rf in c.related_facts))
    merged_ids = list(
        dict.fromkeys(
            [
                *[mid for c in ordered for mid in c.merged_from],
                *[c.claim_id for c in ordered[1:]],
            ]
        )
    )
    total_usage = sum(c.usage_count for c in ordered)
    max_rel = max(c.reliability for c in ordered)
    max_conf = max(c.confidence for c in ordered)
    min_rec = min(c.recorded_at for c in ordered)
    max_upd = max(c.updated_at for c in ordered)

    merged_claim = winner.model_copy(
        update={
            "tags": all_tags,
            "related_facts": all_related,
            "merged_from": merged_ids,
            "evidence": all_evidence,
            "usage_count": total_usage,
            "reliability": max_rel,
            "confidence": max_conf,
            "recorded_at": min_rec,
            "updated_at": max_upd,
        }
    )
    return merged_claim, id_map


class KnowledgeReducer:
    """Reduces mapped batches into a deduplicated, conflict-aware ``LayerData``."""

    def __init__(
        self,
        *,
        lexical_threshold: float = 0.88,
        semantic_threshold: float = 0.84,
        min_claim_length: int = 20,
        conflict_strategy: ConflictStrategy = ConflictStrategy.PRESERVE_DISPUTE,
        embedding_provider: EmbeddingProvider | None = None,
        single_valued_predicates: frozenset[str] | None = None,
    ) -> None:
        self.lexical_threshold = lexical_threshold
        self.semantic_threshold = semantic_threshold
        self.min_claim_length = min_claim_length
        self.conflict_strategy = conflict_strategy
        self.embedding_provider = embedding_provider
        self.single_valued_predicates = single_valued_predicates
        self.validator = IntegrityValidator()

    def reduce_batches(
        self,
        batches: Sequence[MappedBatch],
        *,
        layer_id: str,
        layer_name: str,
        tier: LayerTier = LayerTier.REDUCED,
        parent_layer_ids: list[str] | None = None,
        pipeline_config_hash: str = "",
        strict_validation: bool = True,
    ) -> LayerData:
        """Resolve entities, cluster duplicate claims, resolve conflicts, and validate graph."""
        raw_entities_count = sum(len(b.entities) for b in batches)
        raw_claims_count = sum(len(b.claims) for b in batches)

        entities, remapped_claims, remapped_relations, sources, _entity_id_map = (
            resolve_entities_and_remap(
                batches,
                lexical_threshold=self.lexical_threshold,
            )
        )
        source_trust = {s.source_id: s.trust_weight for s in sources}

        # Compute pre-cluster incident relation counts for claim importance ranking.
        degree_map: dict[str, int] = defaultdict(int)
        for rel in remapped_relations:
            degree_map[rel.source_id] += 1
            degree_map[rel.target_id] += 1
        max_degree = max(degree_map.values(), default=1)

        clusters, dropped_short = cluster_claims(
            remapped_claims,
            lexical_threshold=self.lexical_threshold,
            semantic_threshold=self.semantic_threshold,
            min_length=self.min_claim_length,
            embedding_provider=self.embedding_provider,
        )

        reduced_claims: list[Claim] = []
        claim_id_map: dict[str, str] = {}
        for cluster in clusters:
            canonical_claim, local_map = _merge_claim_cluster(
                cluster, source_trust, degree_map, max_degree
            )
            reduced_claims.append(canonical_claim)
            claim_id_map.update(local_map)

        # Resolve conflicts (PreserveDispute keeps competing claims + adds CONTRADICTS edges).
        final_claims, contradiction_rels, conflicts = resolve_claim_conflicts(
            reduced_claims,
            source_trust,
            strategy=self.conflict_strategy,
            functional_predicates=self.single_valued_predicates,
        )

        surviving_nodes = {e.entity_id for e in entities} | {c.claim_id for c in final_claims}

        # Rewrite relation endpoints via claim_id_map and deduplicate parallel identical triples.
        dedup_rels: dict[tuple[str, str, str], Relation] = {}
        for rel in [*remapped_relations, *contradiction_rels]:
            new_src = claim_id_map.get(rel.source_id, rel.source_id)
            new_dst = claim_id_map.get(rel.target_id, rel.target_id)
            if new_src == new_dst:
                continue
            if new_src not in surviving_nodes or new_dst not in surviving_nodes:
                continue

            triple_key = (new_src, new_dst, rel.relation_type)
            if triple_key in dedup_rels:
                existing = dedup_rels[triple_key]
                dedup_rels[triple_key] = existing.model_copy(
                    update={
                        "confidence": max(existing.confidence, rel.confidence),
                        "weight": max(existing.weight, rel.weight),
                        "evidence": _dedup_evidence([*existing.evidence, *rel.evidence]),
                    }
                )
            else:
                dedup_rels[triple_key] = rel.model_copy(
                    update={"source_id": new_src, "target_id": new_dst}
                )

        final_relations = list(dedup_rels.values())

        compression_ratio = (
            round(1.0 - (len(final_claims) / raw_claims_count), 4) if raw_claims_count > 0 else 0.0
        )

        layer_meta = KnowledgeLayer(
            layer_id=layer_id,
            name=layer_name,
            tier=tier,
            parent_layer_ids=list(parent_layer_ids or []),
            created_at=utc_now(),
            pipeline_config_hash=pipeline_config_hash,
            stats={
                "sources": len(sources),
                "entities_before": raw_entities_count,
                "entities_after": len(entities),
                "claims_before": raw_claims_count,
                "claims_after": len(final_claims),
                "dropped_short_claims": len(dropped_short),
                "relations": len(final_relations),
                "conflicts": len(conflicts),
                "open_conflicts": sum(1 for cf in conflicts if cf.needs_review),
                "compression_ratio": compression_ratio,
            },
        )
        layer_data = LayerData(
            layer=layer_meta,
            sources=sources,
            entities=entities,
            claims=final_claims,
            relations=final_relations,
            conflicts=conflicts,
        )
        self.validator.validate(layer_data, strict=strict_validation)
        return layer_data
