"""Command-line interface entrypoint for KnowledgeReduce."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, TextIO, cast

import structlog
import typer
import yaml
from pydantic import ValidationError

from knowledgereduce.export import (
    export_gexf,
    export_graphml,
    export_layer_json,
    export_layer_markdown,
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
from knowledgereduce.mcp.server import (
    build_graph_analytics_payload,
    build_layer_lineage_payload,
    build_layers_payload,
)
from knowledgereduce.models import (
    ConflictStrategy,
    IngestionError,
    KnowledgeReduceError,
    LayerTier,
    MergeMode,
    ReliabilityRating,
    SourceDocument,
)
from knowledgereduce.pipeline import (
    LocalFileSourceConfig,
    PipelineConfig,
    PipelineRunner,
    filter_unchanged_documents,
    load_layer_source_hashes,
)
from knowledgereduce.query import HybridGraphRAGRetriever, QueryBuilder
from knowledgereduce.reduce import IntegrityValidator, adjudicate_conflict
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
    except (KnowledgeReduceError, ValidationError, ValueError, yaml.YAMLError, OSError) as exc:
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
    incremental_from: str | None = typer.Option(
        None,
        "--incremental-from",
        help="Optional prior layer ID for SHA-256 skip-unchanged delta ingestion.",
    ),
    store_dir: Path = typer.Option(  # noqa: B008
        Path(".knowledgereduce_store"), "--store", "-s", help="DuckDB/Parquet store directory."
    ),
) -> None:
    """Ingest local files and/or web pages into a JSONL checkpoint."""
    try:
        if not files and not urls:
            raise IngestionError("Provide at least one --file or --url input to ingest.")
        known_by_uri: dict[str, str] = {}
        known_by_source_id: dict[str, str] = {}
        if incremental_from is not None:
            with DuckDBParquetStore(store_dir) as store:
                known_by_uri, known_by_source_id = load_layer_source_hashes(store, incremental_from)

        skipped_unchanged = 0
        docs: list[SourceDocument] = []
        if urls:
            connector = WebConnector(
                CrawlConfig(
                    seed_urls=urls,
                    max_depth=max_depth,
                    max_pages_per_domain=max_pages,
                    known_hashes=known_by_uri,
                )
            )
            docs.extend(connector.ingest())
            skipped_unchanged += connector.skipped_unchanged

        local_docs: list[SourceDocument] = []
        for path in files:
            local_docs.extend(ingest_local_file(path))
        if known_by_uri or known_by_source_id:
            kept_local, local_skipped = filter_unchanged_documents(
                local_docs, known_by_uri, known_by_source_id
            )
            docs.extend(kept_local)
            skipped_unchanged += local_skipped
        else:
            docs.extend(local_docs)

        out = write_jsonl_checkpoint(docs, output)
        typer.echo(
            json.dumps(
                {
                    "document_count": len(docs),
                    "skipped_unchanged": skipped_unchanged,
                    "checkpoint": str(out),
                },
                indent=2,
            )
        )
    except (KnowledgeReduceError, ValidationError, ValueError) as exc:
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
    except (KnowledgeReduceError, ValidationError, ValueError) as exc:
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
    parent_layers: list[str] = typer.Option(  # noqa: B008
        [], "--parent-layer", help="Optional parent layer IDs to record in layer lineage."
    ),
    build_index: bool = typer.Option(
        True,
        "--build-index/--no-build-index",
        help="Pre-build persisted claim_embeddings.parquet for warm GraphRAG.",
    ),
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
            build_embeddings_index=build_index,
            overwrite=overwrite,
        )
        with DuckDBParquetStore(store_dir) as store:
            layer_data = PipelineRunner(store=store).reduce_and_store(
                batches,
                cfg,
                parent_layer_ids=parent_layers or None,
            )
        typer.echo(layer_data.layer.model_dump_json(indent=2))
    except (KnowledgeReduceError, ValidationError, ValueError) as exc:
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
    reconcile: bool = typer.Option(
        False,
        "--reconcile",
        help="Disambiguate entities and detect conflicts across distinct IDs.",
    ),
    build_index: bool = typer.Option(
        True,
        "--build-index/--no-build-index",
        help="Pre-build persisted claim_embeddings.parquet for warm GraphRAG.",
    ),
    overwrite: bool = typer.Option(False, "--overwrite"),
) -> None:
    """Stack or combine immutable knowledge layers (overlay, union, intersection, difference)."""
    try:
        with DuckDBParquetStore(store_dir) as store:
            stacked = StackManager(store).merge_layers(
                layer_ids,
                target_layer_id=target_layer_id,
                mode=mode,
                conflict_strategy=conflict_strategy,
                reconcile=reconcile,
                overwrite=overwrite,
            )
            if build_index and stacked.claims:
                HybridGraphRAGRetriever(store).build_index(target_layer_id)
        typer.echo(stacked.layer.model_dump_json(indent=2))
    except (KnowledgeReduceError, ValidationError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("index")
def index_command(
    layer_id: str = typer.Argument(..., help="Layer ID to index."),
    store_dir: Path = typer.Option(  # noqa: B008
        Path(".knowledgereduce_store"), "--store", "-s"
    ),
) -> None:
    """Build or refresh persisted claim embeddings for a stored layer."""
    try:
        with DuckDBParquetStore(store_dir) as store:
            indexed = HybridGraphRAGRetriever(store).build_index(layer_id)
        typer.echo(json.dumps({"layer_id": layer_id, "embeddings_indexed": indexed}, indent=2))
    except (KnowledgeReduceError, ValidationError, ValueError) as exc:
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
        with DuckDBParquetStore(store_dir) as store:
            diff = StackManager(store).diff_layers(left_layer_id, right_layer_id)
        typer.echo(diff.model_dump_json(indent=2))
    except (KnowledgeReduceError, ValidationError, ValueError) as exc:
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
        rel_rating = ReliabilityRating(min_reliability)
        with DuckDBParquetStore(store_dir) as store:
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
    except (KnowledgeReduceError, ValidationError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("export")
def export_command(
    layer_id: str = typer.Argument(..., help="Layer ID to export."),
    format: str = typer.Option(
        "json", "--format", "-f", help="json|sharded_jsonl|graphml|gexf|markdown"
    ),
    output: Path = typer.Option(..., "--output", "-o", help="Output file or directory."),  # noqa: B008
    shard_size: int = typer.Option(100, "--shard-size"),
    overwrite: bool = typer.Option(False, "--overwrite"),
    store_dir: Path = typer.Option(  # noqa: B008
        Path(".knowledgereduce_store"), "--store", "-s"
    ),
) -> None:
    """Export a layer to portable JSON, sharded JSONL, GraphML, GEXF, or Markdown."""
    try:
        with DuckDBParquetStore(store_dir) as store:
            layer_data = store.load_layer(layer_id)
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
        elif fmt == "markdown":
            out = export_layer_markdown(layer_data, output)
        else:
            raise KnowledgeReduceError(f"Unsupported format {format!r}.")
        typer.echo(str(out))
    except (KnowledgeReduceError, ValidationError, ValueError) as exc:
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
        with DuckDBParquetStore(store_dir) as store:
            layer_data = store.load_layer(layer_id)
        report = IntegrityValidator().validate(layer_data, strict=False)
        typer.echo(report.model_dump_json(indent=2))
        if strict and not report.valid:
            raise typer.Exit(code=1)
    except (KnowledgeReduceError, ValidationError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("conflicts")
def conflicts_command(
    layer_id: str = typer.Argument(..., help="Layer ID to inspect."),
    show_all: bool = typer.Option(False, "--all", help="Include already adjudicated conflicts."),
    limit: int = typer.Option(100, "--limit", help="Maximum conflicts to return."),
    store_dir: Path = typer.Option(  # noqa: B008
        Path(".knowledgereduce_store"), "--store", "-s"
    ),
) -> None:
    """List preserved or adjudicated conflicts in a stored layer."""
    try:
        with DuckDBParquetStore(store_dir) as store:
            conflicts = store.list_conflicts(
                layer_id,
                needs_review=None if show_all else True,
                limit=limit,
            )
        typer.echo(
            json.dumps(
                {
                    "layer_id": layer_id,
                    "count": len(conflicts),
                    "conflicts": [cf.model_dump(mode="json") for cf in conflicts],
                },
                indent=2,
            )
        )
    except (KnowledgeReduceError, ValidationError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("resolve-conflict")
def resolve_conflict_command(
    base_layer_id: str = typer.Argument(..., help="Base layer ID containing the conflict."),
    conflict_id: str = typer.Option(..., "--conflict-id", help="Conflict ID to adjudicate."),
    target_layer_id: str = typer.Option(
        ..., "--target", "-t", help="Target CURATED child layer ID."
    ),
    winning_value: str = typer.Option(..., "--winning-value", help="Adjudicated canonical value."),
    winning_source_id: str | None = typer.Option(None, "--winning-source-id"),
    notes: str = typer.Option("", "--notes", help="Adjudication rationale notes."),
    overwrite: bool = typer.Option(False, "--overwrite"),
    store_dir: Path = typer.Option(  # noqa: B008
        Path(".knowledgereduce_store"), "--store", "-s"
    ),
) -> None:
    """Adjudicate a conflict non-destructively into a new CURATED child layer."""
    try:
        with DuckDBParquetStore(store_dir) as store:
            base_data = store.load_layer(base_layer_id)
            curated, updated_conflict = adjudicate_conflict(
                base_data,
                conflict_id=conflict_id,
                target_layer_id=target_layer_id,
                winning_value=winning_value,
                winning_source_id=winning_source_id,
                resolution_notes=notes or "Adjudicated via CLI resolve-conflict.",
            )
            store.save_layer(curated, overwrite=overwrite)
        typer.echo(
            json.dumps(
                {
                    "layer": curated.layer.model_dump(mode="json"),
                    "resolved_conflict": updated_conflict.model_dump(mode="json"),
                },
                indent=2,
            )
        )
    except (KnowledgeReduceError, ValidationError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("layers")
def layers_command(
    store_dir: Path = typer.Option(  # noqa: B008
        Path(".knowledgereduce_store"), "--store", "-s"
    ),
) -> None:
    """List persisted knowledge layers and their metadata."""
    try:
        with DuckDBParquetStore(store_dir) as store:
            payload = build_layers_payload(store)
        typer.echo(json.dumps(payload, indent=2))
    except (KnowledgeReduceError, ValidationError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("lineage")
def lineage_command(
    layer_id: str = typer.Argument(..., help="Layer ID to inspect."),
    store_dir: Path = typer.Option(  # noqa: B008
        Path(".knowledgereduce_store"), "--store", "-s"
    ),
) -> None:
    """Display ancestor and descendant layer lineage for a stored layer."""
    try:
        with DuckDBParquetStore(store_dir) as store:
            mgr = StackManager(store)
            payload = build_layer_lineage_payload(mgr, layer_id)
        typer.echo(json.dumps(payload, indent=2))
    except (KnowledgeReduceError, ValidationError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("analyze")
def analyze_command(
    layer_id: str = typer.Argument(..., help="Layer ID to analyze."),
    metric: str = typer.Option("pagerank", "--metric", "-m", help="pagerank|degree|betweenness"),
    top_k: int = typer.Option(10, "--top-k", help="Maximum ranked central nodes."),
    communities: bool = typer.Option(
        True, "--communities/--no-communities", help="Compute Louvain communities."
    ),
    path_from: str | None = typer.Option(None, "--path-from", help="Shortest-path source ID."),
    path_to: str | None = typer.Option(None, "--path-to", help="Shortest-path target ID."),
    max_hops: int = typer.Option(6, "--max-hops", help="Maximum shortest-path hop count."),
    store_dir: Path = typer.Option(  # noqa: B008
        Path(".knowledgereduce_store"), "--store", "-s"
    ),
) -> None:
    """Compute node centrality, Louvain communities, and optional shortest paths."""
    try:
        with DuckDBParquetStore(store_dir) as store:
            payload = build_graph_analytics_payload(
                store,
                layer_id,
                metric=metric,
                top_k=top_k,
                include_communities=communities,
                path_source_id=path_from,
                path_target_id=path_to,
                max_hops=max_hops,
            )
        typer.echo(json.dumps(payload, indent=2))
    except (KnowledgeReduceError, ValidationError, ValueError) as exc:
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
