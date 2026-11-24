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

            # Adding fact to the graph
            self.graph.add_node(fact_id, fact_statement=fact_statement, category=category,
                                tags=tags_str, date_recorded=date_recorded_str, last_updated=last_updated_str,
                                reliability_rating=reliability_rating, source_id=source_id, source_title=source_title,
                                author_creator=author_creator, publication_date=publication_date_str,
                                url_reference=url_reference, related_facts=related_facts, contextual_notes=contextual_notes,
                                access_level=access_level, usage_count=usage_count)
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
        except Exception as e:
            raise Exception(f"Error updating fact: {e}")