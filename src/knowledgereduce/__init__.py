"""KnowledgeReduce: MapReduce-inspired stackable knowledge graph framework."""

from knowledgereduce.cli import app
from knowledgereduce.models import (
    Claim,
    ConflictRecord,
    ConflictStrategy,
    Entity,
    Evidence,
    KnowledgeLayer,
    LayerData,
    LayerDiff,
    LayerTier,
    MappedBatch,
    MergeMode,
    Relation,
    ReliabilityRating,
    SourceDocument,
    SourceType,
    ValidationReport,
)
from knowledgereduce.pipeline import LocalFileSourceConfig, PipelineConfig, PipelineRunner
from knowledgereduce.query import (
    HybridGraphRAGRetriever,
    QueryBuilder,
    bounded_shortest_path,
    central_nodes,
    detect_communities,
    k_hop_neighborhood,
)
from knowledgereduce.reduce import IntegrityValidator, KnowledgeReducer, adjudicate_conflict
from knowledgereduce.resolve import HashingEmbeddingProvider
from knowledgereduce.stack import StackManager
from knowledgereduce.storage import DuckDBParquetStore, GraphStore, MemoryGraphStore

__version__ = "1.5.0"

__all__ = [
    "Claim",
    "ConflictRecord",
    "ConflictStrategy",
    "DuckDBParquetStore",
    "Entity",
    "Evidence",
    "GraphStore",
    "HashingEmbeddingProvider",
    "HybridGraphRAGRetriever",
    "IntegrityValidator",
    "KnowledgeLayer",
    "KnowledgeReducer",
    "LayerData",
    "LayerDiff",
    "LayerTier",
    "LocalFileSourceConfig",
    "MappedBatch",
    "MemoryGraphStore",
    "MergeMode",
    "PipelineConfig",
    "PipelineRunner",
    "QueryBuilder",
    "Relation",
    "ReliabilityRating",
    "SourceDocument",
    "SourceType",
    "StackManager",
    "ValidationReport",
    "__version__",
    "adjudicate_conflict",
    "app",
    "bounded_shortest_path",
    "central_nodes",
    "detect_communities",
    "k_hop_neighborhood",
]
