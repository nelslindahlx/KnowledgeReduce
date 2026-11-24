"""Non-mutating sanitized GraphML and GEXF exporters."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import networkx as nx

from knowledgereduce.models import LayerData
from knowledgereduce.security import ensure_within_base
from knowledgereduce.storage.base import layer_data_to_networkx


def _sanitize_attr_value(value: Any) -> str | int | float | bool:
    if value is None:
        return ""
    if isinstance(value, Enum):
        return str(value.name)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, str)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, default=str)
    return str(value)


def to_sanitized_graph(layer_data: LayerData) -> nx.MultiDiGraph:
    """Create a fresh ``nx.MultiDiGraph`` with GraphML/GEXF-safe scalar attributes."""
    raw = layer_data_to_networkx(layer_data)
    sanitized = nx.MultiDiGraph(**{k: _sanitize_attr_value(v) for k, v in raw.graph.items()})
    for node_id, attrs in raw.nodes(data=True):
        sanitized.add_node(
            str(node_id),
            **{k: _sanitize_attr_value(v) for k, v in attrs.items()},
        )
    for src, dst, key, attrs in raw.edges(keys=True, data=True):
        sanitized.add_edge(
            str(src),
            str(dst),
            key=str(key),
            **{k: _sanitize_attr_value(v) for k, v in attrs.items()},
        )
    return sanitized


def export_graphml(
    layer_data: LayerData,
    output_path: Path | str,
    *,
    base_dir: Path | str | None = None,
) -> Path:
    """Export *layer_data* as sanitized GraphML without mutating source objects."""
    target = (
        ensure_within_base(output_path, base_dir)
        if base_dir is not None
        else Path(output_path).resolve()
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    nx.write_graphml(to_sanitized_graph(layer_data), str(target))
    return target


def export_gexf(
    layer_data: LayerData,
    output_path: Path | str,
    *,
    base_dir: Path | str | None = None,
) -> Path:
    """Export *layer_data* as sanitized GEXF without mutating source objects."""
    target = (
        ensure_within_base(output_path, base_dir)
        if base_dir is not None
        else Path(output_path).resolve()
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    nx.write_gexf(to_sanitized_graph(layer_data), str(target))
    return target
