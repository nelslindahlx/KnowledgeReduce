"""
Integration module for the KnowledgeReduce framework.
This module provides the main framework class that integrates all components.
"""

from datetime import datetime
from ..core.core import KnowledgeGraph, StackableKnowledgeGraph, ReliabilityRating
from ..visualization.visualization import (
    visualize_graph, visualize_fact_neighborhood, 
    create_graph_statistics, visualize_graph_statistics
)
from ..analysis.analysis import (
    identify_central_facts, identify_fact_clusters, 
    calculate_fact_similarity, find_similar_facts, 
    analyze_fact_categories, find_path_between_facts,
    extract_keywords_from_fact, analyze_fact_reliability,
    identify_conflicting_facts, analyze_fact_usage
)
from ..query.query import (
    KnowledgeQuery, find_facts_by_pattern, 
    get_facts_with_relationship, get_related_facts,
    find_facts_by_quality_range, get_fact_relationships,
    find_facts_by_relationship_count
)
from ..serialization.serialization import (
    KnowledgeGraphSerializer, StackableKnowledgeGraphSerializer
)
from ..utils.utils import (
    scrape_webpage, extract_entities_from_text,
    create_knowledge_graph_from_text, create_knowledge_graph_from_url,
    merge_knowledge_graphs
)

class KnowledgeReduceFramework:
    """
    Main class for the KnowledgeReduce framework that integrates all components.
    
    This class provides a high-level API for working with knowledge graphs,
    with methods for creating, analyzing, visualizing, and querying knowledge graphs.
    """
    
    def __init__(self, use_stackable=False):
        """
        Initialize the KnowledgeReduce framework with a new knowledge graph.
        
        Args:
            use_stackable (bool, optional): Whether to use a stackable knowledge graph. Defaults to False.
        """
        if use_stackable:
            self.knowledge_graph = StackableKnowledgeGraph()
            self._is_stackable = True
        else:
            self.knowledge_graph = KnowledgeGraph()
            self._is_stackable = False
    
    # ===== Loading and Saving =====
    
    def load_from_file(self, filepath, format='json'):
        """
        Load a knowledge graph from a file.
        
        Args:
            filepath (str): Path to the file
            format (str): File format ('json', 'gexf', or 'graphml')
            
        Returns:
            bool: True if loading was successful
        """
        if self._is_stackable:
            if format.lower() == 'json':
                self.knowledge_graph = StackableKnowledgeGraphSerializer.from_json(filepath)
                return True
            else:
                raise ValueError(f"Unsupported format for stackable knowledge graph: {format}. Use 'json'.")
        else:
            if format.lower() == 'json':
                self.knowledge_graph = KnowledgeGraphSerializer.from_json(filepath)
                return True
            elif format.lower() == 'gexf':
                return self.knowledge_graph.import_from_gexf(filepath)
            elif format.lower() == 'graphml':
                return self.knowledge_graph.import_from_graphml(filepath)
            else:
                raise ValueError(f"Unsupported format: {format}. Use 'json', 'gexf', or 'graphml'.")
    
    def save_to_file(self, filepath, format='json', shard_size=100):
        """
        Save the knowledge graph to a file.
        
        Args:
            filepath (str): Path to save the file
            format (str): File format ('json', 'gexf', or 'graphml')
            shard_size (int, optional): Number of nodes per shard for JSON format. Defaults to 100.
            
        Returns:
            bool or list: True if saving was successful, or list of file paths for sharded JSON
        """
        if self._is_stackable:
            if format.lower() == 'json':
                return StackableKnowledgeGraphSerializer.to_json(self.knowledge_graph, filepath, shard_size)
            else:
                raise ValueError(f"Unsupported format for stackable knowledge graph: {format}. Use 'json'.")
        else:
            if format.lower() == 'json':
                return self.knowledge_graph.export_to_json(filepath, shard_size)
            elif format.lower() == 'gexf':
                return self.knowledge_graph.export_to_gexf(filepath)
            elif format.lower() == 'graphml':
                return self.knowledge_graph.export_to_graphml(filepath)
            else:
                raise ValueError(f"Unsupported format: {format}. Use 'json', 'gexf', or 'graphml'.")
    
    # ===== Creation Methods =====
    
    def create_from_url(self, url):
        """
        Create a knowledge graph from a webpage.
        
        Args:
            url (str): URL of the webpage
            
        Returns:
            KnowledgeReduceFramework: Self for method chaining
        """
        if self._is_stackable:
            # For stackable graphs, add to base layer
            layer = self.knowledge_graph.get_layer("base")
            create_knowledge_graph_from_url(url, layer)
        else:
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
        if self._is_stackable:
            # For stackable graphs, add to base layer
            layer = self.knowledge_graph.get_layer("base")
            create_knowledge_graph_from_text(text, layer)
        else:
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
        if self._is_stackable != other_framework._is_stackable:
            raise ValueError("Cannot merge stackable and non-stackable knowledge graphs.")
        
        if self._is_stackable:
            # For stackable graphs, merge each layer
            for layer_name in other_framework.knowledge_graph.layer_order:
                if layer_name in self.knowledge_graph.layers:
                    # Merge existing layer
                    self.knowledge_graph.layers[layer_name] = merge_knowledge_graphs(
                        self.knowledge_graph.layers[layer_name],
                        other_framework.knowledge_graph.layers[layer_name]
                    )
                else:
                    # Add new layer
                    self.knowledge_graph.add_layer(layer_name)
                    self.knowledge_graph.layers[layer_name] = other_framework.knowledge_graph.layers[layer_name]
        else:
            self.knowledge_graph = merge_knowledge_graphs(
                self.knowledge_graph,
                other_framework.knowledge_graph
            )
        return self
    
    # ===== Fact Management =====
    
    def add_fact(self, fact_id, fact_statement, category, tags=None, 
                reliability_rating=ReliabilityRating.UNVERIFIED, layer_name=None, **kwargs):
        """
        Add a fact to the knowledge graph with simplified parameters.
        
        Args:
            fact_id (str): Unique identifier for the fact
            fact_statement (str): The fact statement
            category (str): Category of the fact
            tags (list, optional): List of tags
            reliability_rating (ReliabilityRating, optional): Reliability rating
            layer_name (str, optional): Layer to add the fact to (for stackable graphs)
            **kwargs: Additional parameters for the fact
            
        Returns:
            KnowledgeReduceFramework: Self for method chaining
        """
        if tags is None:
            tags = []
            
        # Set default values for required parameters
        defaults = {
            'date_recorded': kwargs.get('date_recorded', datetime.now().isoformat()),
            'last_updated': kwargs.get('last_updated', datetime.now().isoformat()),
            'source_id': kwargs.get('source_id', ''),
            'source_title': kwargs.get('source_title', ''),
            'author_creator': kwargs.get('author_creator', ''),
            'publication_date': kwargs.get('publication_date', ''),
            'url_reference': kwargs.get('url_reference', ''),
            'related_facts': kwargs.get('related_facts', []),
            'contextual_notes': kwargs.get('contextual_notes', ''),
            'access_level': kwargs.get('access_level', 'public'),
            'usage_count': kwargs.get('usage_count', 1),
            'source_quality': kwargs.get('source_quality', 0)
        }
        
        # Add fact to the knowledge graph
        if self._is_stackable and layer_name:
            self.knowledge_graph.add_fact_to_layer(
                layer_name,
                fact_id=fact_id,
                fact_statement=fact_statement,
                category=category,
                tags=tags,
                reliability_rating=reliability_rating,
                **defaults
            )
        else:
            self.knowledge_graph.add_fact(
                fact_id=fact_id,
                fact_statement=fact_statement,
                category=category,
                tags=tags,
                reliability_rating=reliability_rating,
                **defaults
            )
        
        return self
    
    def add_relationship(self, source_fact_id, target_fact_id, relationship_type, 
                        weight=1.0, attributes=None, layer_name=None):
        """
        Add a relationship between two facts.
        
        Args:
            source_fact_id (str): ID of the source fact
            target_fact_id (str): ID of the target fact
            relationship_type (str): Type of relationship
            weight (float, optional): Weight of the relationship. Defaults to 1.0.
            attributes (dict, optional): Additional attributes. Defaults to None.
            layer_name (str, optional): Layer to add the relationship to (for stackable graphs)
            
        Returns:
            KnowledgeReduceFramework: Self for method chaining
        """
        if self._is_stackable and layer_name:
            self.knowledge_graph.add_relationship_to_layer(
                layer_name,
                source_fact_id,
                target_fact_id,
                relationship_type,
                weight,
                attributes
            )
        else:
            self.knowledge_graph.add_relationship(
                source_fact_id,
                target_fact_id,
                relationship_type,
                weight,
                attributes
            )
        
        return self
    
    def get_fact(self, fact_id, layer_name=None):
        """
        Get a fact from the knowledge graph.
        
        Args:
            fact_id (str): ID of the fact
            layer_name (str, optional): Layer to get the fact from (for stackable graphs)
            
        Returns:
            dict: Fact data
        """
        if self._is_stackable:
            return self.knowledge_graph.get_fact(fact_id, layer_name)
        else:
            return self.knowledge_graph.get_fact(fact_id)
    
    def update_fact(self, fact_id, **kwargs):
        """
        Update a fact in the knowledge graph.
        
        Args:
            fact_id (str): ID of the fact
            **kwargs: Attributes to update
            
        Returns:
            KnowledgeReduceFramework: Self for method chaining
        """
        # For stackable graphs, update in all layers
        if self._is_stackable:
            for layer_name in self.knowledge_graph.layer_order:
                try:
                    layer = self.knowledge_graph.get_layer(layer_name)
                    layer.update_fact(fact_id, **kwargs)
                except ValueError:
                    # Fact not in this layer, skip
                    pass
        else:
            self.knowledge_graph.update_fact(fact_id, **kwargs)
        
        return self
    
    # ===== Layer Management (for Stackable Graphs) =====
    
    def add_layer(self, layer_name, parent_layer=None):
        """
        Add a new layer to the knowledge graph (for stackable graphs only).
        
        Args:
            layer_name (str): Name of the new layer
            parent_layer (str, optional): Name of the parent layer. Defaults to None.
            
        Returns:
            KnowledgeReduceFramework: Self for method chaining
            
        Raises:
            ValueError: If not using a stackable knowledge graph
        """
        if not self._is_stackable:
            raise ValueError("Cannot add layer to non-stackable knowledge graph. Initialize with use_stackable=True.")
        
        self.knowledge_graph.add_layer(layer_name, parent_layer)
        return self
    
    def get_layer(self, layer_name):
        """
        Get a specific layer of the knowledge graph (for stackable graphs only).
        
        Args:
            layer_name (str): Name of the layer
            
        Returns:
            KnowledgeGraph: The requested layer
            
        Raises:
            ValueError: If not using a stackable knowledge graph
        """
        if not self._is_stackable:
            raise ValueError("Cannot get layer from non-stackable knowledge graph. Initialize with use_stackable=True.")
        
        return self.knowledge_graph.get_layer(layer_name)
    
    def get_merged_graph(self):
        """
        Get a merged view of all layers (for stackable graphs only).
        
        Returns:
            KnowledgeGraph: A new knowledge graph containing the merged view
            
        Raises:
            ValueError: If not using a stackable knowledge graph
        """
        if not self._is_stackable:
            raise ValueError("Cannot get merged graph from non-stackable knowledge graph. Initialize with use_stackable=True.")
        
        return self.knowledge_graph.get_merged_graph()
    
    # ===== Visualization =====
    
    def visualize(self, max_nodes=50, **kwargs):
        """
        Visualize the knowledge graph.
        
        Args:
            max_nodes (int, optional): Maximum number of nodes to display. Defaults to 50.
            **kwargs: Additional parameters for visualization
            
        Returns:
            matplotlib.figure.Figure or str: The figure object or HTML string
        """
        if self._is_stackable and 'layer_name' in kwargs:
            # Visualize specific layer
            layer_name = kwargs.pop('layer_name')
            layer = self.knowledge_graph.get_layer(layer_name)
            return visualize_graph(layer, max_nodes=max_nodes, **kwargs)
        elif self._is_stackable:
            # Visualize merged graph
            merged_graph = self.knowledge_graph.get_merged_graph()
            return visualize_graph(merged_graph, max_nodes=max_nodes, **kwargs)
        else:
            return visualize_graph(self.knowledge_graph, max_nodes=max_nodes, **kwargs)
    
    def visualize_fact(self, fact_id, **kwargs):
        """
        Visualize a specific fact and its neighborhood.
        
        Args:
            fact_id (str): ID of the fact to visualize
            **kwargs: Additional parameters for visualization
            
        Returns:
            matplotlib.figure.Figure or str: The figure object or HTML string
        """
        if self._is_stackable and 'layer_name' in kwargs:
            # Visualize in specific layer
            layer_name = kwargs.pop('layer_name')
            layer = self.knowledge_graph.get_layer(la<response clipped><NOTE>To save on context only part of this file has been shown to you. You should retry this tool after you have searched inside the file with `grep -n` in order to find the line numbers of what you are looking for.</NOTE>