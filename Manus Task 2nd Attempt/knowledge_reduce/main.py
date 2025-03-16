"""
Main module for the KnowledgeReduce framework.

This module provides high-level functions for using the KnowledgeReduce framework
to build and manage knowledge graphs.
"""

from .graph import ReliabilityRating, KnowledgeGraph
from .extraction import (
    extract_facts_from_url,
    extract_facts_from_multiple_urls,
    populate_knowledge_graph_from_urls
)
from .processing import (
    remove_duplicate_facts,
    advanced_cleaning,
    semantic_cleaning,
    clean_knowledge_graph
)
from .utils import (
    serialize_knowledge_graph,
    deserialize_knowledge_graph
)


def create_knowledge_graph():
    """
    Create a new knowledge graph.
    
    Returns:
        KnowledgeGraph: A new empty knowledge graph
    """
    return KnowledgeGraph()


def build_knowledge_graph_from_urls(urls, category="General", tags=None, 
                                   reliability_rating=None, clean=True):
    """
    Build a knowledge graph from a set of URLs.
    
    This is a high-level function that combines extraction, population, and cleaning.
    
    Args:
        urls: Dictionary mapping source_ids to URLs or list of URLs
        category: Category for the facts
        tags: Additional tags for the facts
        reliability_rating: ReliabilityRating for the facts
        clean: Whether to clean the knowledge graph after population
        
    Returns:
        tuple: (KnowledgeGraph, stats) where stats contains information about the process
    """
    # Create a new knowledge graph
    kg = create_knowledge_graph()
    
    # Set default values
    if tags is None:
        tags = ["WebScraped"]
    if reliability_rating is None:
        reliability_rating = ReliabilityRating.UNVERIFIED
    
    # Populate the knowledge graph
    fact_count = populate_knowledge_graph_from_urls(
        kg, urls, category, tags, reliability_rating
    )
    
    stats = {
        'extracted_facts': fact_count
    }
    
    # Clean the knowledge graph if requested
    if clean and fact_count > 0:
        cleaning_stats = clean_knowledge_graph(kg)
        stats.update(cleaning_stats)
    
    return kg, stats


def save_knowledge_graph(kg, filename, sharded=False, shard_size=100):
    """
    Save a knowledge graph to disk.
    
    Args:
        kg: KnowledgeGraph instance
        filename: Path to save the file
        sharded: Whether to use sharded serialization
        shard_size: Size of each shard if using sharded serialization
        
    Returns:
        bool: True if successful, False otherwise
    """
    if sharded:
        from .utils.serialization import KnowledgeGraphPortable
        from os.path import dirname, basename, splitext, join
        
        # Get directory and filename without extension
        directory = dirname(filename) or '.'
        base_name = splitext(basename(filename))[0]
        
        # Create portable representation
        portable = KnowledgeGraphPortable(kg)
        
        # Serialize sharded
        shard_files = portable.serialize_sharded(
            directory, 
            shard_size=shard_size, 
            prefix=f"{base_name}_shard_"
        )
        
        return len(shard_files) > 0
    else:
        return serialize_knowledge_graph(kg, filename)


def load_knowledge_graph(filename, sharded=False):
    """
    Load a knowledge graph from disk.
    
    Args:
        filename: Path to the file
        sharded: Whether the file is a sharded serialization metadata file
        
    Returns:
        KnowledgeGraph: The loaded knowledge graph or None if failed
    """
    if sharded:
        from .utils.serialization import KnowledgeGraphPortable
        
        # Create portable representation
        portable = KnowledgeGraphPortable(nx.DiGraph())
        
        # Deserialize sharded
        graph = portable.deserialize_sharded(filename)
        
        if graph is None:
            return None
            
        # Create knowledge graph from graph
        kg = KnowledgeGraph()
        kg.graph = graph
        kg.data = [dict(graph.nodes[node]) for node in graph.nodes]
        
        return kg
    else:
        return deserialize_knowledge_graph(filename, KnowledgeGraph)
