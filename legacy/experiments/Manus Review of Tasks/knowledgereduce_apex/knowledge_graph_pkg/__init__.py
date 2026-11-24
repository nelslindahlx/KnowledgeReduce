"""
KnowledgeReduce Apex: A comprehensive knowledge graph framework with advanced capabilities.

This package provides advanced tools for creating, managing, and analyzing knowledge graphs
with reliability ratings, semantic capabilities, performance optimizations, real-time
streaming, vector embeddings, blockchain verification, AI integration, multi-modal data,
and federated collaboration.
"""

from .core import KnowledgeGraph, ReliabilityRating
from .enhanced import EnhancedKnowledgeGraph
from .semantic import SemanticKnowledgeGraph
from .sharding import ShardedKnowledgeGraph
from .vector import VectorKnowledgeGraph
from .streaming import StreamingKnowledgeGraph
from .blockchain import BlockchainKnowledgeGraph
from .ai import AIKnowledgeGraph
from .multimodal import MultiModalKnowledgeGraph
from .federated import FederatedKnowledgeGraph

__version__ = "3.0.0"
__all__ = [
    'KnowledgeGraph',
    'ReliabilityRating',
    'EnhancedKnowledgeGraph',
    'SemanticKnowledgeGraph',
    'ShardedKnowledgeGraph',
    'VectorKnowledgeGraph',
    'StreamingKnowledgeGraph',
    'BlockchainKnowledgeGraph',
    'AIKnowledgeGraph',
    'MultiModalKnowledgeGraph',
    'FederatedKnowledgeGraph'
]
