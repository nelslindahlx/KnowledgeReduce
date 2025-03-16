"""
Core functionality of the knowledge graph package.
This module provides the basic knowledge schema and features for creating and managing knowledge graphs.
"""

import networkx as nx
from datetime import datetime
from enum import Enum
import json
import os
import math

class ReliabilityRating(Enum):
    """
    Enum for classifying the reliability of information in the knowledge graph.
    
    Attributes:
        UNVERIFIED (1): Information that has not been verified
        POSSIBLY_TRUE (2): Information that is possibly true but requires further verification
        LIKELY_TRUE (3): Information that is likely true based on reliable sources
        VERIFIED (4): Information that has been verified from multiple reliable sources
    """
    UNVERIFIED = 1
    POSSIBLY_TRUE = 2
    LIKELY_TRUE = 3
    VERIFIED = 4

class KnowledgeGraph:
    """
    Main class for creating and managing knowledge graphs.
    
    This class provides methods for adding, updating, and retrieving facts,
    managing relationships between facts, and calculating quality scores.
    """
    def __init__(self):
        """Initialize a new knowledge graph."""
        self.graph = nx.DiGraph()
    
    def validate_fact_id(self, fact_id):
        """
        Validate that a fact ID is a non-empty string.
        
        Args:
            fact_id (str): The fact ID to validate
            
        Raises:
            ValueError: If fact_id is not a non-empty string
        """
        if not isinstance(fact_id, str) or not fact_id:
            raise ValueError("Fact ID must be a non-empty string.")
    
    def validate_reliability_rating(self, rating):
        """
        Validate that a reliability rating is a valid ReliabilityRating enum.
        
        Args:
            rating (ReliabilityRating): The reliability rating to validate
            
        Raises:
            ValueError: If rating is not a ReliabilityRating enum
        """
        if not isinstance(rating, ReliabilityRating):
            raise ValueError("Reliability rating must be an instance of ReliabilityRating Enum.")
    
    def calculate_quality_score(self, reliability_rating, usage_count, related_facts_count=0, source_quality=0):
        """
        Calculate the quality score of a fact based on multiple factors.
        
        Args:
            reliability_rating (ReliabilityRating): The reliability rating of the fact
            usage_count (int): How many times the fact has been used or referenced
            related_facts_count (int, optional): Number of related facts. Defaults to 0.
            source_quality (int, optional): Quality score of the source (0-10). Defaults to 0.
            
        Returns:
            int: The calculated quality score
        """
        # Base score from reliability rating (10-40 points)
        base_score = reliability_rating.value * 10
        
        # Additional score from usage (2 points per usage, max 20)
        usage_score = min(2 * usage_count, 20)
        
        # Additional score from related facts (1 point per related fact, max 15)
        related_score = min(related_facts_count, 15)
        
        # Additional score from source quality (0-10 points)
        source_score = source_quality
        
        # Calculate total score
        total_score = base_score + usage_score + related_score + source_score
        
        return total_score
    
    def add_fact(self, fact_id, fact_statement, category, tags, date_recorded, last_updated,
                 reliability_rating, source_id, source_title, author_creator,
                 publication_date, url_reference, related_facts, contextual_notes,
                 access_level, usage_count, source_quality=0):
        """
        Add a fact to the knowledge graph.
        
        Args:
            fact_id (str): Unique identifier for the fact
            fact_statement (str): The fact statement
            category (str): Category of the fact
            tags (list): List of tags
            date_recorded (datetime or str): When the fact was recorded
            last_updated (datetime or str): When the fact was last updated
            reliability_rating (ReliabilityRating): Reliability rating
            source_id (str): ID of the source
            source_title (str): Title of the source
            author_creator (str): Author or creator of the fact
            publication_date (datetime or str): Publication date
            url_reference (str): URL reference
            related_facts (list): List of related fact IDs
            contextual_notes (str): Contextual notes
            access_level (str): Access level
            usage_count (int): Usage count
            source_quality (int, optional): Quality score of the source (0-10). Defaults to 0.
            
        Raises:
            ValueError: If validation fails
            Exception: If there's an error adding the fact
        """
        self.validate_fact_id(fact_id)
        self.validate_reliability_rating(reliability_rating)
        # Additional validations for other parameters can be added here
        
        try:
            # Conversion of list and datetime objects to strings for storage
            tags_str = ', '.join(tags) if tags else ''
            date_recorded_str = date_recorded.isoformat() if isinstance(date_recorded, datetime) else date_recorded
            last_updated_str = last_updated.isoformat() if isinstance(last_updated, datetime) else last_updated
            publication_date_str = publication_date.isoformat() if isinstance(publication_date, datetime) else publication_date
            
            # Calculate related facts count
            related_facts_count = len(related_facts) if related_facts else 0
            
            # Calculate quality score
            quality_score = self.calculate_quality_score(
                reliability_rating, 
                usage_count, 
                related_facts_count, 
                source_quality
            )
            
            # Adding fact to the graph
            self.graph.add_node(fact_id, fact_statement=fact_statement, category=category,
                                tags=tags_str, date_recorded=date_recorded_str, last_updated=last_updated_str,
                                reliability_rating=reliability_rating, source_id=source_id, source_title=source_title,
                                author_creator=author_creator, publication_date=publication_date_str,
                                url_reference=url_reference, related_facts=related_facts, contextual_notes=contextual_notes,
                                access_level=access_level, usage_count=usage_count, quality_score=quality_score,
                                source_quality=source_quality)
            
            # Add relationships to related facts
            if related_facts:
                for related_id in related_facts:
                    if related_id in self.graph:
                        self.add_relationship(fact_id, related_id, "related_to")
        except Exception as e:
            raise Exception(f"Error adding fact: {e}")
    
    def get_fact(self, fact_id):
        """
        Get a fact from the knowledge graph.
        
        Args:
            fact_id (str): ID of the fact to retrieve
            
        Returns:
            dict: Fact data
            
        Raises:
            ValueError: If fact_id is not found in the graph
        """
        self.validate_fact_id(fact_id)
        if fact_id not in self.graph:
            raise ValueError(f"Fact ID '{fact_id}' not found in the graph.")
        return self.graph.nodes[fact_id]
    
    def update_fact(self, fact_id, **kwargs):
        """
        Update a fact in the knowledge graph.
        
        Args:
            fact_id (str): ID of the fact to update
            **kwargs: Attributes to update
            
        Raises:
            ValueError: If fact_id is not found or attribute is invalid
            Exception: If there's an error updating the fact
        """
        self.validate_fact_id(fact_id)
        if fact_id not in self.graph:
            raise ValueError(f"Fact ID '{fact_id}' not found in the graph.")
        
        try:
            for key, value in kwargs.items():
                if key in self.graph.nodes[fact_id]:
                    self.graph.nodes[fact_id][key] = value
                else:
                    raise ValueError(f"Invalid attribute '{key}' for fact update.")
            
            # If reliability_rating, usage_count, or related_facts was updated, recalculate quality_score
            if any(key in kwargs for key in ['reliability_rating', 'usage_count', 'related_facts', 'source_quality']):
                reliability_rating = self.graph.nodes[fact_id]['reliability_rating']
                usage_count = self.graph.nodes[fact_id]['usage_count']
                related_facts = self.graph.nodes[fact_id].get('related_facts', [])
                related_facts_count = len(related_facts) if related_facts else 0
                source_quality = self.graph.nodes[fact_id].get('source_quality', 0)
                
                self.graph.nodes[fact_id]['quality_score'] = self.calculate_quality_score(
                    reliability_rating, 
                    usage_count, 
                    related_facts_count, 
                    source_quality
                )
                
        except Exception as e:
            raise Exception(f"Error updating fact: {e}")
    
    def add_relationship(self, source_fact_id, target_fact_id, relationship_type, weight=1.0, attributes=None):
        """
        Add a relationship (edge) between two facts in the knowledge graph.
        
        Args:
            source_fact_id (str): ID of the source fact
            target_fact_id (str): ID of the target fact
            relationship_type (str): Type of relationship between the facts
            weight (float, optional): Weight of the relationship. Defaults to 1.0.
            attributes (dict, optional): Additional attributes for the relationship. Defaults to None.
        
        Raises:
            ValueError: If either fact ID is not found in the graph
        """
        self.validate_fact_id(source_fact_id)
        self.validate_fact_id(target_fact_id)
        
        if source_fact_id not in self.graph:
            raise ValueError(f"Source fact ID '{source_fact_id}' not found in the graph.")
        if target_fact_id not in self.graph:
            raise ValueError(f"Target fact ID '{target_fact_id}' not found in the graph.")
        
        # Initialize attributes dictionary if None
        if attributes is None:
            attributes = {}
        
        # Add relationship type and weight to attributes
        attributes['relationship_type'] = relationship_type
        attributes['weight'] = weight
        
        # Add edge to the graph with attributes
        self.graph.add_edge(source_fact_id, target_fact_id, **attributes)
        
        # Update related_facts attribute for both facts
        source_related = self.graph.nodes[source_fact_id].get('related_facts', [])
        if target_fact_id not in source_related:
            if isinstance(source_related, list):
                source_related.append(target_fact_id)
            else:
                source_related = [target_fact_id]
            self.graph.nodes[source_fact_id]['related_facts'] = source_related
            
        target_related = self.graph.nodes[target_fact_id].get('related_facts', [])
        if source_fact_id not in target_related:
            if isinstance(target_related, list):
                target_related.append(source_fact_id)
            else:
                target_related = [source_fact_id]
            self.graph.nodes[target_fact_id]['related_facts'] = target_related
            
        # Recalculate quality scores for both facts
        self.update_fact(source_fact_id)
        self.update_fact(target_fact_id)
    
    def get_relationships(self, fact_id):
        """
        Get all relationships (edges) connected to a fact.
        
        Args:
            fact_id (str): ID of the fact
            
        Returns:
            dict: Dictionary with 'outgoing' and 'incoming' relationships
            
        Raises:
            ValueError: If fact ID is not found in the graph
        """
        self.validate_fact_id(fact_id)
        
        if fact_id not in self.graph:
            raise ValueError(f"Fact ID '{fact_id}' not found in the graph.")
        
        # Get outgoing edges (relationships where this fact is the source)
        outgoing = []
        for target in self.graph.successors(fact_id):
            edge_data = self.graph.get_edge_data(fact_id, target)
            outgoing.append({
                'target_id': target,
                'target_statement': self.graph.nodes[target]['fact_statement'],
                'relationship_type': edge_data.get('relationship_type', 'unknown'),
                'weight': edge_data.get('weight', 1.0),
                'attributes': {k: v for k, v in edge_data.items() if k not in ['relationship_type', 'weight']}
            })
        
        # Get incoming edges (relationships where this fact is the target)
        incoming = []
        for source in self.graph.predecessors(fact_id):
            edge_data = self.graph.get_edge_data(source, fact_id)
            incoming.append({
                'source_id': source,
                'source_statement': self.graph.nodes[source]['fact_statement'],
                'relationship_type': edge_data.get('relationship_type', 'unknown'),
                'weight': edge_data.get('weight', 1.0),
                'attributes': {k: v for k, v in edge_data.items() if k not in ['relationship_type', 'weight']}
            })
        
        return {
            'outgoing': outgoing,
            'incoming': incoming
        }
    
    def export_to_gexf(self, filepath):
        """
        Export the knowledge graph to GEXF format.
        
        Args:
            filepath (str): Path to save the GEXF file
            
        Returns:
            bool: True if export was successful
        """
        try:
            nx.write_gexf(self.graph, filepath)
            return True
        except Exception as e:
            raise Exception(f"Error exporting to GEXF: {e}")
    
    def export_to_graphml(self, filepath):
        """
        Export the knowledge graph to GraphML format.
        
        Args:
            filepath (str): Path to save the GraphML file
            
        Returns:
            bool: True if export was successful
        """
        try:
            nx.write_graphml(self.graph, filepath)
            return True
        except Exception as e:
            raise Exception(f"Error exporting to GraphML: {e}")
    
    def import_from_gexf(self, filepath):
        """
        Import a knowledge graph from a GEXF file.
        
        Args:
            filepath (str): Path to the GEXF file
            
        Returns:
            bool: True if import was successful
        """
        try:
            self.graph = nx.read_gexf(filepath)
            return True
        except Exception as e:
            raise Exception(f"Error importing from GEXF: {e}")
    
    def import_from_graphml(self, filepath):
        """
        Import a knowledge graph from a GraphML file.
        
        Args:
            filepath (str): Path to the GraphML file
            
        Returns:
            bool: True if import was successful
        """
        try:
            self.graph = nx.read_graphml(filepath)
            return True
        except Exception as e:
            raise Exception(f"Error importing from GraphML: {e}")
    
    def search_facts(self, query, fields=None):
        """
        Search for facts in the knowledge graph based on a query string.
        
        Args:
            query (str): The search que<response clipped><NOTE>To save on context only part of this file has been shown to you. You should retry this tool after you have searched inside the file with `grep -n` in order to find the line numbers of what you are looking for.</NOTE>