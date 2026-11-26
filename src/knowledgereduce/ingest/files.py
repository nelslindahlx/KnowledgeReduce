"""Local file connectors (CSV, JSON, JSONL, Markdown, plain text)."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import sys
from collections.abc import Sequence
from datetime import UTC, date, datetime
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
            try:
                parsed = yaml.safe_load(fm_raw)
            except yaml.YAMLError:
                return {}, raw
            if isinstance(parsed, dict):
                return parsed, body.strip()
            break
    return {}, raw


def _json_safe_value(value: Any) -> Any:
    """Recursively normalize YAML/frontmatter values into JSON-serializable primitives."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(item) for item in value]
    return str(value)


def _parse_frontmatter_date(value: Any) -> datetime | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    raw = str(value).strip()
    if not raw:
        return None
    try:
        parsed_dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return (
            parsed_dt.replace(tzinfo=UTC) if parsed_dt.tzinfo is None else parsed_dt.astimezone(UTC)
        )
    except ValueError:
        try:
            parsed_d = date.fromisoformat(raw)
        except ValueError:
            return None
        return datetime(parsed_d.year, parsed_d.month, parsed_d.day, tzinfo=UTC)


def _normalize_frontmatter_tags(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        items = [str(item).strip() for item in value]
    elif isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    else:
        return []
    return list(dict.fromkeys(item for item in items if item))


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
        raw_author = fm.get("author")
        fm_author = str(raw_author).strip() if raw_author is not None else ""
        doc_author = self.author or (fm_author or None)
        published_at = _parse_frontmatter_date(
            fm.get("published_at") if "published_at" in fm else fm.get("date")
        )
        tags = _normalize_frontmatter_tags(fm.get("tags"))
        return [
            SourceDocument(
                source_id=self.source_id or _file_source_id("md", resolved),
                uri=resolved.as_uri(),
                source_type=SourceType.MARKDOWN,
                title=doc_title,
                author=doc_author,
                published_at=published_at,
                fetched_at=utc_now(),
                content=body.strip(),
                trust_weight=self.trust_weight,
                metadata={"frontmatter": _json_safe_value(fm), "tags": tags},
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


class HTMLConnector:
    """Ingest a local HTML file into a normalized ``SourceDocument`` using offline extraction."""

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
        from knowledgereduce.ingest.web import _parse_optional_iso, extract_main_text

        resolved = _resolve_input_path(self.path, self.base_dir)
        raw_html = resolved.read_text(encoding="utf-8")
        text, meta = extract_main_text(raw_html, resolved.as_uri())
        doc_title = self.title or meta.get("title") or resolved.stem
        doc_author = self.author or meta.get("author")
        published_at = _parse_optional_iso(meta.get("published_at"))
        return [
            SourceDocument(
                source_id=self.source_id or _file_source_id("html", resolved),
                uri=resolved.as_uri(),
                source_type=SourceType.HTML,
                title=doc_title,
                author=doc_author,
                published_at=published_at,
                fetched_at=utc_now(),
                content=text,
                trust_weight=self.trust_weight,
                metadata={
                    "description": meta.get("description") or "",
                    "raw_bytes": len(raw_html.encode("utf-8")),
                },
            )
        ]


_SUPPORTED_LOCAL_SUFFIXES = frozenset(
    {".csv", ".json", ".jsonl", ".md", ".markdown", ".html", ".htm", ".txt", ".pdf"}
)


class PDFConnector:
    """Ingest a local PDF file into a normalized ``SourceDocument`` (requires ``[pdf]`` extra)."""

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
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise IngestionError(
                "PDF ingestion requires optional `[pdf]` dependencies (`pypdf>=5.0`). "
                "Install with `uv sync --extra pdf`."
            ) from exc

        reader = PdfReader(str(resolved))
        reader_pages = getattr(reader, "pages", [])
        pages = [(page.extract_text() or "").strip() for page in reader_pages]
        content = "\n\n".join(page for page in pages if page)
        pdf_meta = getattr(reader, "metadata", None)
        meta_title = (
            pdf_meta.get("/Title")
            if isinstance(pdf_meta, dict)
            else getattr(pdf_meta, "title", None)
        )
        meta_author = (
            pdf_meta.get("/Author")
            if isinstance(pdf_meta, dict)
            else getattr(pdf_meta, "author", None)
        )
        return [
            SourceDocument(
                source_id=self.source_id or _file_source_id("pdf", resolved),
                uri=resolved.as_uri(),
                source_type=SourceType.PDF,
                title=self.title
                or (str(meta_title).strip() if meta_title else "")
                or resolved.stem,
                author=self.author or (str(meta_author).strip() if meta_author else None),
                fetched_at=utc_now(),
                content=content,
                trust_weight=self.trust_weight,
                metadata={"page_count": len(reader_pages)},
            )
        ]


class DirectoryConnector:
    """Ingest supported local files from a directory using sandboxed glob matching."""

    def __init__(
        self,
        path: Path | str,
        *,
        patterns: Sequence[str] = ("**/*",),
        recursive: bool = True,
        trust_weight: float = 0.75,
        base_dir: Path | str | None = None,
    ) -> None:
        self.path = path
        self.patterns = tuple(patterns) if patterns else ("**/*",)
        self.recursive = recursive
        self.trust_weight = trust_weight
        self.base_dir = base_dir

    def ingest(self) -> list[SourceDocument]:
        return ingest_local_directory(
            self.path,
            patterns=self.patterns,
            recursive=self.recursive,
            trust_weight=self.trust_weight,
            base_dir=self.base_dir,
        )


def _has_pypdf_installed() -> bool:
    return "pypdf" in sys.modules or importlib.util.find_spec("pypdf") is not None


def ingest_local_directory(
    directory: Path | str,
    *,
    patterns: Sequence[str] = ("**/*",),
    recursive: bool = True,
    trust_weight: float = 0.75,
    base_dir: Path | str | None = None,
) -> list[SourceDocument]:
    """Discover and ingest supported files under *directory* with symlink containment checks."""
    resolved_dir = (
        ensure_within_base(directory, base_dir)
        if base_dir is not None
        else Path(directory).resolve()
    )
    if not resolved_dir.is_dir():
        raise IngestionError(f"Input directory not found: {resolved_dir}")

    effective_patterns = tuple(patterns) if patterns else ("**/*",)
    pypdf_available = _has_pypdf_installed()
    matched_by_rel: dict[str, Path] = {}

    for raw_pattern in effective_patterns:
        pattern = raw_pattern
        if not recursive and pattern.startswith("**/"):
            pattern = pattern[3:] or "*"
        iterator = resolved_dir.rglob(pattern) if recursive else resolved_dir.glob(pattern)
        explicit_pdf = pattern.lower().endswith(".pdf")
        for candidate in iterator:
            rel_lexical = candidate.relative_to(resolved_dir)
            if any(part.startswith(".") for part in rel_lexical.parts):
                continue
            safe_path = ensure_within_base(candidate, resolved_dir)
            if not safe_path.is_file():
                continue
            suffix = safe_path.suffix.lower()
            if suffix not in _SUPPORTED_LOCAL_SUFFIXES:
                continue
            if suffix == ".pdf" and not pypdf_available and not explicit_pdf:
                continue
            rel_key = safe_path.relative_to(resolved_dir).as_posix()
            matched_by_rel.setdefault(rel_key, safe_path)

    docs: list[SourceDocument] = []
    for rel_key in sorted(matched_by_rel):
        file_path = matched_by_rel[rel_key]
        docs.extend(
            ingest_local_file(
                file_path,
                trust_weight=trust_weight,
                base_dir=resolved_dir,
            )
        )
    return docs


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
    if suffix in {".html", ".htm"}:
        return HTMLConnector(resolved, source_id=source_id, trust_weight=trust_weight).ingest()
    if suffix == ".pdf":
        return PDFConnector(resolved, source_id=source_id, trust_weight=trust_weight).ingest()
    if suffix == ".txt":
        return TextConnector(resolved, source_id=source_id, trust_weight=trust_weight).ingest()
    raise IngestionError(f"Unsupported local file extension {suffix!r} for {resolved}.")
