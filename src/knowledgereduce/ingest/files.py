"""Local file connectors (CSV, JSON, JSONL, Markdown, plain text)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import yaml

from knowledgereduce.models import IngestionError, SourceDocument, SourceType, utc_now
from knowledgereduce.security import ensure_within_base


def _resolve_input_path(path: Path | str, base_dir: Path | str | None) -> Path:
    resolved = ensure_within_base(path, base_dir) if base_dir is not None else Path(path).resolve()
    if not resolved.is_file():
        raise IngestionError(f"Input file not found: {resolved}")
    return resolved


def _file_source_id(prefix: str, resolved: Path) -> str:
    digest = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _parse_markdown_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---"):
        return {}, raw
    lines = raw.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, raw
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            fm_raw = "".join(lines[1:idx])
            body = "".join(lines[idx + 1 :])
            parsed = yaml.safe_load(fm_raw)
            if isinstance(parsed, dict):
                return parsed, body.strip()
            break
    return {}, raw


class CSVConnector:
    """Ingest a CSV file into a normalized ``SourceDocument`` preserving parsed rows."""

    def __init__(
        self,
        path: Path | str,
        *,
        source_id: str | None = None,
        title: str | None = None,
        trust_weight: float = 0.8,
        base_dir: Path | str | None = None,
    ) -> None:
        self.path = path
        self.source_id = source_id
        self.title = title
        self.trust_weight = trust_weight
        self.base_dir = base_dir

    def ingest(self) -> list[SourceDocument]:
        resolved = _resolve_input_path(self.path, self.base_dir)
        raw = resolved.read_text(encoding="utf-8")
        reader = csv.DictReader(io.StringIO(raw))
        rows = [dict(row) for row in reader]
        return [
            SourceDocument(
                source_id=self.source_id or _file_source_id("csv", resolved),
                uri=resolved.as_uri(),
                source_type=SourceType.CSV,
                title=self.title or resolved.name,
                fetched_at=utc_now(),
                content=raw,
                trust_weight=self.trust_weight,
                metadata={"row_count": len(rows), "columns": list(reader.fieldnames or [])},
            )
        ]


class JSONConnector:
    """Ingest a JSON or JSONL file into a normalized ``SourceDocument``."""

    def __init__(
        self,
        path: Path | str,
        *,
        source_id: str | None = None,
        title: str | None = None,
        trust_weight: float = 0.8,
        base_dir: Path | str | None = None,
    ) -> None:
        self.path = path
        self.source_id = source_id
        self.title = title
        self.trust_weight = trust_weight
        self.base_dir = base_dir

    def ingest(self) -> list[SourceDocument]:
        resolved = _resolve_input_path(self.path, self.base_dir)
        raw = resolved.read_text(encoding="utf-8")
        is_jsonl = resolved.suffix.lower() == ".jsonl"
        try:
            if is_jsonl:
                records = [json.loads(line) for line in raw.splitlines() if line.strip()]
                source_type = SourceType.JSONL
            else:
                parsed = json.loads(raw)
                records = parsed if isinstance(parsed, list) else [parsed]
                source_type = SourceType.JSON
        except json.JSONDecodeError as exc:
            raise IngestionError(f"Invalid JSON content in {resolved}: {exc}") from exc

        return [
            SourceDocument(
                source_id=self.source_id or _file_source_id(source_type.value, resolved),
                uri=resolved.as_uri(),
                source_type=source_type,
                title=self.title or resolved.name,
                fetched_at=utc_now(),
                content=json.dumps(records),
                trust_weight=self.trust_weight,
                metadata={"record_count": len(records)},
            )
        ]


class MarkdownConnector:
    """Ingest a Markdown file (with optional YAML frontmatter)."""

    def __init__(
        self,
        path: Path | str,
        *,
        source_id: str | None = None,
        title: str | None = None,
        author: str | None = None,
        trust_weight: float = 0.75,
        base_dir: Path | str | None = None,
    ) -> None:
        self.path = path
        self.source_id = source_id
        self.title = title
        self.author = author
        self.trust_weight = trust_weight
        self.base_dir = base_dir

    def ingest(self) -> list[SourceDocument]:
        resolved = _resolve_input_path(self.path, self.base_dir)
        raw = resolved.read_text(encoding="utf-8")
        fm, body = _parse_markdown_frontmatter(raw)
        doc_title = self.title or str(fm.get("title") or resolved.stem)
        doc_author = self.author or (str(fm["author"]) if "author" in fm else None)
        return [
            SourceDocument(
                source_id=self.source_id or _file_source_id("md", resolved),
                uri=resolved.as_uri(),
                source_type=SourceType.MARKDOWN,
                title=doc_title,
                author=doc_author,
                fetched_at=utc_now(),
                content=body.strip(),
                trust_weight=self.trust_weight,
                metadata={"frontmatter": fm},
            )
        ]


class TextConnector:
    """Ingest a plain-text file into a normalized ``SourceDocument``."""

    def __init__(
        self,
        path: Path | str,
        *,
        source_id: str | None = None,
        title: str | None = None,
        author: str | None = None,
        trust_weight: float = 0.7,
        base_dir: Path | str | None = None,
    ) -> None:
        self.path = path
        self.source_id = source_id
        self.title = title
        self.author = author
        self.trust_weight = trust_weight
        self.base_dir = base_dir

    def ingest(self) -> list[SourceDocument]:
        resolved = _resolve_input_path(self.path, self.base_dir)
        raw = resolved.read_text(encoding="utf-8").strip()
        return [
            SourceDocument(
                source_id=self.source_id or _file_source_id("txt", resolved),
                uri=resolved.as_uri(),
                source_type=SourceType.TEXT,
                title=self.title or resolved.name,
                author=self.author,
                fetched_at=utc_now(),
                content=raw,
                trust_weight=self.trust_weight,
                metadata={"char_count": len(raw)},
            )
        ]


def ingest_local_file(
    path: Path | str,
    *,
    source_id: str | None = None,
    trust_weight: float = 0.75,
    base_dir: Path | str | None = None,
) -> list[SourceDocument]:
    """Dispatch a local file to the matching connector based on suffix."""
    resolved = _resolve_input_path(path, base_dir)
    suffix = resolved.suffix.lower()
    if suffix == ".csv":
        return CSVConnector(resolved, source_id=source_id, trust_weight=trust_weight).ingest()
    if suffix in {".json", ".jsonl"}:
        return JSONConnector(resolved, source_id=source_id, trust_weight=trust_weight).ingest()
    if suffix in {".md", ".markdown"}:
        return MarkdownConnector(resolved, source_id=source_id, trust_weight=trust_weight).ingest()
    if suffix == ".txt":
        return TextConnector(resolved, source_id=source_id, trust_weight=trust_weight).ingest()
    raise IngestionError(f"Unsupported local file extension {suffix!r} for {resolved}.")
