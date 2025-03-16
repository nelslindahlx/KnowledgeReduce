"""
API Documentation for the KnowledgeReduce Framework

This document provides detailed API documentation for all modules and classes
in the KnowledgeReduce framework.
"""

# Core Module

## KnowledgeGraph

```python
class KnowledgeGraph:
    """
    Core class for representing a knowledge graph.
    
    A knowledge graph consists of facts (nodes) and relationships (edges).
    Each fact has attributes such as statement, category, tags, and reliability rating.
    Relationships connect facts and have a type and weight.
    """
    
    def __init__(self):
        """Initialize a new empty knowledge graph."""
        
    def add_fact(self, fact_id, fact_statement, category, tags=None, 
                date_recorded=None, last_updated=None, reliability_rating=None, 
                source_id=None, source_title=None, author_creator=None, 
                publication_date=None, url_reference=None, related_facts=None, 
                contextual_notes=None, access_level=None, usage_count=None, 
                source_quality=None, **kwargs):
        """
        Add a fact to the knowledge graph.
        
        Args:
            fact_id (str): Unique identifier for the fact
            fact_statement (str): The fact statement
            category (str): Category of the fact
            tags (list, optional): List of tags
            date_recorded (str, optional): Date when the fact was recorded
            last_updated (str, optional): Date when the fact was last updated
            reliability_rating (ReliabilityRating, optional): Reliability rating
            source_id (str, optional): ID of the source
            source_title (str, optional): Title of the source
            author_creator (str, optional): Author or creator of the fact
            publication_date (str, optional): Publication date of the source
            url_reference (str, optional): URL reference
            related_facts (list, optional): List of related fact IDs
            contextual_notes (str, optional): Contextual notes
            access_level (str, optional): Access level (e.g., 'public', 'restricted')
            usage_count (int, optional): Number of times the fact has been used
            source_quality (int, optional): Quality score of the source
            **kwargs: Additional attributes for the fact
            
        Returns:
            bool: True if the fact was added successfully
            
        Raises:
            ValueError: If a fact with the same ID already exists
        """
        
    def get_fact(self, fact_id):
        """
        Get a fact from the knowledge graph.
        
        Args:
            fact_id (str): ID of the fact
            
        Returns:
            dict: Fact data
            
        Raises:
            ValueError: If the fact is not found
        """
        
    def update_fact(self, fact_id, **kwargs):
        """
        Update a fact in the knowledge graph.
        
        Args:
            fact_id (str): ID of the fact
            **kwargs: Attributes to update
            
        Returns:
            bool: True if the fact was updated successfully
            
        Raises:
            ValueError: If the fact is not found
        """
        
    def add_relationship(self, source_fact_id, target_fact_id, relationship_type, 
                        weight=1.0, attributes=None):
        """
        Add a relationship between two facts.
        
        Args:
            source_fact_id (str): ID of the source fact
            target_fact_id (str): ID of the target fact
            relationship_type (str): Type of relationship
            weight (float, optional): Weight of the relationship. Defaults to 1.0.
            attributes (dict, optional): Additional attributes. Defaults to None.
            
        Returns:
            bool: True if the relationship was added successfully
            
        Raises:
            ValueError: If either fact is not found
        """
        
    def get_relationships(self, fact_id):
        """
        Get all relationships for a fact.
        
        Args:
            fact_id (str): ID of the fact
            
        Returns:
            dict: Dictionary with 'outgoing' and 'incoming' relationships
            
        Raises:
            ValueError: If the fact is not found
        """
        
    def search_facts(self, text, fields=None, case_sensitive=False):
        """
        Search for facts containing specific text.
        
        Args:
            text (str): Text to search for
            fields (list, optional): Fields to search in. Defaults to ['fact_statement'].
            case_sensitive (bool, optional): Whether the search is case-sensitive. Defaults to False.
            
        Returns:
            list: List of fact IDs matching the search
        """
        
    def calculate_quality_score(self, reliability_rating, usage_count=0, 
                              related_facts_count=0, source_quality=0):
        """
        Calculate a quality score for a fact.
        
        Args:
            reliability_rating (ReliabilityRating): Reliability rating
            usage_count (int, optional): Number of times the fact has been used. Defaults to 0.
            related_facts_count (int, optional): Number of related facts. Defaults to 0.
            source_quality (int, optional): Quality score of the source. Defaults to 0.
            
        Returns:
            int: Quality score
        """
        
    def export_to_json(self, filepath, shard_size=None):
        """
        Export the knowledge graph to a JSON file.
        
        Args:
            filepath (str): Path to save the file
            shard_size (int, optional): Number of nodes per shard. Defaults to None.
            
        Returns:
            list: List of file paths (main file or shards)
        """
        
    def import_from_json(self, filepath):
        """
        Import a knowledge graph from a JSON file.
        
        Args:
            filepath (str): Path to the file
            
        Returns:
            bool: True if the import was successful
        """
        
    def export_to_gexf(self, filepath):
        """
        Export the knowledge graph to a GEXF file.
        
        Args:
            filepath (str): Path to save the file
            
        Returns:
            bool: True if the export was successful
        """
        
    def import_from_gexf(self, filepath):
        """
        Import a knowledge graph from a GEXF file.
        
        Args:
            filepath (str): Path to the file
            
        Returns:
            bool: True if the import was successful
        """
        
    def export_to_graphml(self, filepath):
        """
        Export the knowledge graph to a GraphML file.
        
        Args:
            filepath (str): Path to save the file
            
        Returns:
            bool: True if the export was successful
        """
        
    def import_from_graphml(self, filepath):
        """
        Import a knowledge graph from a GraphML file.
        
        Args:
            filepath (str): Path to the file
            
        Returns:
            bool: True if the import was successful
        """

## StackableKnowledgeGraph

```python
class StackableKnowledgeGraph:
    """
    Class for representing a stackable knowledge graph.
    
    A stackable knowledge graph consists of multiple layers of knowledge graphs,
    with inheritance relationships between layers.
    """
    
    def __init__(self):
        """Initialize a new empty stackable knowledge graph with a base layer."""
        
    def add_layer(self, layer_name, parent_layer=None):
        """
        Add a new layer to the stackable knowledge graph.
        
        Args:
            layer_name (str): Name of the new layer
            parent_layer (str, optional): Name of the parent layer. Defaults to None.
            
        Returns:
            bool: True if the layer was added successfully
            
        Raises:
            ValueError: If the layer already exists or the parent layer doesn't exist
        """
        
    def get_layer(self, layer_name):
        """
        Get a specific layer of the stackable knowledge graph.
        
        Args:
            layer_name (str): Name of the layer
            
        Returns:
            KnowledgeGraph: The requested layer
            
        Raises:
            ValueError: If the layer doesn't exist
        """
        
    def add_fact_to_layer(self, layer_name, fact_id, fact_statement, category, 
                         tags=None, date_recorded=None, last_updated=None, 
                         reliability_rating=None, source_id=None, source_title=None, 
                         author_creator=None, publication_date=None, url_reference=None, 
                         related_facts=None, contextual_notes=None, access_level=None, 
                         usage_count=None, source_quality=None, **kwargs):
        """
        Add a fact to a specific layer.
        
        Args:
            layer_name (str): Name of the layer
            fact_id (str): Unique identifier for the fact
            fact_statement (str): The fact statement
            category (str): Category of the fact
            tags (list, optional): List of tags
            date_recorded (str, optional): Date when the fact was recorded
            last_updated (str, optional): Date when the fact was last updated
            reliability_rating (ReliabilityRating, optional): Reliability rating
            source_id (str, optional): ID of the source
            source_title (str, optional): Title of the source
            author_creator (str, optional): Author or creator of the fact
            publication_date (str, optional): Publication date of the source
            url_reference (str, optional): URL reference
            related_facts (list, optional): List of related fact IDs
            contextual_notes (str, optional): Contextual notes
            access_level (str, optional): Access level (e.g., 'public', 'restricted')
            usage_count (int, optional): Number of times the fact has been used
            source_quality (int, optional): Quality score of the source
            **kwargs: Additional attributes for the fact
            
        Returns:
            bool: True if the fact was added successfully
            
        Raises:
            ValueError: If the layer doesn't exist
        """
        
    def add_relationship_to_layer(self, layer_name, source_fact_id, target_fact_id, 
                                relationship_type, weight=1.0, attributes=None):
        """
        Add a relationship to a specific layer.
        
        Args:
            layer_name (str): Name of the layer
            source_fact_id (str): ID of the source fact
            target_fact_id (str): ID of the target fact
            relationship_type (str): Type of relationship
            weight (float, optional): Weight of the relationship. Defaults to 1.0.
            attributes (dict, optional): Additional attributes. Defaults to None.
            
        Returns:
            bool: True if the relationship was added successfully
            
        Raises:
            ValueError: If the layer doesn't exist or either fact is not found
        """
        
    def get_fact(self, fact_id, layer_name=None):
        """
        Get a fact from the stackable knowledge graph.
        
        Args:
            fact_id (str): ID of the fact
            layer_name (str, optional): Name of the layer. Defaults to None.
            
        Returns:
            dict: Fact data
            
        Raises:
            ValueError: If the fact is not found
        """
        
    def get_merged_graph(self):
        """
        Get a merged view of all layers.
        
        Returns:
            KnowledgeGraph: A new knowledge graph containing the merged view
        """
        
    def export_layer_to_json(self, layer_name, filepath, shard_size=None):
        """
        Export a specific layer to a JSON file.
        
        Args:
            layer_name (str): Name of the layer
            filepath (str): Path to save the file
            shard_size (int, optional): Number of nodes per shard. Defaults to None.
            
        Returns:
            list: List of file paths (main file or shards)
            
        Raises:
            ValueError: If the layer doesn't exist
        """

## ReliabilityRating

```python
class ReliabilityRating(Enum):
    """
    Enum for fact reliability ratings.
    
    Values:
        VERIFIED (4): Fact has been verified by multiple reliable sources
        LIKELY_TRUE (3): Fact is likely true based on reliable sources
        POSSIBLY_TRUE (2): Fact is possibly true but needs more verification
        UNVERIFIED (1): Fact has not been verified
        DISPUTED (0): Fact is disputed by reliable sources
    """
    
    VERIFIED = 4
    LIKELY_TRUE = 3
    POSSIBLY_TRUE = 2
    UNVERIFIED = 1
    DISPUTED = 0

# Integration Module

## KnowledgeReduceFramework

```python
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
        
    def load_from_file(self, filepath, format='json'):
        """
        Load a knowledge graph from a file.
        
        Args:
            filepath (str): Path to the file
            format (str): File format ('json', 'gexf', or 'graphml')
            
        Returns:
            bool: True if loading was successful
        """
        
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
        
    def create_from_url(self, url):
        """
        Create a knowledge graph from a webpage.
        
        Args:
            url (str): URL of the webpage
            
        Returns:
            KnowledgeReduceFramework: Self for method chaining
        """
        
    def create_from_text(self, text):
        """
        Create a knowledge graph from text.
        
        Args:
            text (str): Text content
            
        Returns:
            KnowledgeReduceFramework: Self for method chaining
        """
        
    def merge_with(self, other_framework):
        """
        Merge with another KnowledgeReduceFramework instance.
        
        Args:
            other_framework (KnowledgeReduceFramework): Another framework instance
            
        Returns:
            KnowledgeReduceFramework: Self for method chaining
        """
        
    def add_fact(self, fact_id, fact_statement, category, tags=None, 
                reliability_rating=ReliabilityRating.UNVERIFIED, layer_name=None, **kwargs):
        """
        Add a fact to the knowledge graph with simplified parameters.
        
        Args:
            fact_id (str): Unique identifier for the fact
            fact_statement (str): The fact statement
            category (str): Category of the fact
            tags (list, optional): List of tags<response clipped><NOTE>To save on context only part of this file has been shown to you. You should retry this tool after you have searched inside the file with `grep -n` in order to find the line numbers of what you are looking for.</NOTE>