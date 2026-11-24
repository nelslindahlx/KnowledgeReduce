"""Human- and LLM-readable Markdown Knowledge Brief exporter."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from knowledgereduce.models import LayerData, StorageError
from knowledgereduce.security import ensure_within_base


def _md_cell(text: str, *, max_len: int | None = None) -> str:
    """Escape pipes and collapse whitespace for valid GFM table cells."""
    cleaned = " ".join(text.split())
    if max_len is not None and len(cleaned) > max_len:
        cutoff = max(0, max_len - 3)
        cleaned = cleaned[:cutoff].rstrip() + "..."
    return cleaned.replace("|", "\\|")


def render_layer_markdown(
    layer_data: LayerData,
    *,
    max_entities: int = 50,
    max_claims: int = 100,
    max_relations: int = 100,
) -> str:
    """Render *layer_data* as a deterministic, provenance-cited Markdown Knowledge Brief."""
    if max_entities < 0 or max_claims < 0 or max_relations < 0:
        raise StorageError("max_entities, max_claims, and max_relations must be >= 0.")

    layer = layer_data.layer
    entity_names = {e.entity_id: e.canonical_name for e in layer_data.entities}
    sources_by_id = {s.source_id: s for s in layer_data.sources}

    degree: dict[str, int] = defaultdict(int)
    for rel in layer_data.relations:
        degree[rel.source_id] += 1
        degree[rel.target_id] += 1

    mean_quality = (
        round(sum(c.quality_score for c in layer_data.claims) / len(layer_data.claims), 2)
        if layer_data.claims
        else 0.0
    )
    open_conflicts = sum(1 for cf in layer_data.conflicts if cf.needs_review)
    parents = ", ".join(layer.parent_layer_ids) if layer.parent_layer_ids else "None"

    lines: list[str] = [
        f"# {_md_cell(layer.name)}",
        "",
        "## Layer Summary",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Layer ID | `{_md_cell(layer.layer_id)}` |",
        f"| Tier | `{layer.tier.value}` |",
        f"| Version | `{layer.version}` |",
        f"| Parents | {_md_cell(parents)} |",
        f"| Created At | `{layer.created_at.isoformat()}` |",
        f"| Sources | {len(layer_data.sources)} |",
        f"| Entities | {len(layer_data.entities)} |",
        f"| Claims | {len(layer_data.claims)} |",
        f"| Relations | {len(layer_data.relations)} |",
        f"| Open Conflicts | {open_conflicts} / {len(layer_data.conflicts)} |",
        f"| Mean Quality Score | {mean_quality:.2f} |",
        "",
        "## Top Entities",
        "",
    ]

    ranked_entities = sorted(
        layer_data.entities,
        key=lambda e: (-degree.get(e.entity_id, 0), e.canonical_name.lower(), e.entity_id),
    )[:max_entities]
    if ranked_entities:
        lines.extend(
            [
                "| Entity | Type | Aliases | Degree |",
                "| --- | --- | --- | --- |",
            ]
        )
        for ent in ranked_entities:
            aliases = ", ".join(ent.aliases[:5]) if ent.aliases else "-"
            lines.append(
                "| "
                f"{_md_cell(ent.canonical_name, max_len=120)} | "
                f"`{_md_cell(ent.entity_type)}` | "
                f"{_md_cell(aliases, max_len=120)} | "
                f"{degree.get(ent.entity_id, 0)} |"
            )
    else:
        lines.append("_No entities recorded._")

    lines.extend(["", "## Grounded Knowledge Triples", ""])
    triple_map: dict[tuple[str, str, str], float] = {}
    for rel in layer_data.relations:
        if rel.relation_type in {"MENTIONS", "CONTRADICTS"}:
            continue
        subj = entity_names.get(rel.source_id, rel.source_id)
        obj = entity_names.get(rel.target_id, rel.target_id)
        key = (subj, rel.relation_type, obj)
        triple_map[key] = max(triple_map.get(key, 0.0), rel.confidence)

    for clm in layer_data.claims:
        if (
            clm.subject_id
            and clm.predicate
            and (clm.object_id is not None or clm.object_literal is not None)
        ):
            subj = entity_names.get(clm.subject_id, clm.subject_id)
            obj = (
                entity_names.get(clm.object_id, clm.object_id)
                if clm.object_id is not None
                else (clm.object_literal or "")
            )
            key = (subj, clm.predicate, obj)
            triple_map[key] = max(triple_map.get(key, 0.0), clm.confidence)

    sorted_triples = sorted(
        triple_map.items(),
        key=lambda item: (-item[1], item[0][0].lower(), item[0][1], item[0][2].lower()),
    )[:max_relations]
    if sorted_triples:
        lines.extend(
            [
                "| Subject | Predicate | Object | Confidence |",
                "| --- | --- | --- | --- |",
            ]
        )
        for (subj, pred, obj), conf in sorted_triples:
            lines.append(
                f"| {_md_cell(subj, max_len=80)} | `{_md_cell(pred)}` | "
                f"{_md_cell(obj, max_len=120)} | {conf:.2f} |"
            )
    else:
        lines.append("_No grounded triples recorded._")

    lines.extend(["", "## Key Claims", ""])
    ranked_claims = sorted(
        layer_data.claims,
        key=lambda c: (-c.quality_score, -int(c.reliability), -c.confidence, c.claim_id),
    )[:max_claims]
    if ranked_claims:
        for idx, clm in enumerate(ranked_claims, start=1):
            review_badge = "**[NEEDS REVIEW]** " if clm.needs_review else ""
            src_doc = sources_by_id.get(clm.source_id)
            src_label = (
                clm.source_title
                or (src_doc.title if src_doc and src_doc.title else "")
                or clm.source_id
                or "unknown"
            )
            ref = clm.url_reference or (src_doc.uri if src_doc is not None else "")
            cite = f"{_md_cell(src_label, max_len=80)}" + (f" ({ref})" if ref else "")
            tag_str = ", ".join(f"`{t}`" for t in clm.tags[:6]) if clm.tags else "none"
            stmt = " ".join(clm.statement.split())
            lines.append(f"{idx}. {review_badge}{stmt}")
            lines.append(
                f"   - Reliability: `{clm.reliability.name}` | Quality: `{clm.quality_score:.1f}` "
                f"| Tags: {tag_str} | Source: {cite}"
            )
    else:
        lines.append("_No claims recorded._")

    lines.extend(["", "## Conflicts", ""])
    if layer_data.conflicts:
        ordered_conflicts = sorted(
            layer_data.conflicts,
            key=lambda cf: (not cf.needs_review, cf.target_key, cf.conflict_id),
        )
        lines.extend(
            [
                "| Target | Status | Strategy | Winning Value | Candidates |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for cf in ordered_conflicts:
            status = "Open" if cf.needs_review else "Resolved"
            win_val = str(cf.winning_value) if cf.winning_value is not None else "-"
            cand_vals = ", ".join(
                str(c.get("value") or c.get("statement") or "?") for c in cf.candidates
            )
            lines.append(
                f"| `{_md_cell(cf.target_key)}` | `{status}` | "
                f"`{cf.resolution_strategy.value}` | {_md_cell(win_val, max_len=80)} | "
                f"{_md_cell(cand_vals, max_len=120)} |"
            )
    else:
        lines.append("_No conflicts recorded._")

    lines.extend(["", "## Sources", ""])
    ordered_sources = sorted(layer_data.sources, key=lambda s: (-s.trust_weight, s.source_id))
    if ordered_sources:
        lines.extend(
            [
                "| Source ID | Title | Type | Trust | URI |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for src in ordered_sources:
            title = src.title or src.source_id
            lines.append(
                f"| `{_md_cell(src.source_id)}` | {_md_cell(title, max_len=100)} | "
                f"`{src.source_type.value}` | {src.trust_weight:.2f} | "
                f"{_md_cell(src.uri, max_len=120)} |"
            )
    else:
        lines.append("_No sources recorded._")

    return "\n".join(lines).rstrip() + "\n"


def export_layer_markdown(
    layer_data: LayerData,
    output_path: Path | str,
    *,
    base_dir: Path | str | None = None,
    max_entities: int = 50,
    max_claims: int = 100,
    max_relations: int = 100,
) -> Path:
    """Export *layer_data* as a Markdown Knowledge Brief file."""
    target = (
        ensure_within_base(output_path, base_dir)
        if base_dir is not None
        else Path(output_path).resolve()
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    rendered = render_layer_markdown(
        layer_data,
        max_entities=max_entities,
        max_claims=max_claims,
        max_relations=max_relations,
    )
    target.write_text(rendered, encoding="utf-8")
    return target
