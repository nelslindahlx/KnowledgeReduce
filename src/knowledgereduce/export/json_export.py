"""Versioned JSON export and import for KnowledgeReduce layers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx

from knowledgereduce.models import LayerData, StorageError
from knowledgereduce.security import ensure_within_base
from knowledgereduce.storage.base import layer_data_to_networkx

JSON_EXPORT_SCHEMA_VERSION = "1.0"


def node_link_data_compat(graph: nx.MultiDiGraph) -> dict[str, Any]:
    """Serialize a NetworkX graph using explicit ``edges='links'`` schema stability."""
    try:
        data: dict[str, Any] = nx.node_link_data(graph, edges="links")
    except TypeError:  # pragma: no cover - fallback for NetworkX < 3.4
        data = nx.node_link_data(graph)
    return data


def node_link_graph_compat(data: dict[str, Any]) -> nx.MultiDiGraph:
    """Deserialize a NetworkX node-link JSON dict across NetworkX versions."""
    edges_key = "edges" if "edges" in data and "links" not in data else "links"
    try:
        graph = nx.node_link_graph(data, directed=True, multigraph=True, edges=edges_key)
    except TypeError:  # pragma: no cover - fallback for NetworkX < 3.4
        graph = nx.node_link_graph(data, directed=True, multigraph=True)
    if not isinstance(graph, nx.MultiDiGraph):
        return nx.MultiDiGraph(graph)
    return graph


def export_layer_json(
    layer_data: LayerData,
    output_path: Path | str,
    *,
    base_dir: Path | str | None = None,
    include_networkx: bool = True,
) -> Path:
    """Export *layer_data* as a versioned JSON document."""
    target = (
        ensure_within_base(output_path, base_dir)
        if base_dir is not None
        else Path(output_path).resolve()
    )
    target.parent.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = {
        "schema_version": JSON_EXPORT_SCHEMA_VERSION,
        "layer_data": layer_data.model_dump(mode="json"),
    }
    if include_networkx:
        payload["networkx_graph"] = node_link_data_compat(layer_data_to_networkx(layer_data))

    target.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return target


def import_layer_json(
    input_path: Path | str,
    *,
    base_dir: Path | str | None = None,
) -> LayerData:
    """Import a versioned KnowledgeReduce JSON export."""
    source = (
        ensure_within_base(input_path, base_dir)
        if base_dir is not None
        else Path(input_path).resolve()
    )
    if not source.is_file():
        raise StorageError(f"JSON export file not found: {source}")

    payload = json.loads(source.read_text(encoding="utf-8"))
    version = payload.get("schema_version")
    if version != JSON_EXPORT_SCHEMA_VERSION:
        raise StorageError(
            f"Unsupported JSON export schema_version {version!r} "
            f"(expected {JSON_EXPORT_SCHEMA_VERSION!r})."
        )
    return LayerData.model_validate(payload["layer_data"])
