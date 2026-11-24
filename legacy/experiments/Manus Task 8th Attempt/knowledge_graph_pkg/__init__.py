"""
Knowledge Graph Package initialization.

This module initializes the knowledge_graph_pkg package and provides
convenient imports for the main classes and functions.
"""

__version__ = "0.2.0"

from knowledge_graph_pkg.core.knowledge_graph import KnowledgeGraph, ReliabilityRating

__all__ = ["KnowledgeGraph", "ReliabilityRating"]
