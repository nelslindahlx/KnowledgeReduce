"""DuckDB + Parquet columnar layer store for KnowledgeReduce."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import networkx as nx
import pyarrow as pa
import pyarrow.parquet as pq

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
from knowledgereduce.storage.base import layer_data_to_networkx

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

    def __init__(self, root_dir: Path | str) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.layers_dir = self.root_dir / "layers"
        self.layers_dir.mkdir(parents=True, exist_ok=True)

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

    def _query_rows(self, sql: str, params: list[Any]) -> list[dict[str, Any]]:
        with duckdb.connect(":memory:") as con:
            cursor = con.execute(sql, params)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
        return [dict(zip(columns, row, strict=True)) for row in rows]

    def layer_exists(self, layer_id: str) -> bool:
        try:
            layer_dir = self._layer_path(layer_id)
        except StorageError:
            return False
        return (layer_dir / "manifest.json").is_file()

    def save_layer(self, layer_data: LayerData, *, overwrite: bool = False) -> KnowledgeLayer:
        layer_id = layer_data.layer.layer_id
        target_dir = self._layer_path(layer_id)
        if target_dir.exists() and not overwrite:
            raise StorageError(
                f"Layer {layer_id!r} already exists at {target_dir} (pass overwrite=True)."
            )

        staging_dir = self.layers_dir / f".staging_{layer_id}"
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)

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
                    "metadata_json": json.dumps(s.metadata),
                }
                for s in layer_data.sources
            ]
            entity_rows = [
                {
                    "entity_id": e.entity_id,
                    "canonical_name": e.canonical_name,
                    "entity_type": e.entity_type,
                    "aliases_json": json.dumps(e.aliases),
                    "attributes_json": json.dumps(e.attributes),
                    "evidence_json": json.dumps([ev.model_dump(mode="json") for ev in e.evidence]),
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
                    "evidence_json": json.dumps([ev.model_dump(mode="json") for ev in c.evidence]),
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
                    "evidence_json": json.dumps([ev.model_dump(mode="json") for ev in r.evidence]),
                    "attributes_json": json.dumps(r.attributes),
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
                json.dumps(manifest, indent=2), encoding="utf-8"
            )

            if target_dir.exists():
                shutil.rmtree(target_dir)
            staging_dir.rename(target_dir)
            return layer_copy
        except Exception:
            if staging_dir.exists():
                shutil.rmtree(staging_dir)
            raise

    def load_layer(self, layer_id: str) -> LayerData:
        layer_dir = self._layer_path(layer_id)
        manifest_path = layer_dir / "manifest.json"
        if not manifest_path.is_file():
            raise StorageError(f"Layer {layer_id!r} not found.")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        layer = KnowledgeLayer.model_validate(manifest["layer"])

        source_rows = self._query_rows(
            "SELECT * FROM read_parquet(?)", [str(self._parquet_path(layer_id, "sources"))]
        )
        entity_rows = self._query_rows(
            "SELECT * FROM read_parquet(?)", [str(self._parquet_path(layer_id, "entities"))]
        )
        claim_rows = self._query_rows(
            "SELECT * FROM read_parquet(?)", [str(self._parquet_path(layer_id, "claims"))]
        )
        relation_rows = self._query_rows(
            "SELECT * FROM read_parquet(?)", [str(self._parquet_path(layer_id, "relations"))]
        )
        conflict_rows = self._query_rows(
            "SELECT * FROM read_parquet(?)", [str(self._parquet_path(layer_id, "conflicts"))]
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
        min_reliability: ReliabilityRating | None = None,
        needs_review: bool | None = None,
        text_query: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[Claim]:
        pq_path = str(self._parquet_path(layer_id, "claims"))
        clauses: list[str] = []
        params: list[Any] = [pq_path]

        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        if tag is not None:
            clauses.append("list_contains(from_json(tags_json, '[\"VARCHAR\"]'), ?)")
            params.append(tag)
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

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, offset])
        sql = f"SELECT * FROM read_parquet(?) {where_sql} LIMIT ? OFFSET ?"  # noqa: S608
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
