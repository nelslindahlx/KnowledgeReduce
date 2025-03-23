"""
Core functionality module for the knowledge graph package.

This module contains the core classes and functions for the knowledge graph package,
including the ReliabilityRating enum and KnowledgeGraph class.
"""

from enum import IntEnum
from typing import Dict, List, Any, Union, Optional
from datetime import datetime
import networkx as nx


class ReliabilityRating(IntEnum):
    """Enum representing the reliability rating of a fact in the knowledge graph.
    
    The reliability rating indicates the level of verification and trustworthiness
    of a fact, ranging from UNVERIFIED (lowest) to VERIFIED (highest).
    
    Attributes:
        UNVERIFIED (int): Fact has not been verified from any reliable source.
        POSSIBLY_TRUE (int): Fact has some supporting evidence but is not fully verified.
        LIKELY_TRUE (int): Fact has substantial supporting evidence and is likely accurate.
        VERIFIED (int): Fact has been verified from reliable sources and is considered accurate.
    """
    UNVERIFIED = 1
    POSSIBLY_TRUE = 2
    LIKELY_TRUE = 3
    VERIFIED = 4


class KnowledgeGraph:
    """A class for creating and managing knowledge graphs.
    
    This class provides functionality to create, manage, and query knowledge graphs.
    It uses NetworkX's DiGraph as the underlying data structure to represent
    knowledge as a directed graph where nodes are facts and edges represent
    relationships between facts.
    
    Attributes:
        graph (nx.DiGraph): The directed graph storing the knowledge facts.
    """
    
    def __init__(self) -> None:
        """Initialize a new KnowledgeGraph instance.
        
        Creates an empty directed graph using NetworkX's DiGraph class.
        """
        self.graph = nx.DiGraph()

    def validate_fact_id(self, fact_id: str) -> None:
        """Validate that a fact ID is a non-empty string.
        
        Args:
            fact_id (str): The ID of the fact to validate.
            
        Raises:
            ValueError: If the fact ID is not a non-empty string.
        """
        if not isinstance(fact_id, str) or not fact_id:
            raise ValueError("Fact ID must be a non-empty string.")

    def validate_reliability_rating(self, rating: ReliabilityRating) -> None:
        """Validate that a reliability rating is a valid ReliabilityRating enum value.
        
        Args:
            rating (ReliabilityRating): The reliability rating to validate.
            
        Raises:
            ValueError: If the rating is not a valid ReliabilityRating enum value.
        """
        if not isinstance(rating, ReliabilityRating):
            raise ValueError("Reliability rating must be an instance of ReliabilityRating Enum.")

    def add_fact(self, fact_id: str, fact_statement: str, category: str, 
                tags: List[str], date_recorded: Union[datetime, str], 
                last_updated: Union[datetime, str], reliability_rating: ReliabilityRating, 
                source_id: str, source_title: str, author_creator: str,
                publication_date: Union[datetime, str], url_reference: str, 
                related_facts: List[str], contextual_notes: str,
                access_level: str, usage_count: int) -> None:
        """Add a new fact to the knowledge graph.
        
        This method adds a new fact as a node in the knowledge graph with
        various attributes describing the fact's metadata.
        
        Args:
            fact_id (str): Unique identifier for the fact.
            fact_statement (str): The actual statement or content of the fact.
            category (str): Category or domain the fact belongs to.
            tags (List[str]): List of tags or keywords associated with the fact.
            date_recorded (Union[datetime, str]): Date when the fact was recorded.
            last_updated (Union[datetime, str]): Date when the fact was last updated.
            reliability_rating (ReliabilityRating): Rating indicating the reliability of the fact.
            source_id (str): Identifier for the source of the fact.
            source_title (str): Title of the source document or reference.
            author_creator (str): Name of the author or creator of the fact.
            publication_date (Union[datetime, str]): Date when the source was published.
            url_reference (str): URL reference to the source.
            related_facts (List[str]): List of related fact IDs.
            contextual_notes (str): Additional notes or context for the fact.
            access_level (str): Access level or permissions for the fact.
            usage_count (int): Number of times the fact has been accessed or used.
            
        Raises:
            ValueError: If the fact ID or reliability rating is invalid.
            Exception: If there is an error adding the fact to the graph.
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
            
            # Calculate quality score based on reliability rating and usage count
            quality_score = usage_count * reliability_rating.value + 2 * usage_count

            # Adding fact to the graph
            self.graph.add_node(fact_id, fact_statement=fact_statement, category=category,
                               tags=tags_str, date_recorded=date_recorded_str, last_updated=last_updated_str,
                               reliability_rating=reliability_rating, source_id=source_id, source_title=source_title,
                               author_creator=author_creator, publication_date=publication_date_str,
                               url_reference=url_reference, related_facts=related_facts, contextual_notes=contextual_notes,
                               access_level=access_level, usage_count=usage_count, quality_score=quality_score)
        except Exception as e:
            raise Exception(f"Error adding fact: {e}")

    def get_fact(self, fact_id: str) -> Dict[str, Any]:
        """Retrieve a fact from the knowledge graph.
        
        Args:
            fact_id (str): The ID of the fact to retrieve.
            
        Returns:
            Dict[str, Any]: A dictionary containing the fact's attributes.
            
        Raises:
            ValueError: If the fact ID is invalid or not found in the graph.
        """
        self.validate_fact_id(fact_id)
        if fact_id not in self.graph:
            raise ValueError(f"Fact ID '{fact_id}' not found in the graph.")
        return self.graph.nodes[fact_id]

    def update_fact(self, fact_id: str, **kwargs) -> None:
        """Update attributes of an existing fact in the knowledge graph.
        
        Args:
            fact_id (str): The ID of the fact to update.
            **kwargs: Keyword arguments representing the attributes to update.
            
        Raises:
            ValueError: If the fact ID is invalid, not found, or if an invalid attribute is specified.
        """
        self.validate_fact_id(fact_id)
        if fact_id not in self.graph:
            raise ValueError(f"Fact ID '{fact_id}' not found in the graph.")
        
        for key, value in kwargs.items():
            if key in self.graph.nodes[fact_id]:
                self.graph.nodes[fact_id][key] = value
                
                # Update quality score if reliability_rating or usage_count is updated
                if key in ['reliability_rating', 'usage_count']:
                    reliability_rating = self.graph.nodes[fact_id]['reliability_rating']
                    usage_count = self.graph.nodes[fact_id]['usage_count']
                    self.graph.nodes[fact_id]['quality_score'] = usage_count * reliability_rating.value + 2 * usage_count
            else:
                raise ValueError(f"Invalid attribute '{key}' for fact update.")
