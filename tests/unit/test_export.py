"""Unit tests for portable JSON, sharded JSONL, GraphML, and GEXF exporters."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import networkx as nx
import pytest

from knowledgereduce.export import (
    export_gexf,
    export_graphml,
    export_layer_json,
    export_layer_sharded,
    import_layer_json,
    import_layer_sharded,
)
from knowledgereduce.export.json_export import node_link_graph_compat
from knowledgereduce.models import (
    Claim,
    Entity,
    Evidence,
    KnowledgeLayer,
    LayerData,
    PathSecurityError,
    Relation,
    ReliabilityRating,
    SourceDocument,
    SourceType,
    StorageError,
)


def _make_many_nodes_layer(count: int = 12) -> LayerData:
    sources = [
        SourceDocument(
            source_id="src-1",
            uri="https://civichonors.com/",
            source_type=SourceType.WEB,
            content="Civic Honors text",
        )
    ]
    entities = [
        Entity(
            entity_id=f"e-{i:02d}",
            canonical_name=f"Entity {i}",
            entity_type="CONCEPT",
            aliases=[f"E{i}"],
            evidence=[Evidence(source_id="src-1", excerpt=f"Entity {i}")],
        )
        for i in range(count)
    ]
    claims = [
        Claim(
            claim_id=f"c-{i:02d}",
            statement=f"Statement number {i}",
            tags=["civic", "test"],
            reliability=ReliabilityRating.LIKELY_TRUE,
            source_id="src-1",
        )
        for i in range(count)
    ]
    # Cross-shard relations spanning entities across shard boundaries
    relations = [
        Relation(
            relation_id=f"r-{i:02d}",
            source_id=f"c-{i:02d}",
            target_id=f"e-{(count - 1 - i):02d}",
            relation_type="MENTIONS",
        )
        for i in range(count)
    ]
    return LayerData(
        layer=KnowledgeLayer(layer_id="export-test", name="Export Test"),
        sources=sources,
        entities=entities,
        claims=claims,
        relations=relations,
    )


def test_versioned_json_export_roundtrip_and_path_guard(tmp_path: Path) -> None:
    layer_data = _make_many_nodes_layer(3)
    out = export_layer_json(layer_data, "exports/layer.json", base_dir=tmp_path)
    assert out.is_file()

    restored = import_layer_json("exports/layer.json", base_dir=tmp_path)
    assert restored.layer.layer_id == layer_data.layer.layer_id
    assert len(restored.entities) == 3
    assert len(restored.claims) == 3
    assert len(restored.relations) == 3

    with pytest.raises(PathSecurityError):
        export_layer_json(layer_data, "../escape.json", base_dir=tmp_path)


def test_sharded_jsonl_preserves_cross_shard_edges_and_numeric_order(tmp_path: Path) -> None:
    layer_data = _make_many_nodes_layer(12)
    out_dir = export_layer_sharded(
        layer_data,
        "sharded",
        shard_size=1,
        base_dir=tmp_path,
    )
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    # Ensure >10 shards exist and are zero-padded in exact order
    assert manifest["shards"]["entities"][0] == "entities_00001.jsonl"
    assert manifest["shards"]["entities"][9] == "entities_00010.jsonl"
    assert manifest["shards"]["entities"][11] == "entities_00012.jsonl"

    restored = import_layer_sharded("sharded", base_dir=tmp_path)
    assert [e.entity_id for e in restored.entities] == [e.entity_id for e in layer_data.entities]
    assert len(restored.relations) == 12

    with pytest.raises(StorageError):
        export_layer_sharded(layer_data, "sharded", shard_size=0, base_dir=tmp_path)


def test_graphml_and_gexf_export_valid_xml_without_mutating_source(tmp_path: Path) -> None:
    layer_data = _make_many_nodes_layer(3)
    snapshot = layer_data.model_dump(mode="json")

    gml = export_graphml(layer_data, "graph.graphml", base_dir=tmp_path)
    gexf = export_gexf(layer_data, "graph.gexf", base_dir=tmp_path)

    assert ET.parse(gml).getroot().tag.endswith("graphml")  # noqa: S314
    assert ET.parse(gexf).getroot().tag.endswith("gexf")  # noqa: S314
    # Source LayerData must remain completely untouched
    assert layer_data.model_dump(mode="json") == snapshot


def test_json_export_error_paths_and_compat_loader(tmp_path: Path) -> None:
    with pytest.raises(StorageError, match="not found"):
        import_layer_json(tmp_path / "missing.json")

    bad_ver = tmp_path / "bad_ver.json"
    bad_ver.write_text(json.dumps({"schema_version": "9.9"}), encoding="utf-8")
    with pytest.raises(StorageError, match="schema_version"):
        import_layer_json(bad_ver)

    edges_payload = {
        "directed": True,
        "multigraph": True,
        "graph": {},
        "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [{"source": "a", "target": "b", "key": 0}],
    }
    restored_edges = node_link_graph_compat(edges_payload)
    assert isinstance(restored_edges, nx.MultiDiGraph)
    assert restored_edges.has_edge("a", "b")

    links_digraph_payload = {
        "directed": True,
        "multigraph": False,
        "graph": {},
        "nodes": [{"id": "a"}, {"id": "b"}],
        "links": [{"source": "a", "target": "b"}],
    }
    promoted = node_link_graph_compat(links_digraph_payload)
    assert isinstance(promoted, nx.MultiDiGraph)
    assert promoted.has_edge("a", "b")
