"""End-to-end KnowledgeReduce pipeline orchestrator with resumable checkpoints."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import httpx
import structlog

from knowledgereduce.ingest import (
    WebConnector,
    ingest_local_file,
    read_jsonl_checkpoint,
    write_jsonl_checkpoint,
)
from knowledgereduce.map import (
    DeterministicNLPMapper,
    Mapper,
    SpacyNLPMapper,
    StructuredMapper,
    load_mapped_batches,
    save_mapped_batches,
)
from knowledgereduce.map.structured import StructuredMappingConfig
from knowledgereduce.models import (
    LayerData,
    LayerTier,
    MappedBatch,
    SourceDocument,
    SourceType,
    StorageError,
)
from knowledgereduce.pipeline.config import PipelineConfig
from knowledgereduce.query import HybridGraphRAGRetriever
from knowledgereduce.reduce import KnowledgeReducer
from knowledgereduce.resolve import (
    EmbeddingProvider,
    HashingEmbeddingProvider,
    SentenceTransformerProvider,
    TfidfSVDProvider,
)
from knowledgereduce.security import ResolverFn
from knowledgereduce.storage import DuckDBParquetStore, GraphStore

logger = structlog.get_logger(__name__)


def _map_single_doc_worker(
    args: tuple[SourceDocument, str, int, StructuredMappingConfig | None, bool, bool],
) -> MappedBatch:
    """Top-level picklable worker for parallel Map execution."""
    doc, mapper_kind, min_len, structured_cfg, skip_headings, skip_questions = args
    if mapper_kind == "structured" or doc.source_type in {
        SourceType.CSV,
        SourceType.JSON,
        SourceType.JSONL,
    }:
        return StructuredMapper(structured_cfg).map_document(doc)
    return DeterministicNLPMapper(
        min_sentence_length=min_len,
        skip_headings=skip_headings,
        skip_questions=skip_questions,
    ).map_document(doc)


def build_mapper(config: PipelineConfig) -> Mapper:
    """Instantiate the configured Mapper implementation."""
    if config.mapper == "structured":
        return StructuredMapper(config.structured_config)
    if config.mapper == "spacy":
        return SpacyNLPMapper(
            model_name=config.spacy_model,
            min_sentence_length=config.min_sentence_length,
        )
    return DeterministicNLPMapper(
        min_sentence_length=config.min_sentence_length,
        skip_headings=config.skip_headings,
        skip_questions=config.skip_questions,
    )


def build_embedding_provider(config: PipelineConfig) -> EmbeddingProvider:
    """Instantiate the configured clustering EmbeddingProvider."""
    if config.use_sentence_transformers:
        return SentenceTransformerProvider(model_name=config.embedding_model)
    return TfidfSVDProvider()


def build_retrieval_embedding_provider(config: PipelineConfig) -> EmbeddingProvider:
    """Instantiate the stateless EmbeddingProvider used for persisted GraphRAG indexing."""
    if config.use_sentence_transformers:
        return SentenceTransformerProvider(model_name=config.embedding_model)
    return HashingEmbeddingProvider()


def load_layer_source_hashes(
    store: GraphStore,
    layer_id: str,
) -> tuple[dict[str, str], dict[str, str]]:
    """Load prior source ``(uri -> sha256, source_id -> sha256)`` digests for *layer_id*."""
    if not store.layer_exists(layer_id):
        raise StorageError(f"Incremental base layer {layer_id!r} does not exist.")
    return store.list_source_hashes(layer_id)


def filter_unchanged_documents(
    docs: Sequence[SourceDocument],
    known_by_uri: dict[str, str],
    known_by_source_id: dict[str, str],
) -> tuple[list[SourceDocument], int]:
    """Return ``(changed_docs, skipped_count)`` using prior source SHA-256 digests."""
    kept: list[SourceDocument] = []
    skipped = 0
    for doc in docs:
        expected_sha = known_by_uri.get(doc.uri) or known_by_source_id.get(doc.source_id)
        if expected_sha and expected_sha == doc.content_sha256:
            skipped += 1
            continue
        kept.append(doc)
    return kept, skipped


class PipelineRunner:
    """Orchestrates Ingest -> Map -> Resolve -> Reduce -> Store with stage checkpoints."""

    def __init__(
        self,
        *,
        store: GraphStore | None = None,
        web_transport: httpx.AsyncBaseTransport | None = None,
        dns_resolver: ResolverFn | None = None,
    ) -> None:
        self._explicit_store = store
        self._web_transport = web_transport
        self._dns_resolver = dns_resolver

    def _get_store(self, config: PipelineConfig) -> GraphStore:
        if self._explicit_store is not None:
            return self._explicit_store
        return DuckDBParquetStore(config.store_dir)

    @contextlib.contextmanager
    def _open_store(self, config: PipelineConfig) -> Iterator[GraphStore]:
        if self._explicit_store is not None:
            yield self._explicit_store
            return
        with DuckDBParquetStore(config.store_dir) as store:
            yield store

    def _load_known_source_hashes(
        self,
        config: PipelineConfig,
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Load prior source SHA-256 digests from ``incremental_from_layer``."""
        if config.incremental_from_layer is None:
            return {}, {}
        with self._open_store(config) as store:
            return load_layer_source_hashes(store, config.incremental_from_layer)

    def ingest(self, config: PipelineConfig) -> list[SourceDocument]:
        """Run stage 1 (Ingestion) and write ``01_ingested.jsonl`` if checkpoints enabled."""
        known_by_uri, known_by_source_id = self._load_known_source_hashes(config)
        skipped_unchanged = 0
        docs: list[SourceDocument] = []
        if config.web_crawl is not None:
            crawl_cfg = config.web_crawl
            if known_by_uri:
                merged_hashes = {**known_by_uri, **config.web_crawl.known_hashes}
                crawl_cfg = config.web_crawl.model_copy(update={"known_hashes": merged_hashes})
            crawler = WebConnector(
                crawl_cfg,
                transport=self._web_transport,
                resolver=self._dns_resolver,
            )
            docs.extend(crawler.ingest())
            skipped_unchanged += crawler.skipped_unchanged

        local_docs: list[SourceDocument] = []
        for file_cfg in config.local_files:
            local_docs.extend(
                ingest_local_file(
                    file_cfg.path,
                    source_id=file_cfg.source_id,
                    trust_weight=file_cfg.trust_weight,
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

        if config.checkpoint_dir:
            ckpt = Path(config.checkpoint_dir) / "01_ingested.jsonl"
            write_jsonl_checkpoint(docs, ckpt)

        logger.info(
            "pipeline_ingested",
            layer_id=config.layer_id,
            document_count=len(docs),
            skipped_unchanged=skipped_unchanged,
            incremental_from_layer=config.incremental_from_layer,
        )
        return docs

    def map_documents(
        self,
        docs: Sequence[SourceDocument],
        config: PipelineConfig,
    ) -> list[MappedBatch]:
        """Run stage 2 (Map) over *docs* and write ``02_mapped.jsonl`` if checkpoints enabled."""
        if not docs:
            batches: list[MappedBatch] = []
        elif config.max_workers > 1 and len(docs) > 1 and config.mapper == "deterministic":
            payload = [
                (
                    doc,
                    config.mapper,
                    config.min_sentence_length,
                    config.structured_config,
                    config.skip_headings,
                    config.skip_questions,
                )
                for doc in docs
            ]
            with ProcessPoolExecutor(max_workers=config.max_workers) as pool:
                batches = list(pool.map(_map_single_doc_worker, payload))
        else:
            structured_mapper = StructuredMapper(config.structured_config)
            primary_mapper = build_mapper(config)
            batches = []
            # Route structured docs to StructuredMapper automatically when using mixed corpora.
            for doc in docs:
                if doc.source_type in {SourceType.CSV, SourceType.JSON, SourceType.JSONL} and (
                    config.mapper != "structured"
                ):
                    batches.append(structured_mapper.map_document(doc))
                else:
                    batches.append(primary_mapper.map_document(doc))

        if config.checkpoint_dir:
            ckpt = Path(config.checkpoint_dir) / "02_mapped.jsonl"
            save_mapped_batches(batches, ckpt)

        logger.info(
            "pipeline_mapped",
            layer_id=config.layer_id,
            batch_count=len(batches),
            entities=sum(len(b.entities) for b in batches),
            claims=sum(len(b.claims) for b in batches),
        )
        return batches

    def reduce_and_store(
        self,
        batches: Sequence[MappedBatch],
        config: PipelineConfig,
        *,
        parent_layer_ids: list[str] | None = None,
    ) -> LayerData:
        """Run stages 3-5 (Resolve, Reduce, Integrity Gate, Store) from mapped batches."""
        resolved_parents = (
            list(parent_layer_ids)
            if parent_layer_ids is not None
            else ([config.incremental_from_layer] if config.incremental_from_layer else None)
        )
        cluster_provider = build_embedding_provider(config)
        reducer = KnowledgeReducer(
            lexical_threshold=config.lexical_threshold,
            semantic_threshold=config.semantic_threshold,
            min_claim_length=config.min_claim_length,
            conflict_strategy=config.conflict_strategy,
            embedding_provider=cluster_provider,
        )
        layer_data = reducer.reduce_batches(
            batches,
            layer_id=config.layer_id,
            layer_name=config.layer_name,
            tier=LayerTier(config.tier),
            parent_layer_ids=resolved_parents,
            pipeline_config_hash=config.config_sha256(),
            strict_validation=True,
        )

        if config.checkpoint_dir:
            ckpt = Path(config.checkpoint_dir) / "03_resolved.jsonl"
            write_jsonl_checkpoint([layer_data], ckpt)

        with self._open_store(config) as store:
            store.save_layer(layer_data, overwrite=config.overwrite)

            embeddings_indexed = 0
            if config.build_embeddings_index and layer_data.claims:
                retrieval_provider = (
                    cluster_provider
                    if config.use_sentence_transformers
                    else build_retrieval_embedding_provider(config)
                )
                retriever = HybridGraphRAGRetriever(store, embedding_provider=retrieval_provider)
                embeddings_indexed = retriever.build_index(config.layer_id)

        logger.info(
            "pipeline_reduced",
            layer_id=config.layer_id,
            stats=layer_data.layer.stats,
            embeddings_indexed=embeddings_indexed,
        )
        return layer_data

    def run(self, config: PipelineConfig) -> LayerData:
        """Execute the full Ingest -> Map -> Resolve -> Reduce -> Store pipeline."""
        docs = self.ingest(config)
        batches = self.map_documents(docs, config)
        return self.reduce_and_store(batches, config)

    def run_from_ingested_checkpoint(
        self,
        checkpoint_path: Path | str,
        config: PipelineConfig,
    ) -> LayerData:
        """Resume pipeline execution from an existing ``01_ingested.jsonl`` checkpoint."""
        docs = read_jsonl_checkpoint(checkpoint_path, SourceDocument)
        batches = self.map_documents(docs, config)
        return self.reduce_and_store(batches, config)

    def run_from_mapped_checkpoint(
        self,
        checkpoint_path: Path | str,
        config: PipelineConfig,
    ) -> LayerData:
        """Resume pipeline execution from an existing ``02_mapped.jsonl`` checkpoint."""
        batches = load_mapped_batches(checkpoint_path)
        return self.reduce_and_store(batches, config)
