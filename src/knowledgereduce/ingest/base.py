"""Base connector protocol and JSONL checkpoint utilities."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

from knowledgereduce.models import IngestionError, SourceDocument

TModel = TypeVar("TModel", bound=BaseModel)


@runtime_checkable
class BaseConnector(Protocol):
    """Protocol implemented by all ingestion connectors."""

    def ingest(self) -> list[SourceDocument]:
        """Fetch or read records into normalized ``SourceDocument`` items."""
        ...


def write_jsonl_checkpoint(items: Sequence[BaseModel], path: Path | str) -> Path:
    """Persist a sequence of Pydantic models as UTF-8 JSON Lines."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(f"{item.model_dump_json()}\n" for item in items)
    out.write_text(content, encoding="utf-8")
    return out


def read_jsonl_checkpoint(path: Path | str, model_cls: type[TModel]) -> list[TModel]:
    """Load a sequence of Pydantic models from a JSON Lines checkpoint file."""
    src = Path(path)
    if not src.is_file():
        raise IngestionError(f"Checkpoint file not found: {src}")
    records: list[TModel] = []
    for line_no, raw_line in enumerate(src.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            records.append(model_cls.model_validate_json(stripped))
        except Exception as exc:
            raise IngestionError(f"Invalid JSONL record in {src} at line {line_no}: {exc}") from exc
    return records
