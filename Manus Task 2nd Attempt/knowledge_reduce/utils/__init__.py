"""
Initialization file for the utils module.

This module provides utility functions for the KnowledgeReduce framework,
including serialization and other helper functions.
"""

from .serialization import (
    KnowledgeGraphPortable,
    serialize_knowledge_graph,
    deserialize_knowledge_graph
)

__all__ = [
    'KnowledgeGraphPortable',
    'serialize_knowledge_graph',
    'deserialize_knowledge_graph'
]
