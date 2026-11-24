"""Antigravity-compatible stdio MCP server exposing the full KnowledgeReduce workflow."""

from __future__ import annotations

import functools
import inspect
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import ValidationError

from knowledgereduce.export import (
    export_gexf,
    export_graphml,
    export_layer_json,
    export_layer_sharded,
)
from knowledgereduce.ingest import (
    AsyncWebCrawler,
    CrawlConfig,
    ingest_local_file,
    write_jsonl_checkpoint,
)
from knowledgereduce.map import (
    load_mapped_batches,
    save_mapped_batches,
)
from knowledgereduce.models import (
    ConflictResolutionError,
    ConflictStrategy,
    KnowledgeLayer,
    KnowledgeReduceError,
    LayerData,
    LayerTier,
    MappedBatch,
    MergeMode,
    ReliabilityRating,
    SourceDocument,
    StorageError,
    utc_now,
)
from knowledgereduce.pipeline import PipelineConfig, PipelineRunner
from knowledgereduce.query import HybridGraphRAGRetriever, QueryBuilder
from knowledgereduce.reduce import IntegrityValidator, KnowledgeReducer
from knowledgereduce.security import ResolverFn, ensure_within_base
from knowledgereduce.stack import StackManager
from knowledgereduce.storage import DuckDBParquetStore

_FnT = TypeVar("_FnT", bound=Callable[..., Any])


def _mcp_error_boundary(fn: _FnT) -> _FnT:
    """Translate domain and validation errors to actionable MCP ``ToolError`` responses."""
    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await fn(*args, **kwargs)
            except (KnowledgeReduceError, ValidationError, ValueError) as exc:
                raise ToolError(str(exc)) from exc

        return _async_wrapper  # type: ignore[return-value]

    @functools.wraps(fn)
    def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except (KnowledgeReduceError, ValidationError, ValueError) as exc:
            raise ToolError(str(exc)) from exc

    return _sync_wrapper  # type: ignore[return-value]


def create_mcp_server(
    workspace_dir: Path | str,
    *,
    store_dir: Path | str | None = None,
    checkpoint_dir: Path | str | None = None,
    web_transport: httpx.AsyncBaseTransport | None = None,
    dns_resolver: ResolverFn | None = None,
) -> MCPServer:
    """Create a workspace-scoped ``MCPServer`` exposing KnowledgeReduce tools over stdio."""
    base = Path(workspace_dir).resolve()
    base.mkdir(parents=True, exist_ok=True)
    resolved_store_dir = ensure_within_base(store_dir or ".knowledgereduce_store", base)
    resolved_ckpt_dir = ensure_within_base(checkpoint_dir or ".knowledgereduce_checkpoints", base)
    resolved_store_dir.mkdir(parents=True, exist_ok=True)
    resolved_ckpt_dir.mkdir(parents=True, exist_ok=True)

    store = DuckDBParquetStore(resolved_store_dir)
    stack_mgr = StackManager(store)
    retriever = HybridGraphRAGRetriever(store)
    validator = IntegrityValidator()

    server = MCPServer(
        name="knowledgereduce",
        instructions=(
            "KnowledgeReduce MCP Server: ingest web/local sources, run local or agent-submitted "
            "entity/claim/relation mapping, reduce & resolve conflicts into immutable Parquet "
            "layers, stack layers, and run Hybrid GraphRAG queries."
        ),
    )

    @server.tool()
    @_mcp_error_boundary
    async def ingest_source(
        local_files: list[dict[str, Any]] | None = None,
        crawl_config: dict[str, Any] | None = None,
        checkpoint_name: str = "01_ingested.jsonl",
    ) -> dict[str, Any]:
        """Ingest local files and/or web URLs into a workspace JSONL checkpoint."""
        docs: list[SourceDocument] = []
        if crawl_config is not None:
            cfg = CrawlConfig.model_validate(crawl_config)
            crawler = AsyncWebCrawler(cfg, transport=web_transport, resolver=dns_resolver)
            docs.extend(await crawler.crawl())

        for item in local_files or []:
            raw_path = str(item.get("path", ""))
            safe_file = ensure_within_base(raw_path, base)
            source_id = str(item["source_id"]) if item.get("source_id") else None
            trust_weight = float(item.get("trust_weight", 0.75))
            docs.extend(
                ingest_local_file(
                    safe_file,
                    source_id=source_id,
                    trust_weight=trust_weight,
                    base_dir=base,
                )
            )

        ckpt_path = ensure_within_base(checkpoint_name, resolved_ckpt_dir)
        write_jsonl_checkpoint(docs, ckpt_path)
        return {
            "document_count": len(docs),
            "source_ids": [d.source_id for d in docs],
            "checkpoint_path": str(ckpt_path.relative_to(base)),
        }

    @server.tool()
    @_mcp_error_boundary
    def run_local_map(
        ingested_checkpoint: str = "01_ingested.jsonl",
        mapped_checkpoint: str = "02_mapped.jsonl",
        mapper: str = "deterministic",
        min_sentence_length: int = 25,
        spacy_model: str = "en_core_web_sm",
    ) -> dict[str, Any]:
        """Map an ingested checkpoint locally into entities, claims, and relations."""
        in_path = ensure_within_base(ingested_checkpoint, resolved_ckpt_dir)
        out_path = ensure_within_base(mapped_checkpoint, resolved_ckpt_dir)

        from knowledgereduce.ingest import read_jsonl_checkpoint

        docs = read_jsonl_checkpoint(in_path, SourceDocument)
        cfg = PipelineConfig(
            layer_id="mcp-map-tmp",
            layer_name="MCP Map",
            store_dir=str(resolved_store_dir),
            mapper=mapper,
            min_sentence_length=min_sentence_length,
            spacy_model=spacy_model,
        )
        runner = PipelineRunner(store=store)
        batches = runner.map_documents(docs, cfg)
        save_mapped_batches(batches, out_path)
        return {
            "batch_count": len(batches),
            "entities": sum(len(b.entities) for b in batches),
            "claims": sum(len(b.claims) for b in batches),
            "relations": sum(len(b.relations) for b in batches),
            "checkpoint_path": str(out_path.relative_to(base)),
        }

    @server.tool()
    @_mcp_error_boundary
    def submit_mapped_batch(
        batches: list[dict[str, Any]],
        mapped_checkpoint: str = "02_mapped.jsonl",
        append: bool = True,
    ) -> dict[str, Any]:
        """Validate and store agent-extracted MappedBatch payloads into the Map checkpoint."""
        out_path = ensure_within_base(mapped_checkpoint, resolved_ckpt_dir)
        validated = [MappedBatch.model_validate(item) for item in batches]
        combined: list[MappedBatch] = []
        if append and out_path.is_file():
            combined.extend(load_mapped_batches(out_path))
        combined.extend(validated)
        save_mapped_batches(combined, out_path)
        return {
            "submitted_batches": len(validated),
            "total_batches": len(combined),
            "total_entities": sum(len(b.entities) for b in combined),
            "total_claims": sum(len(b.claims) for b in combined),
            "total_relations": sum(len(b.relations) for b in combined),
            "checkpoint_path": str(out_path.relative_to(base)),
        }

    @server.tool()
    @_mcp_error_boundary
    def resolve_and_reduce(
        layer_id: str,
        layer_name: str,
        mapped_checkpoint: str = "02_mapped.jsonl",
        conflict_strategy: str = "preserve_dispute",
        tier: str = "reduced",
        lexical_threshold: float = 0.88,
        semantic_threshold: float = 0.84,
        min_claim_length: int = 20,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Resolve entities/claims, adjudicate conflicts, and store an immutable Parquet layer."""
        in_path = ensure_within_base(mapped_checkpoint, resolved_ckpt_dir)
        batches = load_mapped_batches(in_path)
        reducer = KnowledgeReducer(
            lexical_threshold=lexical_threshold,
            semantic_threshold=semantic_threshold,
            min_claim_length=min_claim_length,
            conflict_strategy=ConflictStrategy(conflict_strategy),
        )
        layer_data = reducer.reduce_batches(
            batches,
            layer_id=layer_id,
            layer_name=layer_name,
            tier=LayerTier(tier),
            strict_validation=True,
        )
        store.save_layer(layer_data, overwrite=overwrite)
        return layer_data.layer.model_dump(mode="json")

    @server.tool()
    @_mcp_error_boundary
    def stack_layers(
        layer_ids: list[str],
        target_layer_id: str,
        mode: str = "union",
        target_name: str | None = None,
        conflict_strategy: str = "preserve_dispute",
        tier: str = "stacked",
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Compose immutable layers via overlay, union, intersection, or difference."""
        stacked = stack_mgr.merge_layers(
            layer_ids,
            target_layer_id=target_layer_id,
            target_name=target_name,
            mode=MergeMode(mode),
            tier=LayerTier(tier),
            conflict_strategy=ConflictStrategy(conflict_strategy),
            overwrite=overwrite,
        )
        return stacked.layer.model_dump(mode="json")

    @server.tool()
    @_mcp_error_boundary
    def diff_layers(left_layer_id: str, right_layer_id: str) -> dict[str, Any]:
        """Compute structural differences between two layers."""
        return stack_mgr.diff_layers(left_layer_id, right_layer_id).model_dump(mode="json")

    @server.tool()
    @_mcp_error_boundary
    def query_knowledge_graph(
        layer_id: str,
        query: str = "",
        category: str | None = None,
        tag: str | None = None,
        entity_type: str | None = None,
        min_reliability: int = 0,
        needs_review: bool | None = None,
        top_k: int = 10,
        hops: int = 1,
    ) -> dict[str, Any]:
        """Query claims & entities via Hybrid GraphRAG or structured filters."""
        min_rel = ReliabilityRating(min_reliability)
        if query.strip() and category is None and tag is None and needs_review is None:
            ctx = retriever.retrieve(
                layer_id,
                query,
                top_k=top_k,
                hops=hops,
                min_reliability=min_rel,
            )
            return ctx.model_dump(mode="json")

        qb = QueryBuilder(store, layer_id).filter_min_reliability(min_rel)
        if category is not None:
            qb = qb.filter_category(category)
        if tag is not None:
            qb = qb.filter_tag(tag)
        if needs_review is not None:
            qb = qb.filter_needs_review(needs_review)
        if entity_type is not None:
            qb = qb.filter_entity_type(entity_type)
        if query.strip():
            qb = qb.filter_text(query)
        qb = qb.limit(top_k)
        return {
            "layer_id": layer_id,
            "query": query,
            "claims": [c.model_dump(mode="json") for c in qb.execute_claims()],
            "entities": [e.model_dump(mode="json") for e in qb.execute_entities()],
        }

    @server.tool()
    @_mcp_error_boundary
    def list_conflicts(
        layer_id: str,
        needs_review_only: bool = True,
        limit: int = 100,
    ) -> dict[str, Any]:
        """List conflict records for *layer_id*."""
        conflicts = store.list_conflicts(
            layer_id,
            needs_review=True if needs_review_only else None,
            limit=limit,
        )
        return {
            "layer_id": layer_id,
            "count": len(conflicts),
            "conflicts": [cf.model_dump(mode="json") for cf in conflicts],
        }

    @server.tool()
    @_mcp_error_boundary
    def resolve_conflict(
        base_layer_id: str,
        conflict_id: str,
        target_layer_id: str,
        winning_value: str,
        winning_source_id: str | None = None,
        resolution_notes: str = "",
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Adjudicate a conflict non-destructively into a new CURATED child layer."""
        base_data = store.load_layer(base_layer_id)
        target_conflict = next(
            (cf for cf in base_data.conflicts if cf.conflict_id == conflict_id),
            None,
        )
        if target_conflict is None:
            raise ConflictResolutionError(
                f"Conflict {conflict_id!r} not found in layer {base_layer_id!r}."
            )

        participating_claim_ids = {
            str(cid) for cand in target_conflict.candidates for cid in (cand.get("claim_ids") or [])
        }
        updated_conflict = target_conflict.model_copy(
            update={
                "winning_value": winning_value,
                "winning_source_id": winning_source_id or target_conflict.winning_source_id,
                "needs_review": False,
                "resolved_at": utc_now(),
                "resolution_notes": resolution_notes or "Adjudicated via MCP resolve_conflict.",
            }
        )

        updated_conflicts = [
            updated_conflict if cf.conflict_id == conflict_id else cf for cf in base_data.conflicts
        ]
        updated_claims = [
            clm.model_copy(update={"needs_review": False})
            if clm.claim_id in participating_claim_ids
            else clm
            for clm in base_data.claims
        ]
        updated_relations = [
            rel
            for rel in base_data.relations
            if not (
                rel.relation_type == "CONTRADICTS"
                and rel.source_id in participating_claim_ids
                and rel.target_id in participating_claim_ids
            )
        ]

        new_layer = KnowledgeLayer(
            layer_id=target_layer_id,
            name=f"{base_data.layer.name} (Adjudicated)",
            tier=LayerTier.CURATED,
            parent_layer_ids=[base_layer_id],
            created_at=utc_now(),
            stats={
                **base_data.layer.stats,
                "open_conflicts": sum(1 for cf in updated_conflicts if cf.needs_review),
                "resolved_conflict_id": conflict_id,
            },
        )
        curated = LayerData(
            layer=new_layer,
            sources=base_data.sources,
            entities=base_data.entities,
            claims=updated_claims,
            relations=updated_relations,
            conflicts=updated_conflicts,
        )
        validator.validate(curated, strict=True)
        store.save_layer(curated, overwrite=overwrite)
        return {
            "layer": new_layer.model_dump(mode="json"),
            "resolved_conflict": updated_conflict.model_dump(mode="json"),
        }

    @server.tool()
    @_mcp_error_boundary
    def export_layer(
        layer_id: str,
        format: str,
        output_path: str,
        shard_size: int = 100,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Export *layer_id* to json, sharded_jsonl, graphml, gexf, or parquet inside workspace."""
        layer_data = store.load_layer(layer_id)
        fmt = format.strip().lower()
        if fmt == "json":
            out = export_layer_json(layer_data, output_path, base_dir=base)
        elif fmt == "sharded_jsonl":
            out = export_layer_sharded(
                layer_data,
                output_path,
                shard_size=shard_size,
                base_dir=base,
                overwrite=overwrite,
            )
        elif fmt == "graphml":
            out = export_graphml(layer_data, output_path, base_dir=base)
        elif fmt == "gexf":
            out = export_gexf(layer_data, output_path, base_dir=base)
        elif fmt == "parquet":
            out = ensure_within_base(output_path, base)
            src_dir = ensure_within_base(layer_id, resolved_store_dir / "layers")
            if out.exists():
                if not overwrite:
                    raise StorageError(f"Output directory {out} exists (pass overwrite=True).")
                shutil.rmtree(out)
            shutil.copytree(src_dir, out)
        else:
            raise StorageError(
                f"Unsupported export format {format!r}. "
                "Choose json, sharded_jsonl, graphml, gexf, or parquet."
            )
        return {
            "layer_id": layer_id,
            "format": fmt,
            "output_path": str(out.relative_to(base)),
        }

    @server.tool()
    @_mcp_error_boundary
    def validate_layer(layer_id: str) -> dict[str, Any]:
        """Run integrity validation and compute graph telemetry for *layer_id*."""
        layer_data = store.load_layer(layer_id)
        return validator.validate(layer_data, strict=False).model_dump(mode="json")

    return server
