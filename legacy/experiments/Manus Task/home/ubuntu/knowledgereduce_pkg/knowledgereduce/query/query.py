"""
Query module for knowledge graphs.
This module provides classes and functions for querying knowledge graphs.
"""

import re
from collections import defaultdict

class KnowledgeQuery:
    """
    Class for building and executing queries on knowledge graphs.
    
    This class provides a fluent interface for constructing queries
    to filter and retrieve facts from a knowledge graph.
    """
    
    def __init__(self, knowledge_graph):
        """
        Initialize a new query for the given knowledge graph.
        
        Args:
            knowledge_graph: The knowledge graph to query
        """
        self.knowledge_graph = knowledge_graph
        self.filters = []
        self.sort_key = None
        self.sort_reverse = False
        self.limit_value = None
    
    def filter_by_category(self, category):
        """
        Filter facts by category.
        
        Args:
            category (str): Category to filter by
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        self.filters.append(('category', lambda x: x == category))
        return self
    
    def filter_by_categories(self, categories):
        """
        Filter facts by multiple categories.
        
        Args:
            categories (list): List of categories to filter by
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        self.filters.append(('category', lambda x: x in categories))
        return self
    
    def filter_by_tag(self, tag):
        """
        Filter facts by tag.
        
        Args:
            tag (str): Tag to filter by
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        self.filters.append(('tags', lambda x: tag in x.split(', ') if isinstance(x, str) else tag in x))
        return self
    
    def filter_by_tags(self, tags, match_all=False):
        """
        Filter facts by multiple tags.
        
        Args:
            tags (list): List of tags to filter by
            match_all (bool, optional): Whether all tags must match. Defaults to False.
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        if match_all:
            self.filters.append(('tags', lambda x: all(tag in x.split(', ') if isinstance(x, str) else tag in x for tag in tags)))
        else:
            self.filters.append(('tags', lambda x: any(tag in x.split(', ') if isinstance(x, str) else tag in x for tag in tags)))
        return self
    
    def filter_by_reliability(self, min_reliability):
        """
        Filter facts by minimum reliability rating.
        
        Args:
            min_reliability (int or ReliabilityRating): Minimum reliability rating
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        # Handle both enum and integer values
        if hasattr(min_reliability, 'value'):
            min_value = min_reliability.value
        else:
            min_value = min_reliability
            
        self.filters.append(('reliability_rating', lambda x: x.value >= min_value if hasattr(x, 'value') else x >= min_value))
        return self
    
    def filter_by_quality_score(self, min_score):
        """
        Filter facts by minimum quality score.
        
        Args:
            min_score (int): Minimum quality score
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        self.filters.append(('quality_score', lambda x: x >= min_score))
        return self
    
    def filter_by_usage_count(self, min_count):
        """
        Filter facts by minimum usage count.
        
        Args:
            min_count (int): Minimum usage count
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        self.filters.append(('usage_count', lambda x: x >= min_count))
        return self
    
    def filter_by_source(self, source_id):
        """
        Filter facts by source ID.
        
        Args:
            source_id (str): Source ID to filter by
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        self.filters.append(('source_id', lambda x: x == source_id))
        return self
    
    def filter_by_author(self, author):
        """
        Filter facts by author/creator.
        
        Args:
            author (str): Author/creator to filter by
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        self.filters.append(('author_creator', lambda x: x == author))
        return self
    
    def filter_by_access_level(self, access_level):
        """
        Filter facts by access level.
        
        Args:
            access_level (str): Access level to filter by
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        self.filters.append(('access_level', lambda x: x == access_level))
        return self
    
    def filter_by_text(self, text, field='fact_statement'):
        """
        Filter facts by text content.
        
        Args:
            text (str): Text to search for
            field (str, optional): Field to search in. Defaults to 'fact_statement'.
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        self.filters.append((field, lambda x: text.lower() in x.lower() if isinstance(x, str) else False))
        return self
    
    def filter_by_regex(self, pattern, field='fact_statement'):
        """
        Filter facts by regular expression pattern.
        
        Args:
            pattern (str): Regular expression pattern
            field (str, optional): Field to search in. Defaults to 'fact_statement'.
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        regex = re.compile(pattern)
        self.filters.append((field, lambda x: bool(regex.search(x)) if isinstance(x, str) else False))
        return self
    
    def filter_by_related_fact(self, fact_id):
        """
        Filter facts that are related to a specific fact.
        
        Args:
            fact_id (str): ID of the related fact
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        # This is a special filter that needs to check graph structure
        self.filters.append(('_related_to', fact_id))
        return self
    
    def filter_custom(self, attribute, predicate):
        """
        Apply a custom filter.
        
        Args:
            attribute (str): Attribute to filter on
            predicate (callable): Function that takes the attribute value and returns a boolean
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        self.filters.append((attribute, predicate))
        return self
    
    def sort_by(self, attribute, reverse=False):
        """
        Sort results by a specific attribute.
        
        Args:
            attribute (str): Attribute to sort by
            reverse (bool, optional): Whether to sort in descending order. Defaults to False.
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        self.sort_key = attribute
        self.sort_reverse = reverse
        return self
    
    def limit(self, count):
        """
        Limit the number of results.
        
        Args:
            count (int): Maximum number of results to return
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        self.limit_value = count
        return self
    
    def execute(self):
        """
        Execute the query and return the results.
        
        Returns:
            list: List of tuples (fact_id, fact_data) that match the query
        """
        # Get the graph
        G = self.knowledge_graph.graph
        
        # Start with all nodes
        results = []
        
        # Apply filters
        for node_id, node_data in G.nodes(data=True):
            # Check if node passes all filters
            passes_filters = True
            
            for filter_attr, filter_func in self.filters:
                # Special case for related_to filter
                if filter_attr == '_related_to':
                    related_fact_id = filter_func  # In this case, filter_func is actually the fact_id
                    # Check if there's an edge between the nodes
                    if not (G.has_edge(node_id, related_fact_id) or G.has_edge(related_fact_id, node_id)):
                        passes_filters = False
                        break
                elif filter_attr in node_data:
                    if not filter_func(node_data[filter_attr]):
                        passes_filters = False
                        break
                else:
                    # If attribute doesn't exist, filter fails
                    passes_filters = False
                    break
            
            if passes_filters:
                results.append((node_id, node_data))
        
        # Sort results if sort key is specified
        if self.sort_key:
            try:
                results.sort(key=lambda x: x[1].get(self.sort_key, 0), reverse=self.sort_reverse)
            except:
                # If sorting fails, ignore it
                pass
        
        # Apply limit if specified
        if self.limit_value is not None:
            results = results[:self.limit_value]
        
        return results

def find_facts_by_pattern(knowledge_graph, pattern, field='fact_statement'):
    """
    Find facts matching a regular expression pattern.
    
    Args:
        knowledge_graph: The knowledge graph
        pattern (str): Regular expression pattern
        field (str, optional): Field to search in. Defaults to 'fact_statement'.
        
    Returns:
        list: List of fact IDs matching the pattern
    """
    # Get the graph
    G = knowledge_graph.graph
    
    # Compile regex
    regex = re.compile(pattern)
    
    # Find matching facts
    matching_facts = []
    
    for node_id, node_data in G.nodes(data=True):
        if field in node_data and isinstance(node_data[field], str):
            if regex.search(node_data[field]):
                matching_facts.append(node_id)
    
    return matching_facts

def get_facts_with_relationship(knowledge_graph, relationship_type, as_source=True, as_target=True):
    """
    Find facts with a specific relationship type.
    
    Args:
        knowledge_graph: The knowledge graph
        relationship_type (str): Type of relationship
        as_source (bool, optional): Include facts that are sources. Defaults to True.
        as_target (bool, optional): Include facts that are targets. Defaults to True.
        
    Returns:
        dict: Dictionary with 'sources' and 'targets' lists
    """
    # Get the graph
    G = knowledge_graph.graph
    
    sources = set()
    targets = set()
    
    # Check all edges
    for u, v, edge_data in G.edges(data=True):
        if 'relationship_type' in edge_data and edge_data['relationship_type'] == relationship_type:
            if as_source:
                sources.add(u)
            if as_target:
                targets.add(v)
    
    return {
        'sources': list(sources),
        'targets': list(targets)
    }

def get_related_facts(knowledge_graph, fact_id, relationship_types=None, max_depth=1):
    """
    Get facts related to a given fact.
    
    Args:
        knowledge_graph: The knowledge graph
        fact_id (str): ID of the fact
        relationship_types (list, optional): Types of relationships to follow. Defaults to None (all types).
        max_depth (int, optional): Maximum depth of relationships. Defaults to 1.
        
    Returns:
        list: List of related fact IDs
        
    Raises:
        ValueError: If fact_id is not found in the graph
    """
    # Get the graph
    G = knowledge_graph.graph
    
    # Check if fact exists
    if fact_id not in G:
        raise ValueError(f"Fact ID '{fact_id}' not found in the graph.")
    
    # BFS to find related facts
    visited = {fact_id}
    current_depth = 0
    frontier = {fact_id}
    related_facts = []
    
    while current_depth < max_depth and frontier:
        next_frontier = set()
        
        for node in frontier:
            # Check outgoing edges
            for successor in G.successors(node):
                if successor not in visited:
                    edge_data = G.get_edge_data(node, successor)
                    # Check relationship type if specified
                    if relationship_types is None or ('relationship_type' in edge_data and edge_data['relationship_type'] in relationship_types):
                        next_frontier.add(successor)
                        visited.add(successor)
                        related_facts.append(successor)
            
            # Check incoming edges
            for predecessor in G.predecessors(node):
                if predecessor not in visited:
                    edge_data = G.get_edge_data(predecessor, node)
                    # Check relationship type if specified
                    if relationship_types is None or ('relationship_type' in edge_data and edge_data['relationship_type'] in relationship_types):
                        next_frontier.add(predecessor)
                        visited.add(predecessor)
                        related_facts.append(predecessor)
        
        frontier = next_frontier
        current_depth += 1
    
    return related_facts

def find_facts_by_quality_range(knowledge_graph, min_quality, max_quality=None):
    """
    Find facts within a quality score range.
    
    Args:
        knowledge_graph: The knowledge graph
        min_quality (int): Minimum quality score
        max_quality (int, optional): Maximum quality score. Defaults to None.
        
    Returns:
        list: List of fact IDs within the quality range
    """
    # Get the graph
    G = knowledge_graph.graph
    
    # Get quality scores
    quality_scores = {}
    for node_id, node_data in G.nodes(data=True):
        if 'quality_score' in node_data:
            quality_scores[node_id] = node_data['quality_score']
    
    # Filter by quality range
    if max_quality is None:
        matching_facts = [node_id for node_id, score in quality_scores.items() if score >= min_quality]
    else:
        matching_facts = [node_id for node_id, score in quality_scores.items() if min_quality <= score <= max_quality]
    
    return matching_facts

def get_fact_relationships(knowledge_graph, fact_id):
    """
    Get all relationships for a specific fact.
    
    Args:
        knowledge_graph: The knowledge graph
        fact_id (str): ID of the fact
        
    Returns:
        dict: Dictionary with relationship information
        
    Raises:
        ValueError: If fact_id is not found in the graph
    """
    # Get the graph
    G = knowledge_graph.graph
    
    # Check if fact exists
    if fact_id not in G:
        raise ValueError(f"Fact ID '{fact_id}' not found in the graph.")
    
    # Get outgoing relationships
    outgoing = []
    for target in G.successors(fact_id):
        edge_data = G.get_edge_data(fact_id, target)
        relationship_type = edge_data.get('relationship_type', 'unknown')
        weight = edge_data.get('weight', 1.0)
        
        outgoing.append({
            'target_id': target,
            'relationship_type': relationship_type,
            'weight': weight,
            'attributes': {k: v for k, v in edge_data.items() if k not in ['relationship_type', 'weight']}
        })
    
    # Get incoming relationships
    incoming = []
    for source in G.predecessors(fact_id):
        edge_data = G.get_edge_data(source, fact_id)
        relationship<response clipped><NOTE>To save on context only part of this file has been shown to you. You should retry this tool after you have searched inside the file with `grep -n` in order to find the line numbers of what you are looking for.</NOTE>