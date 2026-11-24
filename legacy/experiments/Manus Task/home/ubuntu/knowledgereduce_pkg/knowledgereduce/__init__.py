"""
KnowledgeReduce: A Framework for Building Stackable Knowledge Graphs

This package provides a comprehensive framework for creating, managing, analyzing,
and visualizing knowledge graphs with support for stackable knowledge sets.

The framework is based on the KnowledgeReduce concept, which adapts the Map-Reduce
paradigm for knowledge graph construction and management.

Main Components:
- Core: Basic knowledge graph functionality
- Serialization: Import/export capabilities
- Visualization: Graph visualization and statistics
- Analysis: Fact analysis and relationship discovery
- Query: Flexible query interface
- Integration: High-level API that ties everything together

For more information, see the documentation and examples.
"""

# Import main components
from .core.core import KnowledgeGraph, StackableKnowledgeGraph, ReliabilityRating
from .serialization.serialization import KnowledgeGraphSerializer, StackableKnowledgeGraphSerializer
from .integration import KnowledgeReduceFramework

# Define version
__version__ = '1.0.0'
