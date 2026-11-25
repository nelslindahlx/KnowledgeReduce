"""Antigravity-compatible stdio MCP server exposing the full KnowledgeReduce workflow."""

from __future__ import annotations

import functools
import inspect
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, TypeVar, cast

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import ValidationError

from knowledgereduce.export import (
    export_gexf,
    export_graphml,
    export_layer_json,
    export_layer_markdown,
    export_layer_sharded,
)
from knowledgereduce.ingest import (
    AsyncWebCrawler,
    CrawlConfig,
    ingest_local_directory,
    ingest_local_file,
    read_jsonl_checkpoint,
    write_jsonl_checkpoint,
)
from knowledgereduce.map import (
    load_mapped_batches,
    save_mapped_batches,
)
from knowledgereduce.models import (
    ConflictStrategy,
    KnowledgeReduceError,
    LayerTier,
    MappedBatch,
    MergeMode,
    ReliabilityRating,
    SourceDocument,
    StorageError,
)
from knowledgereduce.pipeline import (
    PipelineConfig,
    PipelineRunner,
    filter_unchanged_documents,
    load_layer_source_hashes,
)
from knowledgereduce.query import (
    HybridGraphRAGRetriever,
    QueryBuilder,
    bounded_shortest_path,
    central_nodes,
    detect_communities,
)
from knowledgereduce.reduce import (
    ConflictResolutionDecision,
    IntegrityValidator,
    KnowledgeReducer,
    adjudicate_conflict,
    adjudicate_conflicts,
)
from knowledgereduce.security import ResolverFn, ensure_within_base
from knowledgereduce.stack import StackManager
from knowledgereduce.storage import DuckDBParquetStore, GraphStore, layer_data_to_networkx

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


_VALID_METRICS = frozenset({"pagerank", "degree", "betweenness"})


def build_layers_payload(store: GraphStore) -> dict[str, Any]:
    """Return a serialized summary of all stored layers in chronological order."""
    layers = store.list_layers()
    return {
        "count": len(layers),
        "layers": [layer.model_dump(mode="json") for layer in layers],
    }


def build_layer_lineage_payload(stack_mgr: StackManager, layer_id: str) -> dict[str, Any]:
    """Return direct parents, ancestors, descendants, and lineage edges for *layer_id*."""
    ancestors = stack_mgr.get_ancestors(layer_id)
    descendants = stack_mgr.get_descendants(layer_id)
    layer_meta = stack_mgr.store.get_layer_manifest(layer_id)
    dag = stack_mgr.build_lineage_graph()
    relevant = {layer_id, *ancestors, *descendants}
    lineage_edges = sorted(
        (
            {"parent": str(src), "child": str(dst)}
            for src, dst in dag.edges()
            if str(src) in relevant and str(dst) in relevant
        ),
        key=lambda item: (item["parent"], item["child"]),
    )
    return {
        "layer_id": layer_id,
        "layer": layer_meta.model_dump(mode="json"),
        "parents": list(layer_meta.parent_layer_ids),
        "ancestors": ancestors,
        "descendants": descendants,
        "lineage_edges": lineage_edges,
    }


def build_graph_analytics_payload(
    store: GraphStore,
    layer_id: str,
    *,
    metric: str = "pagerank",
    top_k: int = 10,
    include_communities: bool = True,
    path_source_id: str | None = None,
    path_target_id: str | None = None,
    max_hops: int = 6,
) -> dict[str, Any]:
    """Compute node centrality, Louvain communities, and optional shortest path."""
    norm_metric = metric.strip().lower()
    if norm_metric not in _VALID_METRICS:
        raise KnowledgeReduceError(
            f"Unsupported centrality metric {metric!r}. Choose pagerank, degree, or betweenness."
        )
    if top_k < 1:
        raise KnowledgeReduceError(f"top_k must be >= 1 (got {top_k}).")
    if max_hops < 0:
        raise KnowledgeReduceError(f"max_hops must be >= 0 (got {max_hops}).")
    if (path_source_id is None) != (path_target_id is None):
        raise KnowledgeReduceError(
            "Provide both path_source_id and path_target_id when computing a shortest path."
        )

    layer_data = store.load_layer(layer_id)
    graph = layer_data_to_networkx(layer_data)
    entity_map = {e.entity_id: e for e in layer_data.entities}
    claim_map = {c.claim_id: c for c in layer_data.claims}

    def _describe_node(node_id: str) -> dict[str, str]:
        if node_id in entity_map:
            ent = entity_map[node_id]
            return {
                "node_id": node_id,
                "node_kind": "entity",
                "label": ent.canonical_name,
                "entity_type": ent.entity_type,
            }
        if node_id in claim_map:
            clm = claim_map[node_id]
            return {
                "node_id": node_id,
                "node_kind": "claim",
                "label": clm.statement,
            }
        return {"node_id": node_id, "node_kind": "unknown", "label": node_id}

    metric_lit = cast(Literal["pagerank", "degree", "betweenness"], norm_metric)
    ranked = central_nodes(graph, metric=metric_lit, top_k=top_k)
    central_entries = [{**_describe_node(nid), "score": round(score, 6)} for nid, score in ranked]

    if include_communities:
        raw_comms = detect_communities(graph)
        communities = [
            {
                "size": len(comm),
                "member_ids": comm,
                "sample_labels": [_describe_node(nid)["label"] for nid in comm[:5]],
            }
            for comm in raw_comms
        ]
    else:
        communities = []

    shortest_path_payload: dict[str, Any] | None = None
    if path_source_id is not None and path_target_id is not None:
        path = bounded_shortest_path(
            graph,
            path_source_id,
            path_target_id,
            max_hops=max_hops,
        )
        shortest_path_payload = {
            "source_id": path_source_id,
            "target_id": path_target_id,
            "found": path is not None,
            "hops": (len(path) - 1) if path is not None else None,
            "nodes": [_describe_node(nid) for nid in path] if path is not None else [],
        }

    return {
        "layer_id": layer_id,
        "metric": norm_metric,
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "central_nodes": central_entries,
        "community_count": len(communities),
        "communities": communities,
        "shortest_path": shortest_path_payload,
    }


def build_entity_inspection_payload(
    store: GraphStore,
    layer_id: str,
    entity_id_or_name: str,
    *,
    max_claims: int = 25,
    max_neighbors: int = 25,
) -> dict[str, Any]:
    """Return full entity details, linked claims, graph neighbors, conflicts, and sources."""
    if max_claims < 1:
        raise KnowledgeReduceError(f"max_claims must be >= 1 (got {max_claims}).")
    if max_neighbors < 0:
        raise KnowledgeReduceError(f"max_neighbors must be >= 0 (got {max_neighbors}).")

    layer_data = store.load_layer(layer_id)
    target = next((e for e in layer_data.entities if e.entity_id == entity_id_or_name), None)
    if target is None:
        norm_query = entity_id_or_name.strip().casefold()
        target = next(
            (
                e
                for e in layer_data.entities
                if e.canonical_name.strip().casefold() == norm_query
                or any(alias.strip().casefold() == norm_query for alias in e.aliases)
            ),
            None,
        )
    if target is None:
        raise KnowledgeReduceError(f"Entity {entity_id_or_name!r} not found in layer {layer_id!r}.")

    mentioned_claim_ids = {
        rel.source_id
        for rel in layer_data.relations
        if rel.relation_type == "MENTIONS" and rel.target_id == target.entity_id
    }
    linked_claims = sorted(
        (
            clm
            for clm in layer_data.claims
            if clm.subject_id == target.entity_id
            or clm.object_id == target.entity_id
            or clm.claim_id in mentioned_claim_ids
        ),
        key=lambda clm: (-int(clm.reliability), -clm.confidence, clm.claim_id),
    )
    top_claims = linked_claims[:max_claims]

    entity_by_id = {e.entity_id: e for e in layer_data.entities}
    neighbors: list[dict[str, Any]] = []
    for rel in layer_data.relations:
        if rel.relation_type in {"MENTIONS", "CONTRADICTS"}:
            continue
        if rel.source_id == target.entity_id and rel.target_id in entity_by_id:
            other = entity_by_id[rel.target_id]
            direction = "outbound"
        elif rel.target_id == target.entity_id and rel.source_id in entity_by_id:
            other = entity_by_id[rel.source_id]
            direction = "inbound"
        else:
            continue
        neighbors.append(
            {
                "direction": direction,
                "relation_type": rel.relation_type,
                "confidence": rel.confidence,
                "entity_id": other.entity_id,
                "canonical_name": other.canonical_name,
                "entity_type": other.entity_type,
            }
        )
    neighbors.sort(
        key=lambda item: (-float(item["confidence"]), item["relation_type"], item["entity_id"])
    )
    top_neighbors = neighbors[:max_neighbors]

    all_linked_claim_ids = {clm.claim_id for clm in linked_claims}
    related_conflicts = [
        cf
        for cf in layer_data.conflicts
        if cf.target_key.startswith(f"{target.entity_id}::")
        or cf.target_key == target.entity_id
        or any(
            str(cid) in all_linked_claim_ids
            for cand in cf.candidates
            for cid in (cand.get("claim_ids") or [])
        )
    ]

    cited_source_ids = (
        {ev.source_id for ev in target.evidence if ev.source_id}
        | {clm.source_id for clm in linked_claims if clm.source_id}
        | {ev.source_id for clm in linked_claims for ev in clm.evidence if ev.source_id}
    )
    sources_by_id = {src.source_id: src for src in layer_data.sources}
    cited_sources = [
        sources_by_id[sid].model_dump(mode="json")
        for sid in sorted(cited_source_ids)
        if sid in sources_by_id
    ]

    return {
        "layer_id": layer_id,
        "entity": target.model_dump(mode="json"),
        "total_linked_claims": len(linked_claims),
        "claims": [clm.model_dump(mode="json") for clm in top_claims],
        "total_neighbors": len(neighbors),
        "neighbors": top_neighbors,
        "conflict_count": len(related_conflicts),
        "conflicts": [cf.model_dump(mode="json") for cf in related_conflicts],
        "sources": cited_sources,
    }


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
        local_directories: list[dict[str, Any]] | None = None,
        crawl_config: dict[str, Any] | None = None,
        checkpoint_name: str = "01_ingested.jsonl",
        incremental_from_layer: str | None = None,
    ) -> dict[str, Any]:
        """Ingest local files, local directories, and/or web URLs into a workspace JSONL checkpoint."""
        known_by_uri: dict[str, str] = {}
        known_by_source_id: dict[str, str] = {}
        if incremental_from_layer is not None:
            known_by_uri, known_by_source_id = load_layer_source_hashes(
                store, incremental_from_layer
            )

        skipped_unchanged = 0
        docs: list[SourceDocument] = []
        if crawl_config is not None:
            cfg = CrawlConfig.model_validate(crawl_config)
            if known_by_uri:
                merged_hashes = {**known_by_uri, **cfg.known_hashes}
                cfg = cfg.model_copy(update={"known_hashes": merged_hashes})
            crawler = AsyncWebCrawler(cfg, transport=web_transport, resolver=dns_resolver)
            docs.extend(await crawler.crawl())
            skipped_unchanged += crawler.skipped_unchanged

        local_docs: list[SourceDocument] = []
        for item in local_files or []:
            raw_path = str(item.get("path", ""))
            safe_file = ensure_within_base(raw_path, base)
            source_id = str(item["source_id"]) if item.get("source_id") else None
            trust_weight = float(item.get("trust_weight", 0.75))
            local_docs.extend(
                ingest_local_file(
                    safe_file,
                    source_id=source_id,
                    trust_weight=trust_weight,
                    base_dir=base,
                )
            )
        for item in local_directories or []:
            raw_path = str(item.get("path", ""))
            safe_dir = ensure_within_base(raw_path, base)
            raw_patterns = item.get("patterns")
            patterns = tuple(str(p) for p in raw_patterns) if raw_patterns else ("**/*",)
            recursive = bool(item.get("recursive", True))
            trust_weight = float(item.get("trust_weight", 0.75))
            local_docs.extend(
                ingest_local_directory(
                    safe_dir,
                    patterns=patterns,
                    recursive=recursive,
                    trust_weight=trust_weight,
                    base_dir=base,
                )
            )
        if known_by_uri or known_by_source_id:
            kept_local, local_skipped = filter_unchanged_documents(
                local_docs, known_by_uri, known_by_source_id
            )
            docs.extend(kept_local)
            skipped_unchanged += local_skipped
        else:
            docs.extend(local_docs)

        ckpt_path = ensure_within_base(checkpoint_name, resolved_ckpt_dir)
        write_jsonl_checkpoint(docs, ckpt_path)
        return {
            "document_count": len(docs),
            "skipped_unchanged": skipped_unchanged,
            "source_ids": [d.source_id for d in docs],
            "checkpoint_path": str(ckpt_path.relative_to(base)),
        }

    @server.tool()
    @_mcp_error_boundary
    def read_ingested_checkpoint(
        checkpoint_name: str = "01_ingested.jsonl",
        offset: int = 0,
        limit: int = 20,
        max_chars_per_doc: int = 4000,
        source_id: str | None = None,
    ) -> dict[str, Any]:
        """Read paginated ingested ``SourceDocument`` records from a workspace checkpoint."""
        if offset < 0:
            raise KnowledgeReduceError(f"offset must be >= 0 (got {offset}).")
        if limit < 1 or limit > 200:
            raise KnowledgeReduceError(f"limit must be between 1 and 200 (got {limit}).")
        if max_chars_per_doc < 100:
            raise KnowledgeReduceError(
                f"max_chars_per_doc must be >= 100 (got {max_chars_per_doc})."
            )

        in_path = ensure_within_base(checkpoint_name, resolved_ckpt_dir)
        docs = read_jsonl_checkpoint(in_path, SourceDocument)
        filtered = [d for d in docs if source_id is None or d.source_id == source_id]
        window = filtered[offset : offset + limit]
        documents = [
            {
                "source_id": d.source_id,
                "uri": d.uri,
                "source_type": str(d.source_type),
                "title": d.title,
                "author": d.author,
                "published_at": d.published_at.isoformat() if d.published_at else None,
                "trust_weight": d.trust_weight,
                "metadata": d.metadata,
                "content_chars": len(d.content),
                "truncated": len(d.content) > max_chars_per_doc,
                "content": d.content[:max_chars_per_doc],
            }
            for d in window
        ]
        return {
            "checkpoint_path": str(in_path.relative_to(base)),
            "total_documents": len(filtered),
            "returned_count": len(documents),
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(window) < len(filtered),
            "documents": documents,
        }

    @server.tool()
    @_mcp_error_boundary
    def run_local_map(
        ingested_checkpoint: str = "01_ingested.jsonl",
        mapped_checkpoint: str = "02_mapped.jsonl",
        mapper: str = "deterministic",
        min_sentence_length: int = 25,
        skip_headings: bool = True,
        skip_questions: bool = True,
        spacy_model: str = "en_core_web_sm",
    ) -> dict[str, Any]:
        """Map an ingested checkpoint locally into entities, claims, and relations."""
        in_path = ensure_within_base(ingested_checkpoint, resolved_ckpt_dir)
        out_path = ensure_within_base(mapped_checkpoint, resolved_ckpt_dir)

        docs = read_jsonl_checkpoint(in_path, SourceDocument)
        cfg = PipelineConfig(
            layer_id="mcp-map-tmp",
            layer_name="MCP Map",
            store_dir=str(resolved_store_dir),
            mapper=mapper,
            min_sentence_length=min_sentence_length,
            skip_headings=skip_headings,
            skip_questions=skip_questions,
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
        parent_layer_ids: list[str] | None = None,
        build_embeddings_index: bool = True,
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
            parent_layer_ids=parent_layer_ids,
            strict_validation=True,
        )
        store.save_layer(layer_data, overwrite=overwrite)
        if build_embeddings_index and layer_data.claims:
            retriever.build_index(layer_id)
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
        reconcile: bool = False,
        deduplicate_claims: bool = True,
        build_embeddings_index: bool = True,
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
            reconcile=reconcile,
            deduplicate_claims=deduplicate_claims,
            overwrite=overwrite,
        )
        if build_embeddings_index and stacked.claims:
            retriever.build_index(target_layer_id)
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
        curated, updated_conflict = adjudicate_conflict(
            base_data,
            conflict_id=conflict_id,
            target_layer_id=target_layer_id,
            winning_value=winning_value,
            winning_source_id=winning_source_id,
            resolution_notes=resolution_notes or "Adjudicated via MCP resolve_conflict.",
        )
        store.save_layer(curated, overwrite=overwrite)
        return {
            "layer": curated.layer.model_dump(mode="json"),
            "resolved_conflict": updated_conflict.model_dump(mode="json"),
        }

    @server.tool()
    @_mcp_error_boundary
    def resolve_conflicts(
        base_layer_id: str,
        target_layer_id: str,
        resolutions: list[dict[str, Any]],
        default_notes: str = "",
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Atomically adjudicate a batch of conflicts into a single CURATED child layer."""
        decisions = [ConflictResolutionDecision.model_validate(item) for item in resolutions]
        base_data = store.load_layer(base_layer_id)
        curated, resolved = adjudicate_conflicts(
            base_data,
            decisions=decisions,
            target_layer_id=target_layer_id,
            default_notes=default_notes or "Adjudicated via MCP resolve_conflicts.",
        )
        store.save_layer(curated, overwrite=overwrite)
        return {
            "layer": curated.layer.model_dump(mode="json"),
            "resolved_count": len(resolved),
            "resolved_conflicts": [cf.model_dump(mode="json") for cf in resolved],
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
        """Export *layer_id* to json, sharded_jsonl, graphml, gexf, markdown, or parquet inside workspace."""
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
        elif fmt == "markdown":
            out = export_layer_markdown(layer_data, output_path, base_dir=base)
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
                "Choose json, sharded_jsonl, graphml, gexf, markdown, or parquet."
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

    @server.tool()
    @_mcp_error_boundary
    def list_layers() -> dict[str, Any]:
        """List all persisted knowledge layers and metadata in the workspace store."""
        return build_layers_payload(store)

    @server.tool()
    @_mcp_error_boundary
    def get_layer_lineage(layer_id: str) -> dict[str, Any]:
        """Inspect parent, ancestor, and descendant layer lineage for *layer_id*."""
        return build_layer_lineage_payload(stack_mgr, layer_id)

    @server.tool()
    @_mcp_error_boundary
    def analyze_graph(
        layer_id: str,
        metric: str = "pagerank",
        top_k: int = 10,
        include_communities: bool = True,
        path_source_id: str | None = None,
        path_target_id: str | None = None,
        max_hops: int = 6,
    ) -> dict[str, Any]:
        """Run graph centrality, Louvain community detection, and optional shortest path."""
        return build_graph_analytics_payload(
            store,
            layer_id,
            metric=metric,
            top_k=top_k,
            include_communities=include_communities,
            path_source_id=path_source_id,
            path_target_id=path_target_id,
            max_hops=max_hops,
        )

    @server.tool()
    @_mcp_error_boundary
    def inspect_entity(
        layer_id: str,
        entity_id_or_name: str,
        max_claims: int = 25,
        max_neighbors: int = 25,
    ) -> dict[str, Any]:
        """Inspect an entity by ID, canonical name, or alias with claims, neighbors, conflicts, and sources."""
        return build_entity_inspection_payload(
            store,
            layer_id,
            entity_id_or_name,
            max_claims=max_claims,
            max_neighbors=max_neighbors,
        )

    @server.resource(
        "kr://layers",
        name="layers_catalog",
        description="Serialized summary of all persisted knowledge layers in the store.",
        mime_type="application/json",
    )
    def layers_catalog_resource() -> str:
        return json.dumps(build_layers_payload(store), indent=2)

    @server.resource(
        "kr://layers/{layer_id}/manifest",
        name="layer_manifest",
        description="Metadata manifest for a stored knowledge layer.",
        mime_type="application/json",
    )
    def layer_manifest_resource(layer_id: str) -> str:
        return json.dumps(store.get_layer_manifest(layer_id).model_dump(mode="json"), indent=2)

    @server.resource(
        "kr://layers/{layer_id}/conflicts",
        name="layer_open_conflicts",
        description="Open conflict records awaiting review in a stored knowledge layer.",
        mime_type="application/json",
    )
    def layer_conflicts_resource(layer_id: str) -> str:
        open_conflicts = store.list_conflicts(layer_id, needs_review=True, limit=200)
        return json.dumps(
            {
                "layer_id": layer_id,
                "count": len(open_conflicts),
                "conflicts": [cf.model_dump(mode="json") for cf in open_conflicts],
            },
            indent=2,
        )

    @server.prompt(
        name="extract_mapped_batch",
        description="Guide an agent to extract structured entities, claims, and relations from an ingested checkpoint.",
    )
    def extract_mapped_batch_prompt(
        checkpoint_path: str = "01_ingested.jsonl",
        source_id: str | None = None,
    ) -> str:
        target_clause = (
            f"Pass `source_id={source_id!r}` to focus on that source."
            if source_id
            else "Paginate with `offset` and `limit` until `has_more` is false."
        )
        return (
            f"1. Call `read_ingested_checkpoint` on `{checkpoint_path}` ({target_clause}).\n"
            "2. Extract normalized `entities` (with canonical_name, aliases, entity_type, evidence), "
            "`claims` (grounded statement, subject_id, predicate, object_id or object_literal, reliability 1..5, evidence), "
            "and `relations` referencing valid entity/claim IDs.\n"
            "3. Submit each extracted `MappedBatch` via `submit_mapped_batch` and persist with `resolve_and_reduce`."
        )

    @server.prompt(
        name="adjudicate_conflicts",
        description="Guide an agent through reviewing open conflicts and submitting atomic batch resolutions.",
    )
    def adjudicate_conflicts_prompt(layer_id: str) -> str:
        return (
            f"1. Inspect open disputes via `kr://layers/{layer_id}/conflicts` or `list_conflicts(layer_id={layer_id!r})`.\n"
            "2. For any disputed subject entity, call `inspect_entity` to examine corroborating claims, sources, and reliability.\n"
            f"3. Submit one atomic batch via `resolve_conflicts(base_layer_id={layer_id!r}, target_layer_id=..., resolutions=[...])` "
            "and verify zero remaining `open_conflicts` in the new CURATED layer."
        )

    return server
