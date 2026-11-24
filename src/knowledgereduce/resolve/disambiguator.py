"""Entity disambiguation and atomic endpoint remapping across mapped batches."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence

from rapidfuzz import fuzz

from knowledgereduce.models import (
    Claim,
    Entity,
    Evidence,
    MappedBatch,
    Relation,
    SourceDocument,
)
from knowledgereduce.resolve.blocking import DisjointSet

_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]+")
_HONORIFIC_PREFIX_RE = re.compile(r"^(?:dr|prof|mr|mrs|ms)\.?\s+")
_TYPE_SPECIFICITY: dict[str, int] = {
    "DATE": 5,
    "GPE": 4,
    "ORG": 3,
    "PERSON": 2,
    "CONCEPT": 1,
}


def _norm_entity_key(name: str) -> str:
    lowered = _HONORIFIC_PREFIX_RE.sub("", name.strip().lower())
    return re.sub(r"\s+", " ", _NON_ALNUM_RE.sub(" ", lowered)).strip()


def _dedup_evidence(items: Sequence[Evidence]) -> list[Evidence]:
    seen: set[tuple[str, str | None, str, tuple[int, int] | None, str]] = set()
    out: list[Evidence] = []
    for ev in items:
        key = (ev.source_id, ev.uri, ev.excerpt, ev.char_span, ev.extractor_name)
        if key not in seen:
            seen.add(key)
            out.append(ev)
    return out


def _initial_token_match(tok_a: str, tok_b: str) -> bool:
    return (
        tok_a == tok_b
        or (len(tok_a) == 1 and tok_b.startswith(tok_a))
        or (len(tok_b) == 1 and tok_a.startswith(tok_b))
    )


def _names_match_with_initials(name_a: str, name_b: str) -> bool:
    """Detect initial-abbreviated matches like 'J. Smith' vs 'John Smith' or 'Charles Carlsen' vs 'Charles J. Carlsen'."""
    toks_a = _norm_entity_key(name_a).split()
    toks_b = _norm_entity_key(name_b).split()
    if len(toks_a) < 2 or len(toks_b) < 2:
        return False
    if toks_a[-1] != toks_b[-1] or len(toks_a[-1]) < 2:
        return False

    given_a = toks_a[:-1]
    given_b = toks_b[:-1]
    if len(given_a) == len(given_b):
        return all(_initial_token_match(ta, tb) for ta, tb in zip(given_a, given_b, strict=True))

    if abs(len(given_a) - len(given_b)) == 1:
        short, longer = (given_a, given_b) if len(given_a) < len(given_b) else (given_b, given_a)
        for drop_idx, tok in enumerate(longer):
            if len(tok) != 1:
                continue
            reduced = [*longer[:drop_idx], *longer[drop_idx + 1 :]]
            if all(
                _initial_token_match(s_tok, r_tok)
                for s_tok, r_tok in zip(short, reduced, strict=True)
            ):
                return True

    return False


def _are_entities_equivalent(
    ent_a: Entity,
    ent_b: Entity,
    cutoff: float,
    *,
    merge_exact_cross_type: bool = True,
) -> bool:
    same_or_concept = ent_a.entity_type == ent_b.entity_type or "CONCEPT" in {
        ent_a.entity_type,
        ent_b.entity_type,
    }
    key_a = _norm_entity_key(ent_a.canonical_name)
    key_b = _norm_entity_key(ent_b.canonical_name)

    names_a = {key_a} | {_norm_entity_key(a) for a in ent_a.aliases}
    names_b = {key_b} | {_norm_entity_key(a) for a in ent_b.aliases}
    names_a.discard("")
    names_b.discard("")

    if names_a & names_b:
        if same_or_concept:
            return True
        if (
            merge_exact_cross_type
            and key_a
            and key_a == key_b
            and (ent_a.entity_type == "DATE") == (ent_b.entity_type == "DATE")
        ):
            return True

    if ent_a.entity_type != ent_b.entity_type:
        return False

    if not key_a or not key_b:
        return False

    if _names_match_with_initials(key_a, key_b):
        return True

    return bool(fuzz.token_sort_ratio(key_a, key_b) >= cutoff)


def _merge_entity_group(group: Sequence[Entity]) -> Entity:
    group_sorted = sorted(
        group,
        key=lambda e: (
            _TYPE_SPECIFICITY.get(e.entity_type, 2),
            len(e.evidence),
            len(e.canonical_name),
            e.entity_id,
        ),
        reverse=True,
    )
    winner = group_sorted[0]
    all_aliases = list(
        dict.fromkeys([a for e in group_sorted for a in [e.canonical_name, *e.aliases]])
    )
    merged_attrs: dict[str, object] = {}
    merged_ext: dict[str, str] = {}
    all_ev: list[Evidence] = []
    for e in reversed(group_sorted):
        merged_attrs.update(e.attributes)
        merged_ext.update(e.external_ids)
        all_ev.extend(e.evidence)
    return Entity(
        entity_id=winner.entity_id,
        canonical_name=winner.canonical_name,
        entity_type=winner.entity_type,
        aliases=[a for a in all_aliases if a != winner.canonical_name],
        attributes=merged_attrs,
        evidence=_dedup_evidence(all_ev),
        external_ids=merged_ext,
    )


def resolve_entities_and_remap(
    batches: Sequence[MappedBatch],
    *,
    lexical_threshold: float = 0.88,
    merge_exact_cross_type: bool = True,
) -> tuple[list[Entity], list[Claim], list[Relation], list[SourceDocument], dict[str, str]]:
    """Disambiguate entities across batches and atomically rewrite all Claim/Relation endpoints.

    Returns ``(entities, claims, relations, sources, entity_id_map)``.
    """
    sources_by_id: dict[str, SourceDocument] = {}
    raw_entities: list[Entity] = []
    raw_claims: list[Claim] = []
    raw_relations: list[Relation] = []

    for batch in batches:
        if batch.source_document is not None:
            doc = batch.source_document
            existing = sources_by_id.get(doc.source_id)
            if existing is None or doc.trust_weight > existing.trust_weight:
                sources_by_id[doc.source_id] = doc
        raw_entities.extend(batch.entities)
        raw_claims.extend(batch.claims)
        raw_relations.extend(batch.relations)

    if not raw_entities:
        return [], raw_claims, raw_relations, list(sources_by_id.values()), {}

    # Merge exact entity_id duplicates first in O(N).
    by_id: dict[str, list[Entity]] = defaultdict(list)
    for ent in raw_entities:
        by_id[ent.entity_id].append(ent)

    unique_entities = [_merge_entity_group(ent_group) for ent_group in by_id.values()]

    # Block entities by normalized key, surname/last-token, and aliases for sub-quadratic resolution.
    n = len(unique_entities)
    dsu = DisjointSet(n)
    block_index: dict[str, list[int]] = defaultdict(list)
    for idx, ent in enumerate(unique_entities):
        for name_variant in [ent.canonical_name, *ent.aliases]:
            norm = _norm_entity_key(name_variant)
            if not norm:
                continue
            block_index[f"exact:{norm}"].append(idx)
            toks = norm.split()
            if toks:
                block_index[f"last:{ent.entity_type}:{toks[-1]}"].append(idx)
                block_index[f"first3:{ent.entity_type}:{toks[0][:3]}"].append(idx)

    cutoff = lexical_threshold * 100.0
    checked_pairs: set[tuple[int, int]] = set()
    for members in block_index.values():
        if len(members) < 2 or len(members) > 250:
            continue
        for i_pos in range(len(members)):
            i = members[i_pos]
            for j_pos in range(i_pos + 1, len(members)):
                j = members[j_pos]
                pair = (i, j) if i < j else (j, i)
                if pair in checked_pairs or dsu.find(i) == dsu.find(j):
                    continue
                checked_pairs.add(pair)
                if _are_entities_equivalent(
                    unique_entities[i],
                    unique_entities[j],
                    cutoff,
                    merge_exact_cross_type=merge_exact_cross_type,
                ):
                    dsu.union(i, j)

    canonical_entities: list[Entity] = []
    entity_id_map: dict[str, str] = {}

    for group_indices in dsu.groups():
        group = [unique_entities[idx] for idx in group_indices]
        merged = _merge_entity_group(group)
        for member in group:
            entity_id_map[member.entity_id] = merged.entity_id
        canonical_entities.append(merged)

    remapped_claims: list[Claim] = []
    for clm in raw_claims:
        new_subj = entity_id_map.get(clm.subject_id, clm.subject_id) if clm.subject_id else None
        new_obj = entity_id_map.get(clm.object_id, clm.object_id) if clm.object_id else None
        if new_subj != clm.subject_id or new_obj != clm.object_id:
            remapped_claims.append(
                clm.model_copy(update={"subject_id": new_subj, "object_id": new_obj})
            )
        else:
            remapped_claims.append(clm)

    remapped_relations: list[Relation] = []
    for rel in raw_relations:
        new_src = entity_id_map.get(rel.source_id, rel.source_id)
        new_dst = entity_id_map.get(rel.target_id, rel.target_id)
        if new_src == new_dst:
            continue
        if new_src != rel.source_id or new_dst != rel.target_id:
            remapped_relations.append(
                rel.model_copy(update={"source_id": new_src, "target_id": new_dst})
            )
        else:
            remapped_relations.append(rel)

    return (
        canonical_entities,
        remapped_claims,
        remapped_relations,
        list(sources_by_id.values()),
        entity_id_map,
    )
