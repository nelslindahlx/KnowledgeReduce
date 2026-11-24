"""
Query module for knowledge graphs.
This module provides functions for querying and extracting information from knowledge graphs.
"""
import re
from datetime import datetime

class KnowledgeQuery:
    """
    Class for querying knowledge graphs with various filtering and sorting options.
    """
    def __init__(self, knowledge_graph):
        """
        Initialize the query object with a knowledge graph.
        
        Args:
            knowledge_graph: The knowledge graph object to query
        """
        self.kg = knowledge_graph
        self.results = []
        self.filters = []
        self.sort_by = None
        self.sort_reverse = False
        self.limit = None
    
    def reset(self):
        """Reset all query parameters."""
        self.results = []
        self.filters = []
        self.sort_by = None
        self.sort_reverse = False
        self.limit = None
        return self
    
    def filter_by_category(self, category):
        """
        Filter facts by category.
        
        Args:
            category (str): Category to filter by
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        self.filters.append(lambda node_id, data: 
                           'category' in data and data['category'] == category)
        return self
    
    def filter_by_tag(self, tag):
        """
        Filter facts by tag.
        
        Args:
            tag (str): Tag to filter by
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        self.filters.append(lambda node_id, data: 
                           'tags' in data and tag in data['tags'].split(', '))
        return self
    
    def filter_by_reliability(self, min_rating):
        """
        Filter facts by minimum reliability rating.
        
        Args:
            min_rating: Minimum reliability rating (ReliabilityRating enum)
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        self.filters.append(lambda node_id, data: 
                           'reliability_rating' in data and 
                           data['reliability_rating'].value >= min_rating.value)
        return self
    
    def filter_by_quality_score(self, min_score):
        """
        Filter facts by minimum quality score.
        
        Args:
            min_score (int): Minimum quality score
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        self.filters.append(lambda node_id, data: 
                           'quality_score' in data and 
                           data['quality_score'] >= min_score)
        return self
    
    def filter_by_text(self, text, fields=None):
        """
        Filter facts by text content in specified fields.
        
        Args:
            text (str): Text to search for
            fields (list, optional): Fields to search in. If None, searches in fact_statement.
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        if fields is None:
            fields = ['fact_statement']
            
        def text_filter(node_id, data):
            for field in fields:
                if field in data and isinstance(data[field], str):
                    if text.lower() in data[field].lower():
                        return True
            return False
            
        self.filters.append(text_filter)
        return self
    
    def filter_by_date_range(self, field, start_date=None, end_date=None):
        """
        Filter facts by date range in a specified date field.
        
        Args:
            field (str): Date field to filter on (e.g., 'date_recorded', 'publication_date')
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        def date_filter(node_id, data):
            if field not in data:
                return False
                
            date_str = data[field]
            try:
                # Parse date string
                date = datetime.fromisoformat(date_str)
                
                # Check range
                if start_date and date < start_date:
                    return False
                if end_date and date > end_date:
                    return False
                return True
            except (ValueError, TypeError):
                return False
                
        self.filters.append(date_filter)
        return self
    
    def filter_by_custom(self, filter_func):
        """
        Filter facts by a custom filter function.
        
        Args:
            filter_func: Function that takes (node_id, data) and returns boolean
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        self.filters.append(filter_func)
        return self
    
    def sort(self, field, reverse=False):
        """
        Sort results by a specified field.
        
        Args:
            field (str): Field to sort by
            reverse (bool, optional): Whether to sort in descending order
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        self.sort_by = field
        self.sort_reverse = reverse
        return self
    
    def limit_results(self, limit):
        """
        Limit the number of results.
        
        Args:
            limit (int): Maximum number of results to return
            
        Returns:
            KnowledgeQuery: Self for method chaining
        """
        self.limit = limit
        return self
    
    def execute(self):
        """
        Execute the query and return results.
        
        Returns:
            list: List of (fact_id, fact_data) tuples matching the query
        """
        # Get all nodes from the graph
        nodes = list(self.kg.graph.nodes(data=True))
        
        # Apply filters
        filtered_nodes = nodes
        for filter_func in self.filters:
            filtered_nodes = [(node_id, data) for node_id, data in filtered_nodes 
                             if filter_func(node_id, data)]
        
        # Sort if specified
        if self.sort_by:
            try:
                filtered_nodes.sort(
                    key=lambda x: x[1].get(self.sort_by, None), 
                    reverse=self.sort_reverse
                )
            except (TypeError, KeyError):
                # If sorting fails, ignore it
                pass
        
        # Apply limit if specified
        if self.limit is not None:
            filtered_nodes = filtered_nodes[:self.limit]
        
        self.results = filtered_nodes
        return filtered_nodes
    
    def get_fact_ids(self):
        """
        Get just the fact IDs from the query results.
        
        Returns:
            list: List of fact IDs matching the query
        """
        if not self.results:
            self.execute()
        return [node_id for node_id, _ in self.results]
    
    def get_values(self, field):
        """
        Get values of a specific field from the query results.
        
        Args:
            field (str): Field to extract
            
        Returns:
            list: List of field values from matching facts
        """
        if not self.results:
            self.execute()
        return [data.get(field, None) for _, data in self.results]

def find_facts_by_pattern(knowledge_graph, pattern, field='fact_statement'):
    """
    Find facts matching a regular expression pattern in a specified field.
    
    Args:
        knowledge_graph: The knowledge graph object
        pattern (str): Regular expression pattern
        field (str): Field to search in
        
    Returns:
        list: List of fact IDs matching the pattern
    """
    compiled_pattern = re.compile(pattern, re.IGNORECASE)
    matches = []
    
    for node_id, data in knowledge_graph.graph.nodes(data=True):
        if field in data and isinstance(data[field], str):
            if compiled_pattern.search(data[field]):
                matches.append(node_id)
    
    return matches

def get_facts_with_relationship(knowledge_graph, relationship_type, as_source=True, as_target=True):
    """
    Find facts that have a specific relationship type.
    
    Args:
        knowledge_graph: The knowledge graph object
        relationship_type (str): Type of relationship to look for
        as_source (bool): Whether to include facts that are sources of this relationship
        as_target (bool): Whether to include facts that are targets of this relationship
        
    Returns:
        dict: Dictionary with 'sources' and 'targets' lists of fact IDs
    """
    G = knowledge_graph.graph
    sources = set()
    targets = set()
    
    for u, v, data in G.edges(data=True):
        if 'relationship_type' in data and data['relationship_type'] == relationship_type:
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
    Get facts related to a given fact through specified relationship types.
    
    Args:
        knowledge_graph: The knowledge graph object
        fact_id (str): ID of the fact to find related facts for
        relationship_types (list, optional): Types of relationships to follow
        max_depth (int): Maximum depth of relationships to traverse
        
    Returns:
        list: List of related fact IDs
    """
    G = knowledge_graph.graph
    
    if fact_id not in G:
        raise ValueError(f"Fact ID '{fact_id}' not found in the graph")
    
    related = set()
    current = {fact_id}
    
    for depth in range(max_depth):
        next_level = set()
        
        for current_id in current:
            # Get outgoing relationships
            for target in G.successors(current_id):
                edge_data = G.get_edge_data(current_id, target)
                rel_type = edge_data.get('relationship_type', None)
                
                if relationship_types is None or rel_type in relationship_types:
                    if target != fact_id and target not in related:
                        next_level.add(target)
            
            # Get incoming relationships
            for source in G.predecessors(current_id):
                edge_data = G.get_edge_data(source, current_id)
                rel_type = edge_data.get('relationship_type', None)
                
                if relationship_types is None or rel_type in relationship_types:
                    if source != fact_id and source not in related:
                        next_level.add(source)
        
        related.update(next_level)
        current = next_level
        
        if not current:
            break
    
    return list(related)
