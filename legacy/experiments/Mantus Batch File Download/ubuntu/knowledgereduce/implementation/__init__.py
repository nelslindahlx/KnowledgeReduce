"""
Main __init__.py file for the KnowledgeReduce package.
This file imports and exposes the main components of the framework.
"""

# Import main framework class
from .framework import KnowledgeReduceFramework

# Import core components
from .core import KnowledgeGraph, ReliabilityRating

# Import utility functions
from .utils import (
    scrape_webpage,
    extract_entities_from_text,
    create_knowledge_graph_from_text,
    create_knowledge_graph_from_url,
    merge_knowledge_graphs
)

# Import visualization functions
from .visualization import (
    visualize_graph,
    visualize_fact_neighborhood,
    create_graph_statistics
)

# Import analysis functions
from .analysis import (
    identify_central_facts,
    identify_fact_clusters,
    calculate_fact_similarity,
    find_similar_facts,
    analyze_fact_categories,
    find_path_between_facts
)

# Import query components
from .query import (
    KnowledgeQuery,
    find_facts_by_pattern,
    get_facts_with_relationship,
    get_related_facts
)

# Define version
__version__ = '0.1.0'

# Define all importable names
__all__ = [
    'KnowledgeReduceFramework',
    'KnowledgeGraph',
    'ReliabilityRating',
    'scrape_webpage',
    'extract_entities_from_text',
    'create_knowledge_graph_from_text',
    'create_knowledge_graph_from_url',
    'merge_knowledge_graphs',
    'visualize_graph',
    'visualize_fact_neighborhood',
    'create_graph_statistics',
    'identify_central_facts',
    'identify_fact_clusters',
    'calculate_fact_similarity',
    'find_similar_facts',
    'analyze_fact_categories',
    'find_path_between_facts',
    'KnowledgeQuery',
    'find_facts_by_pattern',
    'get_facts_with_relationship',
    'get_related_facts'
]
