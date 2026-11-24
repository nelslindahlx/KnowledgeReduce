"""
KnowledgeReduce: A Python package for creating and managing portable knowledge graphs.

This package provides tools for creating, managing, and analyzing knowledge graphs
with reliability ratings, semantic capabilities, and performance optimizations.
"""

from .core import KnowledgeGraph, ReliabilityRating
from .enhanced import EnhancedKnowledgeGraph
from .semantic import SemanticKnowledgeGraph
from .sharding import ShardedKnowledgeGraph

__version__ = "1.0.0"
__all__ = [
    'KnowledgeGraph',
    'ReliabilityRating',
    'EnhancedKnowledgeGraph',
    'SemanticKnowledgeGraph',
    'ShardedKnowledgeGraph'
]
