"""Stackable knowledge layer manager with lineage DAG and set/overlay algebra."""

from __future__ import annotations

import networkx as nx

from knowledgereduce.models import (
    Claim,
    ConflictRecord,
    ConflictStrategy,
    Entity,
    Evidence,
    KnowledgeLayer,
    LayerData,
    LayerDiff,
    LayerTier,
    MappedBatch,
    MergeMode,
    Relation,
    SourceDocument,
    StackError,
    utc_now,
)
from knowledgereduce.reduce import (
    IntegrityValidator,
    deduplicate_and_merge_claims,
    deduplicate_relations,
    resolve_claim_conflicts,
)
from knowledgereduce.resolve import resolve_entities_and_remap
from knowledgereduce.storage.base import GraphStore, compute_layer_diff


def _dedup_evidence(items: list[Evidence]) -> list[Evidence]:
    seen: set[tuple[str, str | None, str, tuple[int, int] | None, str]] = set()
    result: list[Evidence] = []
    for ev in items:
        key = (ev.source_id, ev.uri, ev.excerpt, ev.char_span, ev.extractor_name)
        if key not in seen:
            seen.add(key)
            result.append(ev)
    return result


def _merge_entities(
    base: Entity,
    incoming: Entity,
    *,
    prefer_incoming: bool,
    strategy: ConflictStrategy,
) -> tuple[Entity, ConflictRecord | None]:
    aliases = list(
        dict.fromkeys(
            [*base.aliases, *incoming.aliases, base.canonical_name, incoming.canonical_name]
        )
    )
    merged_evidence = _dedup_evidence([*base.evidence, *incoming.evidence])
    merged_attrs = (
        {**base.attributes, **incoming.attributes}
        if prefer_incoming
        else {**incoming.attributes, **base.attributes}
    )
    merged_ext = {**base.external_ids, **incoming.external_ids}

    conflict: ConflictRecord | None = None
    if base.canonical_name != incoming.canonical_name:
        winner = incoming.canonical_name if prefer_incoming else base.canonical_name
        conflict = ConflictRecord(
            conflict_id=f"stack_entity_{base.entity_id}",
            target_type="entity_attribute",
            target_key=f"{base.entity_id}:canonical_name",
            candidates=[
                {"value": base.canonical_name, "source_ids": [e.source_id for e in base.evidence]},
                {
                    "value": incoming.canonical_name,
                    "source_ids": [e.source_id for e in incoming.evidence],
                },
            ],
            resolution_strategy=strategy,
            winning_value=winner,
            needs_review=(strategy == ConflictStrategy.PRESERVE_DISPUTE),
            resolution_notes="Conflicting canonical_name across stacked layers.",
        )

    winner_entity = incoming if prefer_incoming else base
    merged = Entity(
        entity_id=base.entity_id,
        canonical_name=winner_entity.canonical_name,
        entity_type=winner_entity.entity_type,
        aliases=[a for a in aliases if a != winner_entity.canonical_name],
        attributes=merged_attrs,
        evidence=merged_evidence,
        external_ids=merged_ext,
    )
    return merged, conflict


def _merge_claims(
    base: Claim,
    incoming: Claim,
    *,
    prefer_incoming: bool,
    strategy: ConflictStrategy,
) -> tuple[Claim, ConflictRecord | None]:
    winner = incoming if prefer_incoming else base
    loser = base if prefer_incoming else incoming

    merged_evidence = _dedup_evidence([*base.evidence, *incoming.evidence])
    merged_tags = list(dict.fromkeys([*base.tags, *incoming.tags]))
    merged_related = list(dict.fromkeys([*base.related_facts, *incoming.related_facts]))
    merged_from = list(dict.fromkeys([*base.merged_from, *incoming.merged_from]))

    conflict: ConflictRecord | None = None
    needs_review = base.needs_review or incoming.needs_review
    if base.statement.strip() != incoming.statement.strip():
        needs_review = needs_review or (strategy == ConflictStrategy.PRESERVE_DISPUTE)
        conflict = ConflictRecord(
            conflict_id=f"stack_claim_{base.claim_id}",
            target_type="claim",
            target_key=base.claim_id,
            candidates=[
                {
                    "statement": base.statement,
                    "source_id": base.source_id,
                    "reliability": int(base.reliability),
                    "confidence": base.confidence,
                },
                {
                    "statement": incoming.statement,
                    "source_id": incoming.source_id,
                    "reliability": int(incoming.reliability),
                    "confidence": incoming.confidence,
                },
            ],
            resolution_strategy=strategy,
            winning_value=winner.statement,
            winning_source_id=winner.source_id or None,
            needs_review=(strategy == ConflictStrategy.PRESERVE_DISPUTE),
            resolution_notes="Conflicting claim statement across stacked layers.",
        )

    merged = Claim(
        claim_id=base.claim_id,
        statement=winner.statement,
        category=winner.category,
        tags=merged_tags,
        contextual_notes=winner.contextual_notes or loser.contextual_notes,
        recorded_at=min(base.recorded_at, incoming.recorded_at),
        updated_at=max(base.updated_at, incoming.updated_at),
        published_at=winner.published_at or loser.published_at,
        reliability=max(base.reliability, incoming.reliability)
        if strategy != ConflictStrategy.LATEST_TIMESTAMP
        else winner.reliability,
        source_id=winner.source_id,
        source_title=winner.source_title or loser.source_title,
        author_creator=winner.author_creator or loser.author_creator,
        url_reference=winner.url_reference or loser.url_reference,
        access_level=winner.access_level,
        usage_count=max(base.usage_count, incoming.usage_count),
        related_facts=merged_related,
        confidence=max(base.confidence, incoming.confidence),
        subject_id=winner.subject_id or loser.subject_id,
        predicate=winner.predicate or loser.predicate,
        object_id=winner.object_id or loser.object_id,
        object_literal=winner.object_literal or loser.object_literal,
        evidence=merged_evidence,
        merged_from=merged_from,
        needs_review=needs_review,
    )
    return merged, conflict


def _merge_relations(base: Relation, incoming: Relation, *, prefer_incoming: bool) -> Relation:
    winner = incoming if prefer_incoming else base
    return Relation(
        relation_id=base.relation_id,
        source_id=winner.source_id,
        target_id=winner.target_id,
        relation_type=winner.relation_type,
        confidence=max(base.confidence, incoming.confidence),
        weight=max(base.weight, incoming.weight),
        evidence=_dedup_evidence([*base.evidence, *incoming.evidence]),
        attributes={**base.attributes, **incoming.attributes}
        if prefer_incoming
        else {**incoming.attributes, **base.attributes},
    )


class StackManager:
    """Manages immutable knowledge layer stacking, set algebra, and lineage."""

    def __init__(self, store: GraphStore) -> None:
        self.store = store

    def build_lineage_graph(self) -> nx.DiGraph:
        """Build a directed acyclic graph of layer parent-child relationships."""
        dag = nx.DiGraph()
        layers = self.store.list_layers()
        for layer in layers:
            dag.add_node(
                layer.layer_id,
                name=layer.name,
                version=layer.version,
                tier=str(layer.tier),
                merge_mode=str(layer.merge_mode) if layer.merge_mode else "",
                created_at=layer.created_at.isoformat(),
            )
        for layer in layers:
            for parent_id in layer.parent_layer_ids:
                dag.add_edge(parent_id, layer.layer_id)
        return dag

    def get_ancestors(self, layer_id: str) -> list[str]:
        """Return sorted ancestor layer IDs for *layer_id*."""
        if not self.store.layer_exists(layer_id):
            raise StackError(f"Layer {layer_id!r} not found.")
        dag = self.build_lineage_graph()
        return sorted(nx.ancestors(dag, layer_id))

    def get_descendants(self, layer_id: str) -> list[str]:
        """Return sorted descendant layer IDs for *layer_id*."""
        if not self.store.layer_exists(layer_id):
            raise StackError(f"Layer {layer_id!r} not found.")
        dag = self.build_lineage_graph()
        return sorted(nx.descendants(dag, layer_id))

    def diff_layers(self, left_layer_id: str, right_layer_id: str) -> LayerDiff:
        """Compute structural differences between two layers."""
        if not self.store.layer_exists(left_layer_id):
            raise StackError(f"Layer {left_layer_id!r} not found.")
        if not self.store.layer_exists(right_layer_id):
            raise StackError(f"Layer {right_layer_id!r} not found.")
        return compute_layer_diff(
            self.store.load_layer(left_layer_id),
            self.store.load_layer(right_layer_id),
        )

    def stack_overlay(
        self,
        base_layer_id: str,
        overlay_layer_id: str,
        *,
        target_layer_id: str,
        target_name: str | None = None,
        tier: LayerTier = LayerTier.STACKED,
        conflict_strategy: ConflictStrategy = ConflictStrategy.PRESERVE_DISPUTE,
        reconcile: bool = False,
        deduplicate_claims: bool = True,
        lexical_threshold: float = 0.88,
        semantic_threshold: float = 0.84,
        min_claim_length: int = 0,
        overwrite: bool = False,
    ) -> LayerData:
        """Compose *overlay_layer_id* on top of *base_layer_id* non-destructively."""
        return self.merge_layers(
            [base_layer_id, overlay_layer_id],
            target_layer_id=target_layer_id,
            target_name=target_name,
            mode=MergeMode.OVERLAY,
            tier=tier,
            conflict_strategy=conflict_strategy,
            reconcile=reconcile,
            deduplicate_claims=deduplicate_claims,
            lexical_threshold=lexical_threshold,
            semantic_threshold=semantic_threshold,
            min_claim_length=min_claim_length,
            overwrite=overwrite,
        )

    def merge_layers(
        self,
        layer_ids: list[str],
        *,
        target_layer_id: str,
        target_name: str | None = None,
        mode: MergeMode = MergeMode.UNION,
        tier: LayerTier = LayerTier.STACKED,
        conflict_strategy: ConflictStrategy = ConflictStrategy.PRESERVE_DISPUTE,
        reconcile: bool = False,
        deduplicate_claims: bool = True,
        lexical_threshold: float = 0.88,
        semantic_threshold: float = 0.84,
        min_claim_length: int = 0,
        overwrite: bool = False,
    ) -> LayerData:
        """Combine multiple immutable layers using *mode* without mutating inputs."""
        if not layer_ids:
            raise StackError("At least one source layer_id is required to merge.")
        if reconcile and mode not in {MergeMode.UNION, MergeMode.OVERLAY}:
            raise StackError("reconcile=True is only supported for UNION and OVERLAY merge modes.")
        if len(layer_ids) < 2 and mode in {
            MergeMode.OVERLAY,
            MergeMode.INTERSECTION,
            MergeMode.DIFFERENCE,
        }:
            raise StackError(f"MergeMode.{mode.name} requires at least two input layers.")

        if self.store.layer_exists(target_layer_id) and not overwrite:
            raise StackError(
                f"Target layer {target_layer_id!r} already exists (pass overwrite=True)."
            )

        inputs: list[LayerData] = []
        for lid in layer_ids:
            if not self.store.layer_exists(lid):
                raise StackError(f"Input layer {lid!r} does not exist.")
            inputs.append(self.store.load_layer(lid))

        sources: dict[str, SourceDocument] = {}
        entities: dict[str, Entity] = {}
        claims: dict[str, Claim] = {}
        relations: dict[str, Relation] = {}
        conflicts: dict[str, ConflictRecord] = {}

        if mode in {MergeMode.UNION, MergeMode.OVERLAY}:
            prefer_incoming = mode == MergeMode.OVERLAY
            for layer_data in inputs:
                for src in layer_data.sources:
                    if src.source_id not in sources or prefer_incoming:
                        sources[src.source_id] = src
                for ent in layer_data.entities:
                    if ent.entity_id in entities:
                        merged_ent, conflict = _merge_entities(
                            entities[ent.entity_id],
                            ent,
                            prefer_incoming=prefer_incoming,
                            strategy=conflict_strategy,
                        )
                        entities[ent.entity_id] = merged_ent
                        if conflict is not None:
                            conflicts[conflict.conflict_id] = conflict
                    else:
                        entities[ent.entity_id] = ent
                for clm in layer_data.claims:
                    if clm.claim_id in claims:
                        merged_clm, conflict = _merge_claims(
                            claims[clm.claim_id],
                            clm,
                            prefer_incoming=prefer_incoming,
                            strategy=conflict_strategy,
                        )
                        claims[clm.claim_id] = merged_clm
                        if conflict is not None:
                            conflicts[conflict.conflict_id] = conflict
                    else:
                        claims[clm.claim_id] = clm
                for rel in layer_data.relations:
                    if rel.relation_id in relations:
                        relations[rel.relation_id] = _merge_relations(
                            relations[rel.relation_id],
                            rel,
                            prefer_incoming=prefer_incoming,
                        )
                    else:
                        relations[rel.relation_id] = rel
                for cf in layer_data.conflicts:
                    conflicts[cf.conflict_id] = cf

        elif mode == MergeMode.INTERSECTION:
            common_entity_ids = set.intersection(
                *({e.entity_id for e in ld.entities} for ld in inputs)
            )
            common_claim_ids = set.intersection(*({c.claim_id for c in ld.claims} for ld in inputs))
            common_rel_ids = set.intersection(
                *({r.relation_id for r in ld.relations} for ld in inputs)
            )
            common_source_ids = set.intersection(
                *({s.source_id for s in ld.sources} for ld in inputs)
            )

            for ld in inputs:
                for src in ld.sources:
                    if src.source_id in common_source_ids and src.source_id not in sources:
                        sources[src.source_id] = src
                for ent in ld.entities:
                    if ent.entity_id in common_entity_ids:
                        if ent.entity_id in entities:
                            merged_ent, _ = _merge_entities(
                                entities[ent.entity_id],
                                ent,
                                prefer_incoming=False,
                                strategy=conflict_strategy,
                            )
                            entities[ent.entity_id] = merged_ent
                        else:
                            entities[ent.entity_id] = ent
                for clm in ld.claims:
                    if clm.claim_id in common_claim_ids:
                        if clm.claim_id in claims:
                            merged_clm, _ = _merge_claims(
                                claims[clm.claim_id],
                                clm,
                                prefer_incoming=False,
                                strategy=conflict_strategy,
                            )
                            claims[clm.claim_id] = merged_clm
                        else:
                            claims[clm.claim_id] = clm
                for rel in ld.relations:
                    if rel.relation_id in common_rel_ids:
                        if rel.relation_id in relations:
                            relations[rel.relation_id] = _merge_relations(
                                relations[rel.relation_id], rel, prefer_incoming=False
                            )
                        else:
                            relations[rel.relation_id] = rel

        elif mode == MergeMode.DIFFERENCE:
            base = inputs[0]
            sub_entity_ids = {e.entity_id for ld in inputs[1:] for e in ld.entities}
            sub_claim_ids = {c.claim_id for ld in inputs[1:] for c in ld.claims}
            sub_rel_ids = {r.relation_id for ld in inputs[1:] for r in ld.relations}
            sub_conflict_ids = {cf.conflict_id for ld in inputs[1:] for cf in ld.conflicts}

            sources = {s.source_id: s for s in base.sources}
            entities = {e.entity_id: e for e in base.entities if e.entity_id not in sub_entity_ids}
            claims = {c.claim_id: c for c in base.claims if c.claim_id not in sub_claim_ids}
            relations = {
                r.relation_id: r for r in base.relations if r.relation_id not in sub_rel_ids
            }
            conflicts = {
                cf.conflict_id: cf
                for cf in base.conflicts
                if cf.conflict_id not in sub_conflict_ids
            }

        # Filter out any relation whose source or target node does not survive (no dangling edges).
        surviving_nodes = set(entities.keys()) | set(claims.keys())
        valid_relations = [
            rel
            for rel in relations.values()
            if rel.source_id in surviving_nodes and rel.target_id in surviving_nodes
        ]

        if reconcile:
            rec_entities, remapped_claims, remapped_rels, _rec_sources, _id_map = (
                resolve_entities_and_remap(
                    [
                        MappedBatch(
                            entities=list(entities.values()),
                            claims=list(claims.values()),
                            relations=valid_relations,
                        )
                    ],
                    lexical_threshold=lexical_threshold,
                )
            )
            source_trust = {s.source_id: s.trust_weight for s in sources.values()}
            claim_id_map: dict[str, str] = {}
            claims_for_conflicts = remapped_claims
            if deduplicate_claims and len(remapped_claims) > 1:
                claims_for_conflicts, claim_id_map, _dropped = deduplicate_and_merge_claims(
                    remapped_claims,
                    remapped_rels,
                    source_trust,
                    lexical_threshold=lexical_threshold,
                    semantic_threshold=semantic_threshold,
                    min_length=min_claim_length,
                )

            final_claims, contra_rels, new_conflicts = resolve_claim_conflicts(
                claims_for_conflicts,
                source_trust,
                strategy=conflict_strategy,
            )
            entities = {e.entity_id: e for e in rec_entities}
            claims = {c.claim_id: c for c in final_claims}
            rec_nodes = set(entities.keys()) | set(claims.keys())

            valid_relations = deduplicate_relations(
                [*remapped_rels, *contra_rels],
                rec_nodes,
                claim_id_map=claim_id_map,
            )

            if claim_id_map:
                for cid_key, existing_cf in list(conflicts.items()):
                    updated_cands = []
                    changed = False
                    for cand in existing_cf.candidates:
                        cids = cand.get("claim_ids")
                        if isinstance(cids, list):
                            remapped_cids = list(
                                dict.fromkeys(claim_id_map.get(str(x), str(x)) for x in cids)
                            )
                            if remapped_cids != cids:
                                cand = {**cand, "claim_ids": remapped_cids}
                                changed = True
                        updated_cands.append(cand)
                    if changed:
                        conflicts[cid_key] = existing_cf.model_copy(
                            update={"candidates": updated_cands}
                        )

            for cf in new_conflicts:
                if cf.conflict_id not in conflicts or conflicts[cf.conflict_id].needs_review:
                    conflicts[cf.conflict_id] = cf

        new_layer = KnowledgeLayer(
            layer_id=target_layer_id,
            name=target_name or f"{mode.value}({', '.join(layer_ids)})",
            tier=tier,
            parent_layer_ids=list(dict.fromkeys(layer_ids)),
            merge_mode=mode,
            created_at=utc_now(),
            stats={
                "sources": len(sources),
                "entities": len(entities),
                "claims": len(claims),
                "relations": len(valid_relations),
                "conflicts": len(conflicts),
            },
        )
        result = LayerData(
            layer=new_layer,
            sources=list(sources.values()),
            entities=list(entities.values()),
            claims=list(claims.values()),
            relations=valid_relations,
            conflicts=list(conflicts.values()),
        )
        if reconcile:
            IntegrityValidator().validate(result, strict=True)
        self.store.save_layer(result, overwrite=overwrite)
        return result
