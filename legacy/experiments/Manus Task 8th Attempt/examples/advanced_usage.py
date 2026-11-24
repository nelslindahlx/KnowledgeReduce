#!/usr/bin/env python3
"""
Advanced Usage Example for KnowledgeReduce

This script demonstrates advanced functionality of the KnowledgeReduce package,
including creating relationships between facts and working with multiple facts.
"""

import sys
import os
from datetime import datetime

# Add the parent directory to the path to import the package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from knowledge_graph_pkg import KnowledgeGraph
from knowledge_graph_pkg.core import ReliabilityRating
import networkx as nx


def main():
    """
    Demonstrate advanced usage of the KnowledgeGraph class.
    """
    print("KnowledgeReduce Advanced Usage Example")
    print("=====================================\n")

    # Create a new knowledge graph
    print("Creating a new knowledge graph...")
    kg = KnowledgeGraph()
    print("Knowledge graph created successfully.\n")

    # Add multiple related facts to the knowledge graph
    print("Adding a network of related facts to the knowledge graph...")
    
    # Solar System Facts
    kg.add_fact(
        fact_id="solar_system_001",
        fact_statement="The Solar System consists of the Sun and objects that orbit it",
        category="Astronomy",
        tags=["Solar System", "Sun", "planets"],
        date_recorded=datetime.now(),
        last_updated=datetime.now(),
        reliability_rating=ReliabilityRating.VERIFIED,
        source_id="source_001",
        source_title="NASA Solar System Guide",
        author_creator="NASA",
        publication_date=datetime.now(),
        url_reference="https://example.com/nasa/solar-system",
        related_facts=[],
        contextual_notes="Overview of the Solar System",
        access_level="public",
        usage_count=15
    )
    print("Added fact: solar_system_001")
    
    kg.add_fact(
        fact_id="planet_earth_001",
        fact_statement="Earth is the third planet from the Sun",
        category="Astronomy",
        tags=["Earth", "planet", "Solar System"],
        date_recorded=datetime.now(),
        last_updated=datetime.now(),
        reliability_rating=ReliabilityRating.VERIFIED,
        source_id="source_001",
        source_title="NASA Solar System Guide",
        author_creator="NASA",
        publication_date=datetime.now(),
        url_reference="https://example.com/nasa/earth",
        related_facts=["solar_system_001"],
        contextual_notes="Earth's position in the Solar System",
        access_level="public",
        usage_count=12
    )
    print("Added fact: planet_earth_001")
    
    kg.add_fact(
        fact_id="planet_mars_001",
        fact_statement="Mars is the fourth planet from the Sun",
        category="Astronomy",
        tags=["Mars", "planet", "Solar System"],
        date_recorded=datetime.now(),
        last_updated=datetime.now(),
        reliability_rating=ReliabilityRating.VERIFIED,
        source_id="source_001",
        source_title="NASA Solar System Guide",
        author_creator="NASA",
        publication_date=datetime.now(),
        url_reference="https://example.com/nasa/mars",
        related_facts=["solar_system_001"],
        contextual_notes="Mars' position in the Solar System",
        access_level="public",
        usage_count=10
    )
    print("Added fact: planet_mars_001")
    
    kg.add_fact(
        fact_id="earth_moon_001",
        fact_statement="The Moon is Earth's only natural satellite",
        category="Astronomy",
        tags=["Moon", "Earth", "satellite"],
        date_recorded=datetime.now(),
        last_updated=datetime.now(),
        reliability_rating=ReliabilityRating.VERIFIED,
        source_id="source_001",
        source_title="NASA Solar System Guide",
        author_creator="NASA",
        publication_date=datetime.now(),
        url_reference="https://example.com/nasa/moon",
        related_facts=["planet_earth_001"],
        contextual_notes="Relationship between Earth and Moon",
        access_level="public",
        usage_count=8
    )
    print("Added fact: earth_moon_001")
    
    kg.add_fact(
        fact_id="mars_moons_001",
        fact_statement="Mars has two moons: Phobos and Deimos",
        category="Astronomy",
        tags=["Mars", "Phobos", "Deimos", "moons"],
        date_recorded=datetime.now(),
        last_updated=datetime.now(),
        reliability_rating=ReliabilityRating.VERIFIED,
        source_id="source_001",
        source_title="NASA Solar System Guide",
        author_creator="NASA",
        publication_date=datetime.now(),
        url_reference="https://example.com/nasa/mars-moons",
        related_facts=["planet_mars_001"],
        contextual_notes="Mars' natural satellites",
        access_level="public",
        usage_count=6
    )
    print("Added fact: mars_moons_001\n")

    # Create relationships between facts using NetworkX
    print("Creating relationships between facts...")
    
    # Add edges to represent relationships between facts
    kg.graph.add_edge("solar_system_001", "planet_earth_001", relationship="contains")
    kg.graph.add_edge("solar_system_001", "planet_mars_001", relationship="contains")
    kg.graph.add_edge("planet_earth_001", "earth_moon_001", relationship="has_satellite")
    kg.graph.add_edge("planet_mars_001", "mars_moons_001", relationship="has_satellites")
    
    print("Relationships created successfully.\n")

    # Analyze the knowledge graph
    print("Analyzing the knowledge graph...")
    
    # Get basic graph statistics
    num_facts = len(kg.graph.nodes)
    num_relationships = len(kg.graph.edges)
    
    print(f"Number of facts in the knowledge graph: {num_facts}")
    print(f"Number of relationships between facts: {num_relationships}")
    
    # Find all facts related to Mars
    mars_related_facts = [node for node in kg.graph.nodes if "Mars" in kg.graph.nodes[node].get('tags', '')]
    print(f"\nFacts related to Mars: {mars_related_facts}")
    
    # Find all facts with VERIFIED reliability rating
    verified_facts = [node for node in kg.graph.nodes 
                     if kg.graph.nodes[node].get('reliability_rating') == ReliabilityRating.VERIFIED]
    print(f"Number of verified facts: {len(verified_facts)}")
    
    # Find facts with highest quality scores
    quality_scores = [(node, kg.graph.nodes[node].get('quality_score', 0)) for node in kg.graph.nodes]
    quality_scores.sort(key=lambda x: x[1], reverse=True)
    
    print("\nFacts ranked by quality score:")
    for fact_id, score in quality_scores:
        print(f"  - {fact_id}: {score} ({kg.graph.nodes[fact_id]['fact_statement']})")
    
    # Find connected components
    print("\nConnected components in the knowledge graph:")
    for i, component in enumerate(nx.weakly_connected_components(kg.graph)):
        print(f"  Component {i+1}: {component}")
    
    print("\nAdvanced usage example completed successfully.")


if __name__ == "__main__":
    main()
