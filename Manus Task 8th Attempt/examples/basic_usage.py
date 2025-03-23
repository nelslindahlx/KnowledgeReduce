#!/usr/bin/env python3
"""
Basic Usage Example for KnowledgeReduce

This script demonstrates the basic functionality of the KnowledgeReduce package,
including creating a knowledge graph, adding facts, retrieving facts, and updating facts.
"""

import sys
import os
from datetime import datetime

# Add the parent directory to the path to import the package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from knowledge_graph_pkg import KnowledgeGraph
from knowledge_graph_pkg.core import ReliabilityRating


def main():
    """
    Demonstrate basic usage of the KnowledgeGraph class.
    """
    print("KnowledgeReduce Basic Usage Example")
    print("===================================\n")

    # Create a new knowledge graph
    print("Creating a new knowledge graph...")
    kg = KnowledgeGraph()
    print("Knowledge graph created successfully.\n")

    # Add facts to the knowledge graph
    print("Adding facts to the knowledge graph...")
    
    # Fact 1: Astronomy fact
    kg.add_fact(
        fact_id="astronomy_001",
        fact_statement="The Earth orbits the Sun",
        category="Astronomy",
        tags=["Earth", "Sun", "orbit"],
        date_recorded=datetime.now(),
        last_updated=datetime.now(),
        reliability_rating=ReliabilityRating.VERIFIED,
        source_id="source_001",
        source_title="Astronomy Textbook",
        author_creator="Dr. Astronomer",
        publication_date=datetime.now(),
        url_reference="https://example.com/astronomy",
        related_facts=[],
        contextual_notes="Basic astronomical fact",
        access_level="public",
        usage_count=10
    )
    print("Added fact: astronomy_001")
    
    # Fact 2: Biology fact
    kg.add_fact(
        fact_id="biology_001",
        fact_statement="DNA is the genetic material in humans",
        category="Biology",
        tags=["DNA", "genetics", "humans"],
        date_recorded=datetime.now(),
        last_updated=datetime.now(),
        reliability_rating=ReliabilityRating.VERIFIED,
        source_id="source_002",
        source_title="Biology Journal",
        author_creator="Dr. Biologist",
        publication_date=datetime.now(),
        url_reference="https://example.com/biology",
        related_facts=[],
        contextual_notes="Fundamental biology concept",
        access_level="public",
        usage_count=8
    )
    print("Added fact: biology_001")
    
    # Fact 3: History fact with lower reliability
    kg.add_fact(
        fact_id="history_001",
        fact_statement="The first human civilization emerged around 10,000 BCE",
        category="History",
        tags=["civilization", "ancient history", "archaeology"],
        date_recorded=datetime.now(),
        last_updated=datetime.now(),
        reliability_rating=ReliabilityRating.LIKELY_TRUE,
        source_id="source_003",
        source_title="History Encyclopedia",
        author_creator="Dr. Historian",
        publication_date=datetime.now(),
        url_reference="https://example.com/history",
        related_facts=[],
        contextual_notes="Date is approximate based on archaeological evidence",
        access_level="public",
        usage_count=5
    )
    print("Added fact: history_001\n")

    # Retrieve facts from the knowledge graph
    print("Retrieving facts from the knowledge graph...")
    
    astronomy_fact = kg.get_fact("astronomy_001")
    print(f"Retrieved fact: {astronomy_fact['fact_statement']}")
    print(f"Category: {astronomy_fact['category']}")
    print(f"Reliability: {astronomy_fact['reliability_rating']}")
    print(f"Quality Score: {astronomy_fact['quality_score']}\n")
    
    biology_fact = kg.get_fact("biology_001")
    print(f"Retrieved fact: {biology_fact['fact_statement']}")
    print(f"Category: {biology_fact['category']}")
    print(f"Reliability: {biology_fact['reliability_rating']}")
    print(f"Quality Score: {biology_fact['quality_score']}\n")
    
    history_fact = kg.get_fact("history_001")
    print(f"Retrieved fact: {history_fact['fact_statement']}")
    print(f"Category: {history_fact['category']}")
    print(f"Reliability: {history_fact['reliability_rating']}")
    print(f"Quality Score: {history_fact['quality_score']}\n")

    # Update a fact in the knowledge graph
    print("Updating a fact in the knowledge graph...")
    
    print(f"Before update - Usage count: {history_fact['usage_count']}, Quality score: {history_fact['quality_score']}")
    
    kg.update_fact("history_001", usage_count=10, reliability_rating=ReliabilityRating.VERIFIED)
    
    updated_history_fact = kg.get_fact("history_001")
    print(f"After update - Usage count: {updated_history_fact['usage_count']}, Quality score: {updated_history_fact['quality_score']}")
    print("Fact updated successfully.\n")

    print("Basic usage example completed successfully.")


if __name__ == "__main__":
    main()
