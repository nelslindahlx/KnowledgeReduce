"""DuckDB + Parquet columnar layer store for KnowledgeReduce."""

from __future__ import annotations

import contextlib
import hashlib
import json
import shutil
import tempfile
import threading
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import duckdb
import networkx as nx
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from numpy.typing import NDArray

from knowledgereduce.models import (
    Claim,
    ConflictRecord,
    ConflictStrategy,
    Entity,
    Evidence,
    KnowledgeLayer,
    LayerData,
    Relation,
    ReliabilityRating,
    SourceDocument,
    SourceType,
    StorageError,
    validate_layer_id,
)
from knowledgereduce.security import ensure_within_base
from knowledgereduce.storage.base import (
    ClaimSummary,
    filter_matching_conflicts,
    layer_data_to_networkx,
    normalize_query_datetime,
    rank_claim_summaries,
    tokenize_search_query,
)

_CLAIM_SORT_COLUMNS: dict[str, str] = {
    "quality_score": "quality_score",
    "reliability": "reliability",
    "confidence": "confidence",
    "updated_at": "TRY_CAST(updated_at AS TIMESTAMPTZ)",
}

_CLAIM_SUMMARY_COLUMNS = [
    "claim_id",
    "statement",
    "reliability",
    "quality_score",
    "source_title",
    "author_creator",
    "contextual_notes",
]

SCHEMA_VERSION = "1.0"

_SOURCES_SCHEMA = pa.schema(
    [
        ("source_id", pa.string()),
        ("uri", pa.string()),
        ("source_type", pa.string()),
        ("title", pa.string()),
        ("author", pa.string()),
        ("published_at", pa.string()),
        ("fetched_at", pa.string()),
        ("content", pa.string()),
        ("content_sha256", pa.string()),
        ("trust_weight", pa.float64()),
        ("metadata_json", pa.string()),
    ]
)

_ENTITIES_SCHEMA = pa.schema(
    [
        ("entity_id", pa.string()),
        ("canonical_name", pa.string()),
        ("entity_type", pa.string()),
        ("aliases_json", pa.string()),
        ("attributes_json", pa.string()),
        ("evidence_json", pa.string()),
        ("external_ids_json", pa.string()),
    ]
)

_CLAIMS_SCHEMA = pa.schema(
    [
        ("claim_id", pa.string()),
        ("statement", pa.string()),
        ("category", pa.string()),
        ("tags_json", pa.string()),
        ("contextual_notes", pa.string()),
        ("recorded_at", pa.string()),
        ("updated_at", pa.string()),
        ("published_at", pa.string()),
        ("reliability", pa.int32()),
        ("source_id", pa.string()),
        ("source_title", pa.string()),
        ("author_creator", pa.string()),
        ("url_reference", pa.string()),
        ("access_level", pa.string()),
        ("usage_count", pa.int64()),
        ("related_facts_json", pa.string()),
        ("confidence", pa.float64()),
        ("quality_score", pa.float64()),
        ("subject_id", pa.string()),
        ("predicate", pa.string()),
        ("object_id", pa.string()),
        ("object_literal", pa.string()),
        ("evidence_json", pa.string()),
        ("merged_from_json", pa.string()),
        ("needs_review", pa.bool_()),
    ]
)

_RELATIONS_SCHEMA = pa.schema(
    [
        ("relation_id", pa.string()),
        ("source_id", pa.string()),
        ("target_id", pa.string()),
        ("relation_type", pa.string()),
        ("confidence", pa.float64()),
        ("weight", pa.float64()),
        ("evidence_json", pa.string()),
        ("attributes_json", pa.string()),
    ]
)

_CONFLICTS_SCHEMA = pa.schema(
    [
        ("conflict_id", pa.string()),
        ("target_type", pa.string()),
        ("target_key", pa.string()),
        ("candidates_json", pa.string()),
        ("resolution_strategy", pa.string()),
        ("winning_value_json", pa.string()),
        ("winning_source_id", pa.string()),
        ("resolved_at", pa.string()),
        ("needs_review", pa.bool_()),
        ("resolution_notes", pa.string()),
    ]
)

_CLAIM_EMBEDDINGS_SCHEMA = pa.schema(
    [
        ("claim_id", pa.string()),
        ("model_id", pa.string()),
        ("embedding", pa.list_(pa.float32())),
    ]
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_table(rows: list[dict[str, Any]], schema: pa.Schema, out_path: Path) -> dict[str, Any]:
    if rows:
        table = pa.Table.from_pylist(rows, schema=schema)
    else:
        empty_cols: dict[str, list[Any]] = {name: [] for name in schema.names}
        table = pa.Table.from_pydict(empty_cols, schema=schema)
    pq.write_table(table, out_path, compression="zstd")
    return {"rows": len(rows), "sha256": _sha256_file(out_path)}


def _parse_evidences(raw_json: str) -> list[Evidence]:
    items = json.loads(raw_json) if raw_json else []
    return [Evidence.model_validate(item) for item in items]


def _source_from_row(row: dict[str, Any]) -> SourceDocument:
    return SourceDocument(
        source_id=str(row["source_id"]),
        uri=str(row["uri"]),
        source_type=SourceType(str(row["source_type"])),
        title=str(row["title"] or ""),
        author=str(row["author"]) if row["author"] is not None else None,
        published_at=(
            datetime.fromisoformat(str(row["published_at"])) if row["published_at"] else None
        ),
        fetched_at=datetime.fromisoformat(str(row["fetched_at"])),
        content=str(row["content"] or ""),
        content_sha256=str(row["content_sha256"] or ""),
        trust_weight=float(row["trust_weight"]),
        metadata=json.loads(str(row["metadata_json"] or "{}")),
    )


def _entity_from_row(row: dict[str, Any]) -> Entity:
    return Entity(
        entity_id=str(row["entity_id"]),
        canonical_name=str(row["canonical_name"]),
        entity_type=str(row["entity_type"]),
        aliases=json.loads(str(row["aliases_json"] or "[]")),
        attributes=json.loads(str(row["attributes_json"] or "{}")),
        evidence=_parse_evidences(str(row["evidence_json"] or "[]")),
        external_ids=json.loads(str(row["external_ids_json"] or "{}")),
    )


def _claim_from_row(row: dict[str, Any]) -> Claim:
    return Claim(
        claim_id=str(row["claim_id"]),
        statement=str(row["statement"]),
        category=str(row["category"]),
        tags=json.loads(str(row["tags_json"] or "[]")),
        contextual_notes=str(row["contextual_notes"] or ""),
        recorded_at=datetime.fromisoformat(str(row["recorded_at"])),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
        published_at=(
            datetime.fromisoformat(str(row["published_at"])) if row["published_at"] else None
        ),
        reliability=ReliabilityRating(int(row["reliability"])),
        source_id=str(row["source_id"] or ""),
        source_title=str(row["source_title"] or ""),
        author_creator=str(row["author_creator"]) if row["author_creator"] is not None else None,
        url_reference=str(row["url_reference"]) if row["url_reference"] is not None else None,
        access_level=str(row["access_level"]),
        usage_count=int(row["usage_count"]),
        related_facts=json.loads(str(row["related_facts_json"] or "[]")),
        confidence=float(row["confidence"]),
        subject_id=str(row["subject_id"]) if row["subject_id"] is not None else None,
        predicate=str(row["predicate"]) if row["predicate"] is not None else None,
        object_id=str(row["object_id"]) if row["object_id"] is not None else None,
        object_literal=str(row["object_literal"]) if row["object_literal"] is not None else None,
        evidence=_parse_evidences(str(row["evidence_json"] or "[]")),
        merged_from=json.loads(str(row["merged_from_json"] or "[]")),
        needs_review=bool(row["needs_review"]),
    )


def _relation_from_row(row: dict[str, Any]) -> Relation:
    return Relation(
        relation_id=str(row["relation_id"]),
        source_id=str(row["source_id"]),
        target_id=str(row["target_id"]),
        relation_type=str(row["relation_type"]),
        confidence=float(row["confidence"]),
        weight=float(row["weight"]),
        evidence=_parse_evidences(str(row["evidence_json"] or "[]")),
        attributes=json.loads(str(row["attributes_json"] or "{}")),
    )


def _conflict_from_row(row: dict[str, Any]) -> ConflictRecord:
    return ConflictRecord(
        conflict_id=str(row["conflict_id"]),
        target_type=row["target_type"],
        target_key=str(row["target_key"]),
        candidates=json.loads(str(row["candidates_json"] or "[]")),
        resolution_strategy=ConflictStrategy(str(row["resolution_strategy"])),
        winning_value=json.loads(str(row["winning_value_json"] or "null")),
        winning_source_id=(
            str(row["winning_source_id"]) if row["winning_source_id"] is not None else None
        ),
        resolved_at=datetime.fromisoformat(str(row["resolved_at"])),
        needs_review=bool(row["needs_review"]),
        resolution_notes=str(row["resolution_notes"] or ""),
    )


class DuckDBParquetStore:
    """Persistent columnar layer store writing immutable Parquet files queried via DuckDB."""

    def __init__(self, root_dir: Path | str, *, graph_cache_max_rows: int = 50_000) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.layers_dir = self.root_dir / "layers"
        self.layers_dir.mkdir(parents=True, exist_ok=True)
        self._graph_cache_max_rows = graph_cache_max_rows
        self._con_lock = threading.RLock()
        self._write_lock = threading.RLock()
        self._read_con: duckdb.DuckDBPyConnection | None = None
        self._embedding_cache: dict[
            tuple[str, str], tuple[int, int, tuple[str, ...], NDArray[np.float32]]
        ] = {}
        self._claim_summary_cache: dict[
            str,
            tuple[
                int,
                int,
                tuple[ClaimSummary, ...],
                tuple[str, ...],
                dict[str, ClaimSummary],
            ],
        ] = {}
        self._layer_graph_cache: dict[
            str,
            tuple[
                tuple[tuple[int, int], ...],
                KnowledgeLayer,
                dict[str, Entity],
                dict[str, list[Relation]],
                list[ConflictRecord],
            ],
        ] = {}

    def _get_read_con(self) -> duckdb.DuckDBPyConnection:
        if self._read_con is None:
            self._read_con = duckdb.connect(":memory:")
        return self._read_con

    def close(self) -> None:
        """Close the cached in-memory DuckDB read session and release in-memory caches."""
        with self._con_lock:
            if self._read_con is not None:
                self._read_con.close()
                self._read_con = None
            self._embedding_cache.clear()
            self._claim_summary_cache.clear()
            self._layer_graph_cache.clear()

    def __enter__(self) -> DuckDBParquetStore:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def __del__(self) -> None:
        with contextlib.suppress(Exception):
            self.close()

    def _invalidate_embedding_cache(self, layer_id: str) -> None:
        stale = [key for key in self._embedding_cache if key[0] == layer_id]
        for key in stale:
            self._embedding_cache.pop(key, None)

    def _invalidate_layer_caches(self, layer_id: str) -> None:
        self._invalidate_embedding_cache(layer_id)
        self._claim_summary_cache.pop(layer_id, None)
        self._layer_graph_cache.pop(layer_id, None)

    def _layer_path(self, layer_id: str) -> Path:
        try:
            valid_id = validate_layer_id(layer_id)
        except ValueError as exc:
            raise StorageError(str(exc)) from exc
        return ensure_within_base(valid_id, self.layers_dir)

    def _parquet_path(self, layer_id: str, table_name: str) -> Path:
        layer_dir = self._layer_path(layer_id)
        if not (layer_dir / "manifest.json").is_file():
            raise StorageError(f"Layer {layer_id!r} not found in {self.layers_dir}.")
        pq_file = layer_dir / f"{table_name}.parquet"
        if not pq_file.is_file():
            raise StorageError(f"Missing {table_name}.parquet for layer {layer_id!r}.")
        return pq_file

    def _query_rows_with_con(
        self,
        con: duckdb.DuckDBPyConnection,
        sql: str,
        params: list[Any],
    ) -> list[dict[str, Any]]:
        cursor = con.execute(sql, params)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return [dict(zip(columns, row, strict=True)) for row in rows]

    def _query_rows(self, sql: str, params: list[Any]) -> list[dict[str, Any]]:
        with self._con_lock:
            return self._query_rows_with_con(self._get_read_con(), sql, params)

    def layer_exists(self, layer_id: str) -> bool:
        try:
            layer_dir = self._layer_path(layer_id)
        except StorageError:
            return False
        return (layer_dir / "manifest.json").is_file()

    def get_layer_manifest(self, layer_id: str) -> KnowledgeLayer:
        layer_dir = self._layer_path(layer_id)
        manifest_path = layer_dir / "manifest.json"
        if not manifest_path.is_file():
            raise StorageError(f"Layer {layer_id!r} not found.")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return KnowledgeLayer.model_validate(manifest["layer"])

    def list_source_hashes(self, layer_id: str) -> tuple[dict[str, str], dict[str, str]]:
        sources_pq = self._parquet_path(layer_id, "sources")
        table = pq.read_table(sources_pq, columns=["source_id", "uri", "content_sha256"])
        sids = table.column("source_id").to_pylist()
        uris = table.column("uri").to_pylist()
        shas = table.column("content_sha256").to_pylist()
        known_by_uri: dict[str, str] = {}
        known_by_source_id: dict[str, str] = {}
        for sid, uri, sha in zip(sids, uris, shas, strict=True):
            sha_str = str(sha or "")
            if not sha_str:
                continue
            if uri:
                known_by_uri[str(uri)] = sha_str
            if sid:
                known_by_source_id[str(sid)] = sha_str
        return known_by_uri, known_by_source_id

    def save_layer(self, layer_data: LayerData, *, overwrite: bool = False) -> KnowledgeLayer:
        layer_id = layer_data.layer.layer_id
        with self._write_lock:
            target_dir = self._layer_path(layer_id)
            if target_dir.exists() and not overwrite:
                raise StorageError(
                    f"Layer {layer_id!r} already exists at {target_dir} (pass overwrite=True)."
                )

            staging_dir = Path(
                tempfile.mkdtemp(prefix=f".staging_{layer_id}_", dir=self.layers_dir)
            )
            backup_dir: Path | None = None

            try:
                source_rows = [
                    {
                        "source_id": s.source_id,
                        "uri": s.uri,
                        "source_type": str(s.source_type),
                        "title": s.title,
                        "author": s.author,
                        "published_at": s.published_at.isoformat() if s.published_at else None,
                        "fetched_at": s.fetched_at.isoformat(),
                        "content": s.content,
                        "content_sha256": s.content_sha256,
                        "trust_weight": s.trust_weight,
                        "metadata_json": json.dumps(s.metadata, default=str),
                    }
                    for s in layer_data.sources
                ]
                entity_rows = [
                    {
                        "entity_id": e.entity_id,
                        "canonical_name": e.canonical_name,
                        "entity_type": e.entity_type,
                        "aliases_json": json.dumps(e.aliases),
                        "attributes_json": json.dumps(e.attributes, default=str),
                        "evidence_json": json.dumps(
                            [ev.model_dump(mode="json") for ev in e.evidence]
                        ),
                        "external_ids_json": json.dumps(e.external_ids),
                    }
                    for e in layer_data.entities
                ]
                claim_rows = [
                    {
                        "claim_id": c.claim_id,
                        "statement": c.statement,
                        "category": c.category,
                        "tags_json": json.dumps(c.tags),
                        "contextual_notes": c.contextual_notes,
                        "recorded_at": c.recorded_at.isoformat(),
                        "updated_at": c.updated_at.isoformat(),
                        "published_at": c.published_at.isoformat() if c.published_at else None,
                        "reliability": int(c.reliability),
                        "source_id": c.source_id,
                        "source_title": c.source_title,
                        "author_creator": c.author_creator,
                        "url_reference": c.url_reference,
                        "access_level": c.access_level,
                        "usage_count": c.usage_count,
                        "related_facts_json": json.dumps(c.related_facts),
                        "confidence": c.confidence,
                        "quality_score": c.quality_score,
                        "subject_id": c.subject_id,
                        "predicate": c.predicate,
                        "object_id": c.object_id,
                        "object_literal": c.object_literal,
                        "evidence_json": json.dumps(
                            [ev.model_dump(mode="json") for ev in c.evidence]
                        ),
                        "merged_from_json": json.dumps(c.merged_from),
                        "needs_review": c.needs_review,
                    }
                    for c in layer_data.claims
                ]
                relation_rows = [
                    {
                        "relation_id": r.relation_id,
                        "source_id": r.source_id,
                        "target_id": r.target_id,
                        "relation_type": r.relation_type,
                        "confidence": r.confidence,
                        "weight": r.weight,
                        "evidence_json": json.dumps(
                            [ev.model_dump(mode="json") for ev in r.evidence]
                        ),
                        "attributes_json": json.dumps(r.attributes, default=str),
                    }
                    for r in layer_data.relations
                ]
                conflict_rows = [
                    {
                        "conflict_id": cf.conflict_id,
                        "target_type": cf.target_type,
                        "target_key": cf.target_key,
                        "candidates_json": json.dumps(cf.candidates, default=str),
                        "resolution_strategy": str(cf.resolution_strategy),
                        "winning_value_json": json.dumps(cf.winning_value, default=str),
                        "winning_source_id": cf.winning_source_id,
                        "resolved_at": cf.resolved_at.isoformat(),
                        "needs_review": cf.needs_review,
                        "resolution_notes": cf.resolution_notes,
                    }
                    for cf in layer_data.conflicts
                ]

                files_meta = {
                    "sources.parquet": _write_table(
                        source_rows, _SOURCES_SCHEMA, staging_dir / "sources.parquet"
                    ),
                    "entities.parquet": _write_table(
                        entity_rows, _ENTITIES_SCHEMA, staging_dir / "entities.parquet"
                    ),
                    "claims.parquet": _write_table(
                        claim_rows, _CLAIMS_SCHEMA, staging_dir / "claims.parquet"
                    ),
                    "relations.parquet": _write_table(
                        relation_rows, _RELATIONS_SCHEMA, staging_dir / "relations.parquet"
                    ),
                    "conflicts.parquet": _write_table(
                        conflict_rows, _CONFLICTS_SCHEMA, staging_dir / "conflicts.parquet"
                    ),
                }

                layer_copy = KnowledgeLayer.model_validate(layer_data.layer.model_dump())
                manifest = {
                    "schema_version": SCHEMA_VERSION,
                    "layer": layer_copy.model_dump(mode="json"),
                    "files": files_meta,
                }
                (staging_dir / "manifest.json").write_text(
                    json.dumps(manifest, indent=2, default=str), encoding="utf-8"
                )

                if target_dir.exists():
                    backup_dir = Path(
                        tempfile.mkdtemp(prefix=f".backup_{layer_id}_", dir=self.layers_dir)
                    )
                    backup_dir.rmdir()
                    target_dir.rename(backup_dir)
                staging_dir.rename(target_dir)
                if backup_dir is not None and backup_dir.exists():
                    shutil.rmtree(backup_dir, ignore_errors=True)
                self._invalidate_layer_caches(layer_id)
                return layer_copy
            except Exception:
                if not target_dir.exists() and backup_dir is not None and backup_dir.exists():
                    with contextlib.suppress(Exception):
                        backup_dir.rename(target_dir)
                if staging_dir.exists():
                    shutil.rmtree(staging_dir, ignore_errors=True)
                raise

    def load_layer(self, layer_id: str) -> LayerData:
        layer = self.get_layer_manifest(layer_id)

        sources_pq = str(self._parquet_path(layer_id, "sources"))
        entities_pq = str(self._parquet_path(layer_id, "entities"))
        claims_pq = str(self._parquet_path(layer_id, "claims"))
        relations_pq = str(self._parquet_path(layer_id, "relations"))
        conflicts_pq = str(self._parquet_path(layer_id, "conflicts"))

        with self._con_lock:
            con = self._get_read_con()
            source_rows = self._query_rows_with_con(
                con, "SELECT * FROM read_parquet(?)", [sources_pq]
            )
            entity_rows = self._query_rows_with_con(
                con, "SELECT * FROM read_parquet(?)", [entities_pq]
            )
            claim_rows = self._query_rows_with_con(
                con, "SELECT * FROM read_parquet(?)", [claims_pq]
            )
            relation_rows = self._query_rows_with_con(
                con, "SELECT * FROM read_parquet(?)", [relations_pq]
            )
            conflict_rows = self._query_rows_with_con(
                con, "SELECT * FROM read_parquet(?)", [conflicts_pq]
            )

        return LayerData(
            layer=layer,
            sources=[_source_from_row(r) for r in source_rows],
            entities=[_entity_from_row(r) for r in entity_rows],
            claims=[_claim_from_row(r) for r in claim_rows],
            relations=[_relation_from_row(r) for r in relation_rows],
            conflicts=[_conflict_from_row(r) for r in conflict_rows],
        )

    def list_layers(self) -> list[KnowledgeLayer]:
        layers: list[KnowledgeLayer] = []
        for entry in self.layers_dir.iterdir():
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            manifest_path = entry / "manifest.json"
            if manifest_path.is_file():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                layers.append(KnowledgeLayer.model_validate(manifest["layer"]))
        return sorted(layers, key=lambda item: item.created_at)

    def delete_layer(self, layer_id: str) -> None:
        target_dir = self._layer_path(layer_id)
        if not target_dir.exists():
            raise StorageError(f"Layer {layer_id!r} not found.")
        shutil.rmtree(target_dir)
        self._invalidate_layer_caches(layer_id)

    def list_entities(
        self,
        layer_id: str,
        *,
        entity_type: str | None = None,
        name_query: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[Entity]:
        pq_path = str(self._parquet_path(layer_id, "entities"))
        clauses: list[str] = []
        params: list[Any] = [pq_path]

        if entity_type is not None:
            clauses.append("entity_type = ?")
            params.append(entity_type)
        if name_query is not None:
            like = f"%{name_query.lower()}%"
            clauses.append("(LOWER(canonical_name) LIKE ? OR LOWER(aliases_json) LIKE ?)")
            params.extend([like, like])

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, offset])
        sql = f"SELECT * FROM read_parquet(?) {where_sql} LIMIT ? OFFSET ?"  # noqa: S608
        return [_entity_from_row(r) for r in self._query_rows(sql, params)]

    def list_claims(
        self,
        layer_id: str,
        *,
        category: str | None = None,
        tag: str | None = None,
        tags_any: Sequence[str] | None = None,
        min_reliability: ReliabilityRating | None = None,
        needs_review: bool | None = None,
        text_query: str | None = None,
        recorded_after: datetime | None = None,
        recorded_before: datetime | None = None,
        published_after: datetime | None = None,
        published_before: datetime | None = None,
        subject_id: str | None = None,
        predicate: str | None = None,
        source_id: str | None = None,
        sort_by: Literal["quality_score", "reliability", "confidence", "updated_at"] | None = None,
        descending: bool = True,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[Claim]:
        if sort_by is not None and sort_by not in _CLAIM_SORT_COLUMNS:
            raise StorageError(f"Unsupported sort_by field {sort_by!r}.")
        pq_path = str(self._parquet_path(layer_id, "claims"))
        if limit <= 0 or offset < 0:
            return []
        clauses: list[str] = []
        params: list[Any] = [pq_path]

        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        if tag is not None:
            clauses.append("list_contains(from_json(tags_json, '[\"VARCHAR\"]'), ?)")
            params.append(tag)
        if tags_any is not None:
            tag_list = [str(item) for item in tags_any]
            if not tag_list:
                return []
            clauses.append("list_has_any(from_json(tags_json, '[\"VARCHAR\"]'), ?::VARCHAR[])")
            params.append(tag_list)
        if min_reliability is not None:
            clauses.append("reliability >= ?")
            params.append(int(min_reliability))
        if needs_review is not None:
            clauses.append("needs_review = ?")
            params.append(needs_review)
        if text_query is not None:
            like = f"%{text_query.lower()}%"
            clauses.append("(LOWER(statement) LIKE ? OR LOWER(contextual_notes) LIKE ?)")
            params.extend([like, like])
        if recorded_after is not None:
            clauses.append("TRY_CAST(recorded_at AS TIMESTAMPTZ) >= CAST(? AS TIMESTAMPTZ)")
            params.append(normalize_query_datetime(recorded_after).isoformat())
        if recorded_before is not None:
            clauses.append("TRY_CAST(recorded_at AS TIMESTAMPTZ) <= CAST(? AS TIMESTAMPTZ)")
            params.append(normalize_query_datetime(recorded_before).isoformat())
        if published_after is not None:
            clauses.append(
                "published_at IS NOT NULL AND TRY_CAST(published_at AS TIMESTAMPTZ) >= CAST(? AS TIMESTAMPTZ)"
            )
            params.append(normalize_query_datetime(published_after).isoformat())
        if published_before is not None:
            clauses.append(
                "published_at IS NOT NULL AND TRY_CAST(published_at AS TIMESTAMPTZ) <= CAST(? AS TIMESTAMPTZ)"
            )
            params.append(normalize_query_datetime(published_before).isoformat())
        if subject_id is not None:
            clauses.append("subject_id = ?")
            params.append(subject_id)
        if predicate is not None:
            clauses.append("predicate = ?")
            params.append(predicate)
        if source_id is not None:
            clauses.append("source_id = ?")
            params.append(source_id)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        order_sql = ""
        if sort_by is not None:
            direction = "DESC" if descending else "ASC"
            order_sql = f"ORDER BY {_CLAIM_SORT_COLUMNS[sort_by]} {direction}, claim_id ASC"
        params.extend([limit, offset])
        sql = f"SELECT * FROM read_parquet(?) {where_sql} {order_sql} LIMIT ? OFFSET ?"  # noqa: S608
        return [_claim_from_row(r) for r in self._query_rows(sql, params)]

    def list_relations(
        self,
        layer_id: str,
        *,
        source_id: str | None = None,
        target_id: str | None = None,
        relation_type: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[Relation]:
        pq_path = str(self._parquet_path(layer_id, "relations"))
        clauses: list[str] = []
        params: list[Any] = [pq_path]

        if source_id is not None:
            clauses.append("source_id = ?")
            params.append(source_id)
        if target_id is not None:
            clauses.append("target_id = ?")
            params.append(target_id)
        if relation_type is not None:
            clauses.append("relation_type = ?")
            params.append(relation_type)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, offset])
        sql = f"SELECT * FROM read_parquet(?) {where_sql} LIMIT ? OFFSET ?"  # noqa: S608
        return [_relation_from_row(r) for r in self._query_rows(sql, params)]

    def list_conflicts(
        self,
        layer_id: str,
        *,
        needs_review: bool | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[ConflictRecord]:
        pq_path = str(self._parquet_path(layer_id, "conflicts"))
        clauses: list[str] = []
        params: list[Any] = [pq_path]

        if needs_review is not None:
            clauses.append("needs_review = ?")
            params.append(needs_review)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, offset])
        sql = f"SELECT * FROM read_parquet(?) {where_sql} LIMIT ? OFFSET ?"  # noqa: S608
        return [_conflict_from_row(r) for r in self._query_rows(sql, params)]

    def to_networkx(self, layer_id: str) -> nx.MultiDiGraph:
        return layer_data_to_networkx(self.load_layer(layer_id))

    def list_claim_texts(self, layer_id: str) -> list[tuple[str, str]]:
        pq_path = str(self._parquet_path(layer_id, "claims"))
        rows = self._query_rows("SELECT claim_id, statement FROM read_parquet(?)", [pq_path])
        return [(str(r["claim_id"]), str(r["statement"])) for r in rows]

    def save_claim_embeddings(
        self,
        layer_id: str,
        claim_ids: Sequence[str],
        vectors: NDArray[np.float32],
        *,
        model_id: str,
    ) -> None:
        claims_pq = self._parquet_path(layer_id, "claims")
        layer_dir = claims_pq.parent
        arr = np.asarray(vectors, dtype=np.float32)
        if len(claim_ids) > 0 and (arr.ndim != 2 or arr.shape[0] != len(claim_ids)):
            raise StorageError(
                f"Embedding count mismatch: got {len(claim_ids)} claim_ids vs shape {arr.shape}."
            )
        if len(claim_ids) == 0:
            table = pa.Table.from_pydict(
                {"claim_id": [], "model_id": [], "embedding": []},
                schema=_CLAIM_EMBEDDINGS_SCHEMA,
            )
        elif arr.shape[1] == 0:
            table = pa.table(
                {
                    "claim_id": pa.array(list(claim_ids), type=pa.string()),
                    "model_id": pa.array([model_id] * len(claim_ids), type=pa.string()),
                    "embedding": pa.array(arr.tolist(), type=pa.list_(pa.float32())),
                },
                schema=_CLAIM_EMBEDDINGS_SCHEMA,
            )
        else:
            dim = int(arr.shape[1])
            flat = pa.array(np.ascontiguousarray(arr, dtype=np.float32).ravel(), type=pa.float32())
            emb_arr = pa.FixedSizeListArray.from_arrays(flat, dim)
            emb_schema = pa.schema(
                [
                    ("claim_id", pa.string()),
                    ("model_id", pa.string()),
                    ("embedding", pa.list_(pa.float32(), dim)),
                ]
            )
            table = pa.table(
                {
                    "claim_id": pa.array(list(claim_ids), type=pa.string()),
                    "model_id": pa.array([model_id] * len(claim_ids), type=pa.string()),
                    "embedding": emb_arr,
                },
                schema=emb_schema,
            )
        with self._write_lock:
            staging_emb = layer_dir / ".staging_claim_embeddings.parquet"
            target_emb = layer_dir / "claim_embeddings.parquet"
            pq.write_table(table, staging_emb, compression="zstd")
            staging_emb.replace(target_emb)
            self._invalidate_embedding_cache(layer_id)

    def load_claim_embeddings(
        self,
        layer_id: str,
        *,
        model_id: str,
    ) -> tuple[list[str], NDArray[np.float32]] | None:
        self._parquet_path(layer_id, "claims")
        emb_path = self._layer_path(layer_id) / "claim_embeddings.parquet"
        if not emb_path.is_file():
            return None

        stat = emb_path.stat()
        cache_key = (layer_id, model_id)
        cached = self._embedding_cache.get(cache_key)
        if cached is not None and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
            return list(cached[2]), cached[3]

        table = pq.read_table(emb_path)
        if table.num_rows == 0:
            return None
        stored_models = {str(m) for m in table.column("model_id").unique().to_pylist()}
        if stored_models != {model_id}:
            return None

        ids = tuple(str(cid) for cid in table.column("claim_id").to_pylist())
        emb_col = table.column("embedding").combine_chunks()
        if (
            pa.types.is_fixed_size_list(emb_col.type)
            and emb_col.null_count == 0
            and emb_col.offset == 0
        ):
            dim = int(emb_col.type.list_size)
            vecs = (
                np.asarray(emb_col.values.to_numpy(zero_copy_only=False), dtype=np.float32)
                .reshape(table.num_rows, dim)
                .copy()
            )
        else:
            vecs = np.asarray(emb_col.to_pylist(), dtype=np.float32)

        vecs.flags.writeable = False
        self._embedding_cache[cache_key] = (stat.st_mtime_ns, stat.st_size, ids, vecs)
        return list(ids), vecs

    def search_claims_lexical(
        self,
        layer_id: str,
        query: str,
        *,
        min_reliability: ReliabilityRating = ReliabilityRating.UNKNOWN,
        limit: int = 200,
    ) -> list[Claim]:
        pq_path = str(self._parquet_path(layer_id, "claims"))
        if limit <= 0:
            return []
        like_patterns = [f"%{tok}%" for tok in tokenize_search_query(query)]
        sql = (
            "SELECT * FROM read_parquet(?) "
            "WHERE reliability >= ? "
            "ORDER BY len(list_filter(?::VARCHAR[], tok -> LOWER(statement) LIKE tok)) DESC, "
            "quality_score DESC, claim_id ASC "
            "LIMIT ?"
        )
        return [
            _claim_from_row(r)
            for r in self._query_rows(sql, [pq_path, int(min_reliability), like_patterns, limit])
        ]

    def _load_claim_summaries(
        self, layer_id: str
    ) -> tuple[tuple[ClaimSummary, ...], tuple[str, ...], dict[str, ClaimSummary]]:
        claims_pq = self._parquet_path(layer_id, "claims")
        stat = claims_pq.stat()
        cached = self._claim_summary_cache.get(layer_id)
        if cached is not None and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
            return cached[2], cached[3], cached[4]

        table = pq.read_table(claims_pq, columns=_CLAIM_SUMMARY_COLUMNS)
        cids = table.column("claim_id").to_pylist()
        stmts = table.column("statement").to_pylist()
        rels = table.column("reliability").to_pylist()
        quals = table.column("quality_score").to_pylist()
        titles = table.column("source_title").to_pylist()
        authors = table.column("author_creator").to_pylist()
        notes = table.column("contextual_notes").to_pylist()

        summaries_list: list[ClaimSummary] = []
        lower_list: list[str] = []
        by_id: dict[str, ClaimSummary] = {}
        for cid, stmt, rel, qual, title, author, note in zip(
            cids, stmts, rels, quals, titles, authors, notes, strict=True
        ):
            stmt_str = str(stmt)
            summary = ClaimSummary(
                claim_id=str(cid),
                statement=stmt_str,
                reliability=ReliabilityRating(int(rel)),
                quality_score=float(qual),
                source_title=str(title or ""),
                author_creator=str(author) if author is not None else None,
                contextual_notes=str(note or ""),
            )
            summaries_list.append(summary)
            lower_list.append(stmt_str.lower())
            by_id[summary.claim_id] = summary

        summaries_tup = tuple(summaries_list)
        lower_tup = tuple(lower_list)
        self._claim_summary_cache[layer_id] = (
            stat.st_mtime_ns,
            stat.st_size,
            summaries_tup,
            lower_tup,
            by_id,
        )
        return summaries_tup, lower_tup, by_id

    def search_claim_summaries_lexical(
        self,
        layer_id: str,
        query: str,
        *,
        min_reliability: ReliabilityRating = ReliabilityRating.UNKNOWN,
        limit: int = 200,
    ) -> list[ClaimSummary]:
        """Rank lightweight claim summaries using direct cached Parquet column projections."""
        if limit <= 0:
            self._parquet_path(layer_id, "claims")
            return []
        summaries, lower_stmts, _by_id = self._load_claim_summaries(layer_id)
        return rank_claim_summaries(
            summaries,
            lower_stmts,
            query,
            min_reliability=min_reliability,
            limit=limit,
        )

    def get_claim_summaries_by_ids(
        self, layer_id: str, claim_ids: Sequence[str]
    ) -> list[ClaimSummary]:
        """Fetch cached lightweight ``ClaimSummary`` projections matching *claim_ids*."""
        unique_ids = list(dict.fromkeys(claim_ids))
        if not unique_ids:
            self._parquet_path(layer_id, "claims")
            return []
        _summaries, _lower_stmts, by_id = self._load_claim_summaries(layer_id)
        return [by_id[cid] for cid in unique_ids if cid in by_id]

    def get_claims_by_ids(self, layer_id: str, claim_ids: Sequence[str]) -> list[Claim]:
        pq_path = str(self._parquet_path(layer_id, "claims"))
        unique_ids = list(dict.fromkeys(claim_ids))
        if not unique_ids:
            return []
        rows = self._query_rows(
            "SELECT * FROM read_parquet(?) WHERE claim_id IN (SELECT UNNEST(?::VARCHAR[]))",
            [pq_path, unique_ids],
        )
        by_id = {str(r["claim_id"]): _claim_from_row(r) for r in rows}
        return [by_id[cid] for cid in unique_ids if cid in by_id]

    def _load_cached_graph_index(
        self,
        layer_id: str,
        manifest_path: Path,
        ent_pq: Path,
        rel_pq: Path,
        cf_pq: Path,
    ) -> (
        tuple[
            KnowledgeLayer,
            dict[str, Entity],
            dict[str, list[Relation]],
            list[ConflictRecord],
        ]
        | None
    ):
        if self._graph_cache_max_rows <= 0:
            return None
        m_st = manifest_path.stat()
        e_st = ent_pq.stat()
        r_st = rel_pq.stat()
        c_st = cf_pq.stat()
        stamp = (
            (m_st.st_mtime_ns, m_st.st_size),
            (e_st.st_mtime_ns, e_st.st_size),
            (r_st.st_mtime_ns, r_st.st_size),
            (c_st.st_mtime_ns, c_st.st_size),
        )
        cached = self._layer_graph_cache.get(layer_id)
        if cached is not None and cached[0] == stamp:
            return cached[1], cached[2], cached[3], cached[4]

        ent_num_rows = int(pq.read_metadata(ent_pq).num_rows)
        rel_num_rows = int(pq.read_metadata(rel_pq).num_rows)
        if ent_num_rows > self._graph_cache_max_rows or rel_num_rows > self._graph_cache_max_rows:
            return None

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        layer_meta = KnowledgeLayer.model_validate(manifest["layer"])
        cf_num_rows = int(pq.read_metadata(cf_pq).num_rows)

        with self._con_lock:
            con = self._get_read_con()
            ent_rows = self._query_rows_with_con(
                con, "SELECT * FROM read_parquet(?)", [str(ent_pq)]
            )
            rel_rows = (
                self._query_rows_with_con(con, "SELECT * FROM read_parquet(?)", [str(rel_pq)])
                if rel_num_rows > 0
                else []
            )
            cf_rows = (
                self._query_rows_with_con(con, "SELECT * FROM read_parquet(?)", [str(cf_pq)])
                if cf_num_rows > 0
                else []
            )

        entities_by_id = {e.entity_id: e for e in (_entity_from_row(r) for r in ent_rows)}
        adj_relations: dict[str, list[Relation]] = {}
        for rel in (_relation_from_row(r) for r in rel_rows):
            adj_relations.setdefault(rel.source_id, []).append(rel)
            if rel.target_id != rel.source_id:
                adj_relations.setdefault(rel.target_id, []).append(rel)
        conflicts = [_conflict_from_row(r) for r in cf_rows]

        self._layer_graph_cache[layer_id] = (
            stamp,
            layer_meta,
            entities_by_id,
            adj_relations,
            conflicts,
        )
        return layer_meta, entities_by_id, adj_relations, conflicts

    def get_k_hop_subgraph(
        self,
        layer_id: str,
        seed_node_ids: Sequence[str],
        *,
        hops: int = 1,
    ) -> tuple[nx.MultiDiGraph, list[Entity], list[ConflictRecord]]:
        layer_dir = self._layer_path(layer_id)
        manifest_path = layer_dir / "manifest.json"
        if not manifest_path.is_file():
            raise StorageError(f"Layer {layer_id!r} not found.")
        ent_path = self._parquet_path(layer_id, "entities")
        clm_path = self._parquet_path(layer_id, "claims")
        rel_path = self._parquet_path(layer_id, "relations")
        cf_path = self._parquet_path(layer_id, "conflicts")
        if not seed_node_ids:
            return nx.MultiDiGraph(), [], []

        cached_graph = self._load_cached_graph_index(
            layer_id, manifest_path, ent_path, rel_path, cf_path
        )
        if cached_graph is not None:
            layer_meta, entities_by_id, adj_relations, all_conflicts = cached_graph
            visited: set[str] = set(seed_node_ids)
            frontier: set[str] = set(seed_node_ids)
            for _ in range(max(0, hops)):
                if not frontier:
                    break
                next_frontier: set[str] = set()
                for nid in frontier:
                    for rel in adj_relations.get(nid, ()):
                        if rel.source_id not in visited:
                            next_frontier.add(rel.source_id)
                        if rel.target_id not in visited:
                            next_frontier.add(rel.target_id)
                frontier = next_frontier
                visited.update(frontier)

            sub_entities = [entities_by_id[nid] for nid in visited if nid in entities_by_id]
            claim_ids_needed = [nid for nid in visited if nid not in entities_by_id]
            sub_claims = (
                self.get_claims_by_ids(layer_id, claim_ids_needed) if claim_ids_needed else []
            )
            surviving = {e.entity_id for e in sub_entities} | {c.claim_id for c in sub_claims}
            sub_relations: list[Relation] = []
            if hops > 0 and surviving:
                seen_rel_ids: set[str] = set()
                for nid in surviving:
                    for rel in adj_relations.get(nid, ()):
                        if (
                            rel.relation_id not in seen_rel_ids
                            and rel.source_id in surviving
                            and rel.target_id in surviving
                        ):
                            seen_rel_ids.add(rel.relation_id)
                            sub_relations.append(rel)

            sub_claim_ids = {c.claim_id for c in sub_claims}
            touched_conflicts = (
                filter_matching_conflicts(all_conflicts, sub_claim_ids) if sub_claim_ids else []
            )
            sub_graph = layer_data_to_networkx(
                LayerData(
                    layer=layer_meta,
                    entities=sub_entities,
                    claims=sub_claims,
                    relations=sub_relations,
                )
            )
            return sub_graph, sub_entities, touched_conflicts

        ent_pq = str(ent_path)
        clm_pq = str(clm_path)
        rel_pq = str(rel_path)
        cf_pq = str(cf_path)

        visited = set(seed_node_ids)
        frontier = set(seed_node_ids)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        layer_meta = KnowledgeLayer.model_validate(manifest["layer"])
        has_relations = pq.read_metadata(rel_pq).num_rows > 0
        has_conflicts = pq.read_metadata(cf_pq).num_rows > 0

        with self._con_lock:
            con = self._get_read_con()
            if has_relations:
                for _ in range(max(0, hops)):
                    if not frontier:
                        break
                    frontier_list = list(frontier)
                    hop_rows = self._query_rows_with_con(
                        con,
                        "SELECT source_id, target_id FROM read_parquet(?) "
                        "WHERE source_id IN (SELECT UNNEST(?::VARCHAR[])) "
                        "OR target_id IN (SELECT UNNEST(?::VARCHAR[]))",
                        [rel_pq, frontier_list, frontier_list],
                    )
                    next_frontier = set()
                    for r in hop_rows:
                        next_frontier.add(str(r["source_id"]))
                        next_frontier.add(str(r["target_id"]))
                    frontier = next_frontier - visited
                    visited.update(frontier)

            visited_list = list(visited)
            ent_rows = self._query_rows_with_con(
                con,
                "SELECT * FROM read_parquet(?) WHERE entity_id IN (SELECT UNNEST(?::VARCHAR[]))",
                [ent_pq, visited_list],
            )
            clm_rows = self._query_rows_with_con(
                con,
                "SELECT * FROM read_parquet(?) WHERE claim_id IN (SELECT UNNEST(?::VARCHAR[]))",
                [clm_pq, visited_list],
            )
            sub_entities = [_entity_from_row(r) for r in ent_rows]
            sub_claims = [_claim_from_row(r) for r in clm_rows]
            surviving = {e.entity_id for e in sub_entities} | {c.claim_id for c in sub_claims}

            sub_relations = []
            if hops > 0 and has_relations and surviving:
                surviving_list = list(surviving)
                rel_rows = self._query_rows_with_con(
                    con,
                    "SELECT * FROM read_parquet(?) "
                    "WHERE source_id IN (SELECT UNNEST(?::VARCHAR[])) "
                    "AND target_id IN (SELECT UNNEST(?::VARCHAR[]))",
                    [rel_pq, surviving_list, surviving_list],
                )
                sub_relations = [_relation_from_row(r) for r in rel_rows]

            sub_claim_ids = {c.claim_id for c in sub_claims}
            touched_conflicts = []
            if sub_claim_ids and has_conflicts:
                cf_rows = self._query_rows_with_con(con, "SELECT * FROM read_parquet(?)", [cf_pq])
                touched_conflicts = filter_matching_conflicts(
                    [_conflict_from_row(r) for r in cf_rows],
                    sub_claim_ids,
                )

        sub_graph = layer_data_to_networkx(
            LayerData(
                layer=layer_meta,
                entities=sub_entities,
                claims=sub_claims,
                relations=sub_relations,
            )
        )
        return sub_graph, sub_entities, touched_conflicts
