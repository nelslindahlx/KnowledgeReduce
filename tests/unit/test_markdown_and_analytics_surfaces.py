"""Unit and CLI tests for Markdown export, layer introspection, and graph analytics."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from knowledgereduce.cli import app
from knowledgereduce.export import export_layer_markdown, render_layer_markdown
from knowledgereduce.models import (
    Claim,
    ConflictRecord,
    ConflictStrategy,
    Entity,
    Evidence,
    KnowledgeLayer,
    LayerData,
    LayerTier,
    PathSecurityError,
    Relation,
    ReliabilityRating,
    SourceDocument,
    SourceType,
    StorageError,
)
from knowledgereduce.storage import DuckDBParquetStore


def _build_rich_layer(
    layer_id: str = "md-rich",
    *,
    parents: list[str] | None = None,
) -> LayerData:
    sources = [
        SourceDocument(
            source_id="src-book",
            uri="https://www.civichonors.com/p/the-book",
            source_type=SourceType.WEB,
            title="Civic Honors | The Book",
            trust_weight=0.9,
            content="Civic Honors was published in 2006.",
        )
    ]
    entities = [
        Entity(
            entity_id="ent-nels",
            canonical_name="Nels Lindahl | Author",
            entity_type="PERSON",
            aliases=["Dr. Nels Lindahl"],
            evidence=[Evidence(source_id="src-book", excerpt="Nels Lindahl")],
        ),
        Entity(
            entity_id="ent-ch",
            canonical_name="Civic Honors",
            entity_type="ORG",
            aliases=["Civic Honors Book"],
            evidence=[Evidence(source_id="src-book", excerpt="Civic Honors")],
        ),
        Entity(
            entity_id="ent-ku",
            canonical_name="University of Kansas",
            entity_type="ORG",
            evidence=[Evidence(source_id="src-book", excerpt="University of Kansas")],
        ),
    ]
    claims = [
        Claim(
            claim_id="clm-1",
            statement="Civic Honors was published in 2006\nfor student engagement.",
            category="Publication",
            tags=["civic", "book"],
            reliability=ReliabilityRating.VERIFIED,
            confidence=0.95,
            source_id="src-book",
            source_title="Civic Honors | Book",
            subject_id="ent-ch",
            predicate="PUBLISHED_IN",
            object_literal="2006",
            evidence=[Evidence(source_id="src-book", excerpt="published in 2006")],
        ),
        Claim(
            claim_id="clm-2",
            statement="Dr. Nels Lindahl studied at the University of Kansas in 2002.",
            category="Education",
            tags=["ku"],
            reliability=ReliabilityRating.LIKELY_TRUE,
            confidence=0.85,
            source_id="src-book",
            subject_id="ent-nels",
            predicate="STUDIED_AT",
            object_id="ent-ku",
            needs_review=True,
            evidence=[Evidence(source_id="src-book", excerpt="University of Kansas in 2002")],
        ),
    ]
    relations = [
        Relation(
            relation_id="rel-1",
            source_id="ent-nels",
            target_id="ent-ch",
            relation_type="AUTHORED",
            confidence=0.95,
        ),
        Relation(
            relation_id="rel-2",
            source_id="clm-1",
            target_id="ent-ch",
            relation_type="MENTIONS",
            confidence=0.9,
        ),
        Relation(
            relation_id="rel-3",
            source_id="clm-2",
            target_id="ent-nels",
            relation_type="MENTIONS",
            confidence=0.9,
        ),
        Relation(
            relation_id="rel-4",
            source_id="clm-2",
            target_id="ent-ku",
            relation_type="MENTIONS",
            confidence=0.9,
        ),
    ]
    conflicts = [
        ConflictRecord(
            conflict_id="cf-1",
            target_type="claim",
            target_key="ent-ch::PUBLISHED_IN",
            candidates=[{"value": "2006"}, {"value": "2020"}],
            resolution_strategy=ConflictStrategy.PRESERVE_DISPUTE,
            winning_value="2006",
            needs_review=True,
        )
    ]
    return LayerData(
        layer=KnowledgeLayer(
            layer_id=layer_id,
            name="Civic Honors | Brief",
            tier=LayerTier.REDUCED,
            parent_layer_ids=parents or [],
        ),
        sources=sources,
        entities=entities,
        claims=claims,
        relations=relations,
        conflicts=conflicts,
    )


def test_markdown_export_renders_escaped_provenance_and_guards_paths(tmp_path: Path) -> None:
    layer = _build_rich_layer()
    rendered_a = render_layer_markdown(layer)
    rendered_b = render_layer_markdown(layer)
    assert rendered_a == rendered_b

    assert rendered_a.startswith("# Civic Honors \\| Brief\n")
    assert "## Top Entities" in rendered_a
    assert "Nels Lindahl \\| Author" in rendered_a
    assert "## Grounded Knowledge Triples" in rendered_a
    assert "`AUTHORED`" in rendered_a
    assert "`PUBLISHED_IN`" in rendered_a
    assert "## Key Claims" in rendered_a
    assert "**[NEEDS REVIEW]**" in rendered_a
    assert "Civic Honors was published in 2006 for student engagement." in rendered_a
    assert "## Conflicts" in rendered_a
    assert "`Open`" in rendered_a
    assert "## Sources" in rendered_a

    out_path = export_layer_markdown(layer, "briefs/civic.md", base_dir=tmp_path)
    assert out_path.is_file()
    assert out_path.read_text(encoding="utf-8") == rendered_a

    # Empty layer renders cleanly without errors.
    empty = LayerData(layer=KnowledgeLayer(layer_id="empty", name="Empty Layer"))
    empty_md = render_layer_markdown(empty)
    assert "_No entities recorded._" in empty_md
    assert "_No grounded triples recorded._" in empty_md
    assert "_No claims recorded._" in empty_md
    assert "_No conflicts recorded._" in empty_md
    assert "_No sources recorded._" in empty_md

    with pytest.raises(PathSecurityError):
        export_layer_markdown(layer, "../escape.md", base_dir=tmp_path)
    with pytest.raises(StorageError):
        render_layer_markdown(layer, max_claims=-1)


def test_cli_markdown_export_layers_lineage_and_analyze_commands(tmp_path: Path) -> None:
    runner = CliRunner()
    store_dir = tmp_path / "store"
    store = DuckDBParquetStore(store_dir)

    # Empty store listing
    res_empty = runner.invoke(app, ["layers", "--store", str(store_dir)])
    assert res_empty.exit_code == 0, res_empty.stdout
    assert json.loads(res_empty.stdout) == {"count": 0, "layers": []}

    # Save parent + child layer
    parent = _build_rich_layer("layer-parent")
    child = _build_rich_layer("layer-child", parents=["layer-parent"])
    store.save_layer(parent)
    store.save_layer(child)

    # Export markdown via CLI
    md_out = tmp_path / "brief.md"
    res_md = runner.invoke(
        app,
        [
            "export",
            "layer-child",
            "--format",
            "markdown",
            "--output",
            str(md_out),
            "--store",
            str(store_dir),
        ],
    )
    assert res_md.exit_code == 0, res_md.stdout
    assert md_out.is_file()
    assert "## Grounded Knowledge Triples" in md_out.read_text(encoding="utf-8")

    # Layers catalog
    res_layers = runner.invoke(app, ["layers", "-s", str(store_dir)])
    assert res_layers.exit_code == 0, res_layers.stdout
    layers_payload = json.loads(res_layers.stdout)
    assert layers_payload["count"] == 2
    assert {entry["layer_id"] for entry in layers_payload["layers"]} == {
        "layer-parent",
        "layer-child",
    }

    # Lineage inspection
    res_lineage = runner.invoke(app, ["lineage", "layer-parent", "-s", str(store_dir)])
    assert res_lineage.exit_code == 0, res_lineage.stdout
    lineage_payload = json.loads(res_lineage.stdout)
    assert lineage_payload["descendants"] == ["layer-child"]
    assert lineage_payload["lineage_edges"] == [{"parent": "layer-parent", "child": "layer-child"}]

    res_missing_lineage = runner.invoke(app, ["lineage", "missing-id", "-s", str(store_dir)])
    assert res_missing_lineage.exit_code == 1
    assert "Error:" in res_missing_lineage.output

    # Analytics across metrics, no-communities, and shortest paths
    for metric in ("pagerank", "degree", "betweenness"):
        res_a = runner.invoke(
            app,
            ["analyze", "layer-child", "--metric", metric, "--top-k", "3", "-s", str(store_dir)],
        )
        assert res_a.exit_code == 0, res_a.stdout
        payload = json.loads(res_a.stdout)
        assert payload["metric"] == metric
        assert len(payload["central_nodes"]) == 3
        assert payload["community_count"] >= 1

    res_path = runner.invoke(
        app,
        [
            "analyze",
            "layer-child",
            "--no-communities",
            "--path-from",
            "ent-nels",
            "--path-to",
            "ent-ch",
            "--max-hops",
            "3",
            "-s",
            str(store_dir),
        ],
    )
    assert res_path.exit_code == 0, res_path.stdout
    path_payload = json.loads(res_path.stdout)
    assert path_payload["communities"] == []
    assert path_payload["shortest_path"]["found"] is True
    assert path_payload["shortest_path"]["hops"] == 1

    res_no_path = runner.invoke(
        app,
        [
            "analyze",
            "layer-child",
            "--path-from",
            "ent-nels",
            "--path-to",
            "missing-node",
            "-s",
            str(store_dir),
        ],
    )
    assert res_no_path.exit_code == 0, res_no_path.stdout
    assert json.loads(res_no_path.stdout)["shortest_path"]["found"] is False

    # Negative error exits
    res_bad_metric = runner.invoke(
        app, ["analyze", "layer-child", "--metric", "bogus", "-s", str(store_dir)]
    )
    assert res_bad_metric.exit_code == 1
    assert "Error:" in res_bad_metric.output

    res_half_path = runner.invoke(
        app, ["analyze", "layer-child", "--path-from", "ent-nels", "-s", str(store_dir)]
    )
    assert res_half_path.exit_code == 1
    assert "Error:" in res_half_path.output

    res_bad_k = runner.invoke(app, ["analyze", "layer-child", "--top-k", "0", "-s", str(store_dir)])
    assert res_bad_k.exit_code == 1
    assert "Error:" in res_bad_k.output
