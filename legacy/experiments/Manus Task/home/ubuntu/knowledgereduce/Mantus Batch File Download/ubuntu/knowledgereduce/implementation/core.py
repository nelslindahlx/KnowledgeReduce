"""
Core functionality of the knowledge graph package.
This module provides the basic knowledge schema and features for creating and managing knowledge graphs.
"""
import networkx as nx
from datetime import datetime
from enum import Enum

class ReliabilityRating(Enum):
    UNVERIFIED = 1
    POSSIBLY_TRUE = 2
    LIKELY_TRUE = 3
    VERIFIED = 4

class KnowledgeGraph:
    def __init__(self):
        self.graph = nx.DiGraph()
    
    def validate_fact_id(self, fact_id):
        if not isinstance(fact_id, str) or not fact_id:
            raise ValueError("Fact ID must be a non-empty string.")
    
    def validate_reliability_rating(self, rating):
        if not isinstance(rating, ReliabilityRating):
            raise ValueError("Reliability rating must be an instance of ReliabilityRating Enum.")
    
    def calculate_quality_score(self, reliability_rating, usage_count):
        """
        Calculate the quality score of a fact based on its reliability rating and usage count.
        
        Args:
            reliability_rating (ReliabilityRating): The reliability rating of the fact
            usage_count (int): How many times the fact has been used or referenced
            
        Returns:
            int: The calculated quality score
        """
        # Base score from reliability rating
        base_score = reliability_rating.value * 10
        
        # Additional score from usage (2 points per usage)
        usage_score = 2 * usage_count
        
        return base_score + usage_score
    
    def add_fact(self, fact_id, fact_statement, category, tags, date_recorded, last_updated,
                 reliability_rating, source_id, source_title, author_creator,
                 publication_date, url_reference, related_facts, contextual_notes,
                 access_level, usage_count):
        self.validate_fact_id(fact_id)
        self.validate_reliability_rating(reliability_rating)
        # Additional validations for other parameters can be added here
        
        try:
            # Conversion of list and datetime objects to strings for storage
            tags_str = ', '.join(tags) if tags else ''
            date_recorded_str = date_recorded.isoformat() if isinstance(date_recorded, datetime) else date_recorded
            last_updated_str = last_updated.isoformat() if isinstance(last_updated, datetime) else last_updated
            publication_date_str = publication_date.isoformat() if isinstance(publication_date, datetime) else publication_date
            
            # Calculate quality score
            quality_score = self.calculate_quality_score(reliability_rating, usage_count)
            
            # Adding fact to the graph
            self.graph.add_node(fact_id, fact_statement=fact_statement, category=category,
                                tags=tags_str, date_recorded=date_recorded_str, last_updated=last_updated_str,
                                reliability_rating=reliability_rating, source_id=source_id, source_title=source_title,
                                author_creator=author_creator, publication_date=publication_date_str,
                                url_reference=url_reference, related_facts=related_facts, contextual_notes=contextual_notes,
                                access_level=access_level, usage_count=usage_count, quality_score=quality_score)
        except Exception as e:
            raise Exception(f"Error adding fact: {e}")
    
    def get_fact(self, fact_id):
        self.validate_fact_id(fact_id)
        if fact_id not in self.graph:
            raise ValueError(f"Fact ID '{fact_id}' not found in the graph.")
        return self.graph.nodes[fact_id]
    
    def update_fact(self, fact_id, **kwargs):
        self.validate_fact_id(fact_id)
        if fact_id not in self.graph:
            raise ValueError(f"Fact ID '{fact_id}' not found in the graph.")
        
        try:
            for key, value in kwargs.items():
                if key in self.graph.nodes[fact_id]:
                    self.graph.nodes[fact_id][key] = value
                else:
                    raise ValueError(f"Invalid attribute '{key}' for fact update.")
            
            # If reliability_rating or usage_count was updated, recalculate quality_score
            if 'reliability_rating' in kwargs or 'usage_count' in kwargs:
                reliability_rating = self.graph.nodes[fact_id]['reliability_rating']
                usage_count = self.graph.nodes[fact_id]['usage_count']
                self.graph.nodes[fact_id]['quality_score'] = self.calculate_quality_score(reliability_rating, usage_count)
                
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
            query (str): The search query
            fields (list, optional): List of fields to search in. If None, searches in fact_statement only.
            
        Returns:
            list: List of fact IDs that match the query
        """
        if fields is None:
            fields = ['fact_statement']
        
        results = []
        
        for node_id, node_data in self.graph.nodes(data=True):
            for field in fields:
                if field in node_data and isinstance(node_data[field], str):
                    if query.lower() in node_data[field].lower():
                        results.append(node_id)
                        break
        
        return results