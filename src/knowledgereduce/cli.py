"""Command-line interface entrypoint for KnowledgeReduce."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, TextIO, cast

import structlog
import typer

from knowledgereduce.export import (
    export_gexf,
    export_graphml,
    export_layer_json,
    export_layer_sharded,
)
from knowledgereduce.ingest import (
    CrawlConfig,
    WebConnector,
    ingest_local_file,
    read_jsonl_checkpoint,
    write_jsonl_checkpoint,
)
from knowledgereduce.map import load_mapped_batches, save_mapped_batches
from knowledgereduce.mcp import create_mcp_server
from knowledgereduce.models import (
    ConflictStrategy,
    KnowledgeReduceError,
    LayerTier,
    MergeMode,
    ReliabilityRating,
    SourceDocument,
)
from knowledgereduce.pipeline import LocalFileSourceConfig, PipelineConfig, PipelineRunner
from knowledgereduce.query import HybridGraphRAGRetriever, QueryBuilder
from knowledgereduce.reduce import IntegrityValidator
from knowledgereduce.stack import StackManager
from knowledgereduce.storage import DuckDBParquetStore

app = typer.Typer(
    name="kr",
    help="KnowledgeReduce: stackable, conflict-aware knowledge graph CLI.",
    no_args_is_help=True,
)


class _DynamicStderr:
    """Delegate writes to the active ``sys.stderr`` stream without caching closed streams."""

    def write(self, message: str) -> int:
        return sys.stderr.write(message)

    def flush(self) -> None:
        sys.stderr.flush()


def _configure_stderr_logging() -> None:
    """Route structlog logs to stderr so stdout remains clean for JSON/MCP stdio."""
    structlog.configure(
        logger_factory=structlog.PrintLoggerFactory(file=cast(TextIO, _DynamicStderr())),
    )


@app.callback()
def main_callback() -> None:
    """KnowledgeReduce CLI root."""
    _configure_stderr_logging()


@app.command("version")
def version_command() -> None:
    """Print the installed KnowledgeReduce version."""
    from knowledgereduce import __version__

    typer.echo(f"knowledgereduce {__version__}")


@app.command("run")
def run_command(
    config_file: Annotated[Path, typer.Argument(help="Path to YAML pipeline config.")],
) -> None:
    """Execute the full Ingest -> Map -> Resolve -> Reduce -> Store pipeline from YAML."""
    try:
        cfg = PipelineConfig.from_yaml(config_file)
        layer_data = PipelineRunner().run(cfg)
        typer.echo(layer_data.layer.model_dump_json(indent=2))
    except KnowledgeReduceError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("ingest")
def ingest_command(
    files: list[Path] = typer.Option([], "--file", "-f", help="Local files to ingest."),  # noqa: B008
    urls: list[str] = typer.Option([], "--url", "-u", help="Seed URLs to crawl."),  # noqa: B008
    output: Path = typer.Option(  # noqa: B008
        Path("checkpoints/01_ingested.jsonl"), "--output", "-o", help="Output JSONL checkpoint."
    ),
    max_depth: int = typer.Option(1, "--max-depth", help="Maximum web crawl depth."),
    max_pages: int = typer.Option(10, "--max-pages", help="Maximum pages per domain."),
) -> None:
    """Ingest local files and/or web pages into a JSONL checkpoint."""
    try:
        docs: list[SourceDocument] = []
        if urls:
            docs.extend(
                WebConnector(
                    CrawlConfig(
                        seed_urls=urls,
                        max_depth=max_depth,
                        max_pages_per_domain=max_pages,
                    )
                ).ingest()
            )
        for path in files:
            docs.extend(ingest_local_file(path))
        out = write_jsonl_checkpoint(docs, output)
        typer.echo(json.dumps({"document_count": len(docs), "checkpoint": str(out)}, indent=2))
    except KnowledgeReduceError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("map")
def map_command(
    input_checkpoint: Path = typer.Option(  # noqa: B008
        Path("checkpoints/01_ingested.jsonl"), "--input", "-i", help="Ingested JSONL checkpoint."
    ),
    output: Path = typer.Option(  # noqa: B008
        Path("checkpoints/02_mapped.jsonl"), "--output", "-o", help="Mapped JSONL checkpoint."
    ),
    mapper: str = typer.Option(
        "deterministic", "--mapper", help="Mapper: deterministic|spacy|structured."
    ),
    min_sentence_length: int = typer.Option(25, "--min-sentence-length"),
    max_workers: int = typer.Option(1, "--workers", help="Parallel worker count."),
) -> None:
    """Map an ingested checkpoint into entities, claims, and relations."""
    try:
        docs = read_jsonl_checkpoint(input_checkpoint, SourceDocument)
        cfg = PipelineConfig(
            layer_id="cli-map",
            layer_name="CLI Map",
            mapper=mapper,
            min_sentence_length=min_sentence_length,
            max_workers=max_workers,
        )
        batches = PipelineRunner().map_documents(docs, cfg)
        out = save_mapped_batches(batches, output)
        typer.echo(
            json.dumps(
                {
                    "batch_count": len(batches),
                    "entities": sum(len(b.entities) for b in batches),
                    "claims": sum(len(b.claims) for b in batches),
                    "relations": sum(len(b.relations) for b in batches),
                    "checkpoint": str(out),
                },
                indent=2,
            )
        )
    except KnowledgeReduceError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("reduce")
def reduce_command(
    layer_id: str = typer.Option(..., "--layer-id", help="Target layer ID."),
    layer_name: str = typer.Option(..., "--name", help="Human-readable layer name."),
    input_checkpoint: Path = typer.Option(  # noqa: B008
        Path("checkpoints/02_mapped.jsonl"), "--input", "-i", help="Mapped JSONL checkpoint."
    ),
    store_dir: Path = typer.Option(  # noqa: B008
        Path(".knowledgereduce_store"), "--store", "-s", help="DuckDB/Parquet store directory."
    ),
    conflict_strategy: ConflictStrategy = typer.Option(  # noqa: B008
        ConflictStrategy.PRESERVE_DISPUTE, "--conflict-strategy"
    ),
    tier: LayerTier = typer.Option(LayerTier.REDUCED, "--tier"),  # noqa: B008
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Resolve and reduce mapped batches into an immutable DuckDB/Parquet layer."""
    try:
        batches = load_mapped_batches(input_checkpoint)
        cfg = PipelineConfig(
            layer_id=layer_id,
            layer_name=layer_name,
            tier=tier,
            store_dir=str(store_dir),
            conflict_strategy=conflict_strategy,
            overwrite=overwrite,
        )
        layer_data = PipelineRunner(store=DuckDBParquetStore(store_dir)).reduce_and_store(
            batches, cfg
        )
        typer.echo(layer_data.layer.model_dump_json(indent=2))
    except KnowledgeReduceError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("stack")
def stack_command(
    layer_ids: list[str] = typer.Option(..., "--layer", "-l", help="Input layer IDs in order."),  # noqa: B008
    target_layer_id: str = typer.Option(..., "--target", "-t", help="New target layer ID."),
    mode: MergeMode = typer.Option(MergeMode.UNION, "--mode", "-m"),  # noqa: B008
    store_dir: Path = typer.Option(  # noqa: B008
        Path(".knowledgereduce_store"), "--store", "-s"
    ),
    conflict_strategy: ConflictStrategy = typer.Option(  # noqa: B008
        ConflictStrategy.PRESERVE_DISPUTE, "--conflict-strategy"
    ),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Stack or combine immutable knowledge layers (overlay, union, intersection, difference)."""
    try:
        store = DuckDBParquetStore(store_dir)
        stacked = StackManager(store).merge_layers(
            layer_ids,
            target_layer_id=target_layer_id,
            mode=mode,
            conflict_strategy=conflict_strategy,
            overwrite=overwrite,
        )
        typer.echo(stacked.layer.model_dump_json(indent=2))
    except KnowledgeReduceError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("diff")
def diff_command(
    left_layer_id: str = typer.Argument(..., help="Left layer ID."),
    right_layer_id: str = typer.Argument(..., help="Right layer ID."),
    store_dir: Path = typer.Option(  # noqa: B008
        Path(".knowledgereduce_store"), "--store", "-s"
    ),
) -> None:
    """Show structural diff between two knowledge layers."""
    try:
        diff = StackManager(DuckDBParquetStore(store_dir)).diff_layers(
            left_layer_id, right_layer_id
        )
        typer.echo(diff.model_dump_json(indent=2))
    except KnowledgeReduceError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("query")
def query_command(
    layer_id: str = typer.Argument(..., help="Layer ID to query."),
    query: str = typer.Option("", "--query", "-q", help="Semantic/lexical query text."),
    category: str | None = typer.Option(None, "--category"),
    tag: str | None = typer.Option(None, "--tag"),
    min_reliability: int = typer.Option(0, "--min-reliability"),
    top_k: int = typer.Option(10, "--top-k"),
    hops: int = typer.Option(1, "--hops"),
    store_dir: Path = typer.Option(  # noqa: B008
        Path(".knowledgereduce_store"), "--store", "-s"
    ),
) -> None:
    """Query claims and entities via Hybrid GraphRAG or structured filters."""
    try:
        store = DuckDBParquetStore(store_dir)
        rel_rating = ReliabilityRating(min_reliability)
        if query.strip() and category is None and tag is None:
            ctx = HybridGraphRAGRetriever(store).retrieve(
                layer_id,
                query,
                top_k=top_k,
                hops=hops,
                min_reliability=rel_rating,
            )
            typer.echo(ctx.model_dump_json(indent=2))
            return

        qb = QueryBuilder(store, layer_id).filter_min_reliability(rel_rating)
        if category is not None:
            qb = qb.filter_category(category)
        if tag is not None:
            qb = qb.filter_tag(tag)
        if query.strip():
            qb = qb.filter_text(query)
        claims = qb.limit(top_k).execute_claims()
        typer.echo(json.dumps([c.model_dump(mode="json") for c in claims], indent=2))
    except KnowledgeReduceError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("export")
def export_command(
    layer_id: str = typer.Argument(..., help="Layer ID to export."),
    format: str = typer.Option("json", "--format", "-f", help="json|sharded_jsonl|graphml|gexf"),
    output: Path = typer.Option(..., "--output", "-o", help="Output file or directory."),  # noqa: B008
    shard_size: int = typer.Option(100, "--shard-size"),
    overwrite: bool = typer.Option(False, "--overwrite"),
    store_dir: Path = typer.Option(  # noqa: B008
        Path(".knowledgereduce_store"), "--store", "-s"
    ),
) -> None:
    """Export a layer to portable JSON, sharded JSONL, GraphML, or GEXF."""
    try:
        layer_data = DuckDBParquetStore(store_dir).load_layer(layer_id)
        fmt = format.strip().lower()
        if fmt == "json":
            out = export_layer_json(layer_data, output)
        elif fmt == "sharded_jsonl":
            out = export_layer_sharded(
                layer_data, output, shard_size=shard_size, overwrite=overwrite
            )
        elif fmt == "graphml":
            out = export_graphml(layer_data, output)
        elif fmt == "gexf":
            out = export_gexf(layer_data, output)
        else:
            raise KnowledgeReduceError(f"Unsupported format {format!r}.")
        typer.echo(str(out))
    except KnowledgeReduceError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("validate")
def validate_command(
    layer_id: str = typer.Argument(..., help="Layer ID to validate."),
    store_dir: Path = typer.Option(  # noqa: B008
        Path(".knowledgereduce_store"), "--store", "-s"
    ),
    strict: bool = typer.Option(False, "--strict", help="Exit non-zero if validation fails."),
) -> None:
    """Validate referential integrity and compute metrics for a stored layer."""
    try:
        layer_data = DuckDBParquetStore(store_dir).load_layer(layer_id)
        report = IntegrityValidator().validate(layer_data, strict=False)
        typer.echo(report.model_dump_json(indent=2))
        if strict and not report.valid:
            raise typer.Exit(code=1)
    except KnowledgeReduceError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("mcp")
def mcp_command(
    workspace: Path = typer.Option(  # noqa: B008
        Path("."), "--workspace", "-w", help="Workspace root directory for path sandboxing."
    ),
    store_dir: str = typer.Option(".knowledgereduce_store", "--store-dir"),
    checkpoint_dir: str = typer.Option(".knowledgereduce_checkpoints", "--checkpoint-dir"),
) -> None:  # pragma: no cover - blocks on stdio transport
    """Start the Antigravity-compatible KnowledgeReduce MCP server over stdio."""
    server = create_mcp_server(
        workspace,
        store_dir=store_dir,
        checkpoint_dir=checkpoint_dir,
    )
    server.run(transport="stdio")


# Re-export LocalFileSourceConfig reference cleanly if inspected
_ = LocalFileSourceConfig

if __name__ == "__main__":  # pragma: no cover
    app()
