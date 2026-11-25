"""End-to-end declarative pipeline configuration and runner."""

from knowledgereduce.pipeline.config import (
    LocalDirectorySourceConfig,
    LocalFileSourceConfig,
    PipelineConfig,
)
from knowledgereduce.pipeline.runner import (
    PipelineRunner,
    build_embedding_provider,
    build_mapper,
    filter_unchanged_documents,
    load_layer_source_hashes,
)

__all__ = [
    "LocalDirectorySourceConfig",
    "LocalFileSourceConfig",
    "PipelineConfig",
    "PipelineRunner",
    "build_embedding_provider",
    "build_mapper",
    "filter_unchanged_documents",
    "load_layer_source_hashes",
]
