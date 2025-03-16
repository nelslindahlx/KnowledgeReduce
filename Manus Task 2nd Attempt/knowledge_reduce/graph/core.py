"""
Core data structures for the KnowledgeReduce framework.

This module contains the fundamental data structures used in the KnowledgeReduce
framework, including the ReliabilityRating enum and the KnowledgeGraph class.
"""

from enum import Enum
from datetime import datetime
import json
import networkx as nx


class ReliabilityRating(Enum):
    """
    Enum representing the reliability rating of a fact in the knowledge graph.
    
    Used to assess the quality and trustworthiness of information.
    """
    UNVERIFIED = 1
    POSSIBLY_TRUE = 2
    LIKELY_TRUE = 3
    VERIFIED = 4


class KnowledgeGraph:
    """
    Core class for the KnowledgeReduce framework.
    
    Represents a knowledge graph that stores facts with rich metadata and provides
    methods for adding, querying, and manipulating the graph.
    """
    
    def __init__(self):
        """Initialize an empty knowledge graph using NetworkX DiGraph."""
        self.graph = nx.DiGraph()
        self.data = []  # For compatibility with list-based operations
    
    def calculate_quality_score(self, reliability_rating, usage_count):
        """
        Calculate a quality score for a fact based on its reliability and usage.
        
        Args:
            reliability_rating: ReliabilityRating enum or string representation
            usage_count: Number of times the fact has been used
            
        Returns:
            float: Quality score
        """
        # Handle string representation of Enum
        if isinstance(reliability_rating, str):
            try:
                rating_value = ReliabilityRating[reliability_rating].value
            except KeyError:
                # Default to UNVERIFIED if invalid string
                rating_value = ReliabilityRating.UNVERIFIED.value
        else:
            rating_value = reliability_rating.value
            
        base_score = 10 * rating_value
        usage_bonus = 2 * usage_count
        return base_score + usage_bonus
    
    def add_fact(self, fact_id, fact_statement, category, tags, date_recorded=None, 
                 last_updated=None, reliability_rating=ReliabilityRating.UNVERIFIED, 
                 source_id=None, source_title=None, author_creator=None,
                 publication_date=None, url_reference=None, related_facts=None, 
                 contextual_notes=None, access_level="Public", usage_count=0):
        """
        Add a fact to the knowledge graph with comprehensive metadata.
        
        Args:
            fact_id: Unique identifier for the fact
            fact_statement: The actual statement or content of the fact
            category: Category or domain of the fact
            tags: List of tags associated with the fact
            date_recorded: When the fact was first recorded (defaults to now)
            last_updated: When the fact was last updated (defaults to now)
            reliability_rating: ReliabilityRating enum value
            source_id: Identifier for the source of the fact
            source_title: Title of the source
            author_creator: Author or creator of the fact
            publication_date: When the fact was published
            url_reference: URL reference for the fact
            related_facts: List of related fact IDs
            contextual_notes: Additional notes or context
            access_level: Access level for the fact
            usage_count: Number of times the fact has been used
        """
        # Set default values for timestamps
        if date_recorded is None:
            date_recorded = datetime.now()
        if last_updated is None:
            last_updated = datetime.now()
        if related_facts is None:
            related_facts = []
            
        # Convert list and datetime objects to strings for serialization
        tags_str = ', '.join(tags) if tags else ''
        date_recorded_str = date_recorded.isoformat() if isinstance(date_recorded, datetime) else date_recorded
        last_updated_str = last_updated.isoformat() if isinstance(last_updated, datetime) else last_updated
        publication_date_str = publication_date.isoformat() if isinstance(publication_date, datetime) else publication_date
        
        # Create fact data structure
        fact_data = {
            'fact_id': fact_id,
            'fact_statement': fact_statement,
            'category': category,
            'tags': tags_str,
            'date_recorded': date_recorded_str,
            'last_updated': last_updated_str,
            'reliability_rating': reliability_rating.name if isinstance(reliability_rating, ReliabilityRating) else reliability_rating,
            'source_id': source_id,
            'source_title': source_title,
            'author_creator': author_creator,
            'publication_date': publication_date_str,
            'url_reference': url_reference,
            'related_facts': related_facts,
            'contextual_notes': contextual_notes,
            'access_level': access_level,
            'usage_count': usage_count,
            'quality_score': self.calculate_quality_score(reliability_rating, usage_count)
        }
        
        # Add to both graph and list representations
        self.graph.add_node(fact_id, **fact_data)
        self.data.append(fact_data)
        
        # Add edges for related facts
        for related_fact_id in related_facts:
            self.graph.add_edge(fact_id, related_fact_id, relationship_type="related")
    
    def get_fact(self, fact_id):
        """
        Retrieve a fact by its ID.
        
        Args:
            fact_id: The ID of the fact to retrieve
            
        Returns:
            dict: The fact data or None if not found
        """
        if self.graph.has_node(fact_id):
            return dict(self.graph.nodes[fact_id])
        return None
    
    def update_fact(self, fact_id, **kwargs):
        """
        Update a fact's attributes.
        
        Args:
            fact_id: The ID of the fact to update
            **kwargs: Attributes to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.graph.has_node(fact_id):
            return False
            
        # Update last_updated timestamp
        kwargs['last_updated'] = datetime.now().isoformat()
        
        # Convert ReliabilityRating enum to string if present
        if 'reliability_rating' in kwargs and isinstance(kwargs['reliability_rating'], ReliabilityRating):
            kwargs['reliability_rating'] = kwargs['reliability_rating'].name
            
        # Update node attributes
        for key, value in kwargs.items():
            self.graph.nodes[fact_id][key] = value
            
        # Update in data list as well
        for i, fact in enumerate(self.data):
            if fact['fact_id'] == fact_id:
                self.data[i].update(kwargs)
                break
                
        return True
    
    def remove_fact(self, fact_id):
        """
        Remove a fact from the knowledge graph.
        
        Args:
            fact_id: The ID of the fact to remove
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.graph.has_node(fact_id):
            return False
            
        # Remove from graph
        self.graph.remove_node(fact_id)
        
        # Remove from data list
        self.data = [fact for fact in self.data if fact['fact_id'] != fact_id]
        
        return True
    
    def save_to_file(self, filename):
        """
        Save the knowledge graph to a JSON file.
        
        Args:
            filename: Path to save the file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(filename, 'w') as file:
                json.dump(self.data, file, default=str, indent=4)
            return True
        except Exception as e:
            print(f"Error saving knowledge graph: {e}")
            return False
    
    def load_from_file(self, filename):
        """
        Load a knowledge graph from a JSON file.
        
        Args:
            filename: Path to the file to load
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(filename, 'r') as file:
                self.data = json.load(file)
                
            # Rebuild graph from data
            self.graph = nx.DiGraph()
            for fact in self.data:
                self.graph.add_node(fact['fact_id'], **fact)
                
                # Add edges for related facts
                for related_fact_id in fact.get('related_facts', []):
                    self.graph.add_edge(fact['fact_id'], related_fact_id, relationship_type="related")
                    
            return True
        except Exception as e:
            print(f"Error loading knowledge graph: {e}")
            return False
    
    def get_all_facts(self):
        """
        Get all facts in the knowledge graph.
        
        Returns:
            list: All facts in the graph
        """
        return self.data
    
    def get_facts_by_category(self, category):
        """
        Get facts by category.
        
        Args:
            category: Category to filter by
            
        Returns:
            list: Facts in the specified category
        """
        return [fact for fact in self.data if fact['category'] == category]
    
    def get_facts_by_tag(self, tag):
        """
        Get facts by tag.
        
        Args:
            tag: Tag to filter by
            
        Returns:
            list: Facts with the specified tag
        """
        return [fact for fact in self.data if tag in fact.get('tags', '')]
    
    def get_facts_by_reliability(self, reliability_rating):
        """
        Get facts by reliability rating.
        
        Args:
            reliability_rating: ReliabilityRating enum or string
            
        Returns:
            list: Facts with the specified reliability rating
        """
        rating_str = reliability_rating.name if isinstance(reliability_rating, ReliabilityRating) else reliability_rating
        return [fact for fact in self.data if fact['reliability_rating'] == rating_str]
