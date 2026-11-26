"""Lossless sharded JSONL + manifest exporter and importer."""

from __future__ import annotations

import json
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from knowledgereduce.models import (
    Claim,
    ConflictRecord,
    Entity,
    KnowledgeLayer,
    LayerData,
    Relation,
    SourceDocument,
    StorageError,
)
from knowledgereduce.security import ensure_within_base

SHARDED_SCHEMA_VERSION = "1.0"
TModel = TypeVar("TModel", bound=BaseModel)


def _write_model_shards(
    items: Sequence[BaseModel],
    prefix: str,
    shard_size: int,
    out_dir: Path,
) -> list[str]:
    shard_files: list[str] = []
    if not items:
        return shard_files
    for idx, start in enumerate(range(0, len(items), shard_size), start=1):
        filename = f"{prefix}_{idx:05d}.jsonl"
        chunk = items[start : start + shard_size]
        lines = [item.model_dump_json() for item in chunk]
        (out_dir / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")
        shard_files.append(filename)
    return shard_files


def _read_model_shards(
    filenames: list[str],
    model_cls: type[TModel],
    in_dir: Path,
) -> list[TModel]:
    records: list[TModel] = []
    for fname in filenames:
        shard_path = ensure_within_base(fname, in_dir)
        if not shard_path.is_file():
            raise StorageError(f"Missing shard file referenced in manifest: {shard_path}")
        for line in shard_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped:
                records.append(model_cls.model_validate_json(stripped))
    return records


def export_layer_sharded(
    layer_data: LayerData,
    output_dir: Path | str,
    *,
    shard_size: int = 100,
    base_dir: Path | str | None = None,
    overwrite: bool = False,
) -> Path:
    """Export *layer_data* as lossless zero-padded JSONL shards plus ``manifest.json``."""
    if shard_size < 1:
        raise StorageError(f"shard_size must be >= 1 (got {shard_size}).")

    target_dir = (
        ensure_within_base(output_dir, base_dir)
        if base_dir is not None
        else Path(output_dir).resolve()
    )
    if target_dir.exists():
        if not overwrite:
            raise StorageError(
                f"Output directory {target_dir} already exists (pass overwrite=True)."
            )
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    shards: dict[str, list[str]] = {
        "sources": _write_model_shards(layer_data.sources, "sources", shard_size, target_dir),
        "entities": _write_model_shards(layer_data.entities, "entities", shard_size, target_dir),
        "claims": _write_model_shards(layer_data.claims, "claims", shard_size, target_dir),
        "relations": _write_model_shards(layer_data.relations, "relations", shard_size, target_dir),
        "conflicts": _write_model_shards(layer_data.conflicts, "conflicts", shard_size, target_dir),
    }

    manifest: dict[str, Any] = {
        "schema_version": SHARDED_SCHEMA_VERSION,
        "shard_size": shard_size,
        "layer": layer_data.layer.model_dump(mode="json"),
        "counts": {
            "sources": len(layer_data.sources),
            "entities": len(layer_data.entities),
            "claims": len(layer_data.claims),
            "relations": len(layer_data.relations),
            "conflicts": len(layer_data.conflicts),
        },
        "shards": shards,
    }
    (target_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )
    return target_dir


def import_layer_sharded(
    input_dir: Path | str,
    *,
    base_dir: Path | str | None = None,
) -> LayerData:
    """Reconstruct an exact ``LayerData`` from a sharded JSONL directory."""
    source_dir = (
        ensure_within_base(input_dir, base_dir)
        if base_dir is not None
        else Path(input_dir).resolve()
    )
    manifest_path = source_dir / "manifest.json"
    if not manifest_path.is_file():
        raise StorageError(f"Sharded export manifest.json not found in {source_dir}.")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SHARDED_SCHEMA_VERSION:
        raise StorageError(
            f"Unsupported sharded schema_version {manifest.get('schema_version')!r}."
        )
    shards = manifest["shards"]
    return LayerData(
        layer=KnowledgeLayer.model_validate(manifest["layer"]),
        sources=_read_model_shards(shards.get("sources", []), SourceDocument, source_dir),
        entities=_read_model_shards(shards.get("entities", []), Entity, source_dir),
        claims=_read_model_shards(shards.get("claims", []), Claim, source_dir),
        relations=_read_model_shards(shards.get("relations", []), Relation, source_dir),
        conflicts=_read_model_shards(shards.get("conflicts", []), ConflictRecord, source_dir),
    )
