"""
Integration module for the KnowledgeReduce framework.
This module provides functions to integrate all components of the framework.
"""
from .core import KnowledgeGraph, ReliabilityRating
from .visualization import visualize_graph, visualize_fact_neighborhood, create_graph_statistics
from .analysis import (identify_central_facts, identify_fact_clusters, 
                      calculate_fact_similarity, find_similar_facts, 
                      analyze_fact_categories, find_path_between_facts)
from .query import KnowledgeQuery, find_facts_by_pattern, get_facts_with_relationship, get_related_facts
from .utils import (scrape_webpage, extract_entities_from_text, 
                   create_knowledge_graph_from_text, create_knowledge_graph_from_url,
                   merge_knowledge_graphs)

class KnowledgeReduceFramework:
    """
    Main class for the KnowledgeReduce framework that integrates all components.
    """
    def __init__(self):
        """Initialize the KnowledgeReduce framework with a new knowledge graph."""
        self.knowledge_graph = KnowledgeGraph()
    
    def load_from_file(self, filepath, format='gexf'):
        """
        Load a knowledge graph from a file.
        
        Args:
            filepath (str): Path to the file
            format (str): File format ('gexf' or 'graphml')
            
        Returns:
            bool: True if loading was successful
        """
        if format.lower() == 'gexf':
            return self.knowledge_graph.import_from_gexf(filepath)
        elif format.lower() == 'graphml':
            return self.knowledge_graph.import_from_graphml(filepath)
        else:
            raise ValueError(f"Unsupported format: {format}. Use 'gexf' or 'graphml'.")
    
    def save_to_file(self, filepath, format='gexf'):
        """
        Save the knowledge graph to a file.
        
        Args:
            filepath (str): Path to save the file
            format (str): File format ('gexf' or 'graphml')
            
        Returns:
            bool: True if saving was successful
        """
        if format.lower() == 'gexf':
            return self.knowledge_graph.export_to_gexf(filepath)
        elif format.lower() == 'graphml':
            return self.knowledge_graph.export_to_graphml(filepath)
        else:
            raise ValueError(f"Unsupported format: {format}. Use 'gexf' or 'graphml'.")
    
    def create_from_url(self, url):
        """
        Create a knowledge graph from a webpage.
        
        Args:
            url (str): URL of the webpage
            
        Returns:
            KnowledgeReduceFramework: Self for method chaining
        """
        self.knowledge_graph = create_knowledge_graph_from_url(url)
        return self
    
    def create_from_text(self, text):
        """
        Create a knowledge graph from text.
        
        Args:
            text (str): Text content
            
        Returns:
            KnowledgeReduceFramework: Self for method chaining
        """
        self.knowledge_graph = create_knowledge_graph_from_text(text)
        return self
    
    def merge_with(self, other_framework):
        """
        Merge with another KnowledgeReduceFramework instance.
        
        Args:
            other_framework (KnowledgeReduceFramework): Another framework instance
            
        Returns:
            KnowledgeReduceFramework: Self for method chaining
        """
        self.knowledge_graph = merge_knowledge_graphs(
            self.knowledge_graph, 
            other_framework.knowledge_graph
        )
        return self
    
    def add_fact(self, fact_id, fact_statement, category, tags=None, 
                reliability_rating=ReliabilityRating.UNVERIFIED, **kwargs):
        """
        Add a fact to the knowledge graph with simplified parameters.
        
        Args:
            fact_id (str): Unique identifier for the fact
            fact_statement (str): The fact statement
            category (str): Category of the fact
            tags (list, optional): List of tags
            reliability_rating (ReliabilityRating, optional): Reliability rating
            **kwargs: Additional parameters for the fact
            
        Returns:
            KnowledgeReduceFramework: Self for method chaining
        """
        if tags is None:
            tags = []
            
        # Set default values for required parameters
        defaults = {
            'date_recorded': kwargs.get('date_recorded', 'auto'),
            'last_updated': kwargs.get('last_updated', 'auto'),
            'source_id': kwargs.get('source_id', ''),
            'source_title': kwargs.get('source_title', ''),
            'author_creator': kwargs.get('author_creator', ''),
            'publication_date': kwargs.get('publication_date', 'auto'),
            'url_reference': kwargs.get('url_reference', ''),
            'related_facts': kwargs.get('related_facts', []),
            'contextual_notes': kwargs.get('contextual_notes', ''),
            'access_level': kwargs.get('access_level', 'public'),
            'usage_count': kwargs.get('usage_count', 1)
        }
        
        # Add fact to the knowledge graph
        self.knowledge_graph.add_fact(
            fact_id=fact_id,
            fact_statement=fact_statement,
            category=category,
            tags=tags,
            reliability_rating=reliability_rating,
            **defaults
        )
        
        return self
    
    def visualize(self, max_nodes=20, **kwargs):
        """
        Visualize the knowledge graph.
        
        Args:
            max_nodes (int, optional): Maximum number of nodes to display
            **kwargs: Additional parameters for visualization
            
        Returns:
            matplotlib.figure.Figure: The figure object
        """
        return visualize_graph(self.knowledge_graph, max_nodes=max_nodes, **kwargs)
    
    def visualize_fact(self, fact_id, **kwargs):
        """
        Visualize a specific fact and its neighborhood.
        
        Args:
            fact_id (str): ID of the fact to visualize
            **kwargs: Additional parameters for visualization
            
        Returns:
            matplotlib.figure.Figure: The figure object
        """
        return visualize_fact_neighborhood(self.knowledge_graph, fact_id, **kwargs)
    
    def get_statistics(self):
        """
        Get statistics about the knowledge graph.
        
        Returns:
            dict: Dictionary with graph statistics
        """
        return create_graph_statistics(self.knowledge_graph)
    
    def get_central_facts(self, top_n=10, method='betweenness'):
        """
        Get the most central facts in the knowledge graph.
        
        Args:
            top_n (int, optional): Number of top central facts to return
            method (str, optional): Centrality measure to use
            
        Returns:
            list: List of tuples (fact_id, centrality_score)
        """
        return identify_central_facts(self.knowledge_graph, top_n=top_n, method=method)
    
    def get_fact_clusters(self, min_cluster_size=3):
        """
        Get clusters of related facts.
        
        Args:
            min_cluster_size (int, optional): Minimum size of clusters to return
            
        Returns:
            list: List of fact clusters
        """
        return identify_fact_clusters(self.knowledge_graph, min_cluster_size=min_cluster_size)
    
    def find_similar_facts(self, fact_id, threshold=0.5, max_results=10):
        """
        Find facts similar to a given fact.
        
        Args:
            fact_id (str): ID of the reference fact
            threshold (float, optional): Minimum similarity score
            max_results (int, optional): Maximum number of results
            
        Returns:
            list: List of tuples (fact_id, similarity_score)
        """
        return find_similar_facts(
            self.knowledge_graph, 
            fact_id, 
            threshold=threshold, 
            max_results=max_results
        )
    
    def analyze_categories(self):
        """
        Analyze the distribution of fact categories.
        
        Returns:
            dict: Dictionary with category statistics
        """
        return analyze_fact_categories(self.knowledge_graph)
    
    def find_path(self, source_id, target_id, max_length=None):
        """
        Find the shortest path between two facts.
        
        Args:
            source_id (str): ID of the source fact
            target_id (str): ID of the target fact
            max_length (int, optional): Maximum path length
            
        Returns:
            list: List of fact IDs representing the path
        """
        return find_path_between_facts(
            self.knowledge_graph, 
            source_id, 
            target_id, 
            max_length=max_length
        )
    
    def query(self):
        """
        Create a query object for the knowledge graph.
        
        Returns:
            KnowledgeQuery: Query object
        """
        return KnowledgeQuery(self.knowledge_graph)
    
    def find_by_pattern(self, pattern, field='fact_statement'):
        """
        Find facts matching a regular expression pattern.
        
        Args:
            pattern (str): Regular expression pattern
            field (str, optional): Field to search in
            
        Returns:
            list: List of fact IDs matching the pattern
        """
        return find_facts_by_pattern(self.knowledge_graph, pattern, field=field)
    
    def get_with_relationship(self, relationship_type, as_source=True, as_target=True):
        """
        Find facts with a specific relationship type.
        
        Args:
            relationship_type (str): Type of relationship
            as_source (bool, optional): Include facts that are sources
            as_target (bool, optional): Include facts that are targets
            
        Returns:
            dict: Dictionary with 'sources' and 'targets' lists
        """
        return get_facts_with_relationship(
            self.knowledge_graph, 
            relationship_type, 
            as_source=as_source, 
            as_target=as_target
        )
    
    def get_related(self, fact_id, relationship_types=None, max_depth=1):
        """
        Get facts related to a given fact.
        
        Args:
            fact_id (str): ID of the fact
            relationship_types (list, optional): Types of relationships to follow
            max_depth (int, optional): Maximum depth of relationships
            
        Returns:
            list: List of related fact IDs
        """
        return get_related_facts(
            self.knowledge_graph, 
            fact_id, 
            relationship_types=relationship_types, 
            max_depth=max_depth
        )
