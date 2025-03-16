"""
Example usage of the KnowledgeReduce framework.
This script demonstrates how to use the framework to create, analyze, and visualize knowledge graphs.
"""
import os
import matplotlib.pyplot as plt
from datetime import datetime
from implementation.framework import KnowledgeReduceFramework
from implementation.core import ReliabilityRating

def main():
    # Create a new KnowledgeReduce framework instance
    kr = KnowledgeReduceFramework()
    
    # Add some facts
    kr.add_fact(
        fact_id="fact1",
        fact_statement="The Earth orbits the Sun",
        category="Astronomy",
        tags=["Earth", "Sun", "orbit"],
        reliability_rating=ReliabilityRating.VERIFIED,
        source_title="Astronomy Textbook",
        author_creator="Dr. Astronomer"
    )
    
    kr.add_fact(
        fact_id="fact2",
        fact_statement="The Moon orbits the Earth",
        category="Astronomy",
        tags=["Moon", "Earth", "orbit"],
        reliability_rating=ReliabilityRating.VERIFIED,
        source_title="Astronomy Textbook",
        author_creator="Dr. Astronomer"
    )
    
    kr.add_fact(
        fact_id="fact3",
        fact_statement="The Earth has one natural satellite",
        category="Astronomy",
        tags=["Earth", "Moon", "satellite"],
        reliability_rating=ReliabilityRating.VERIFIED,
        source_title="Astronomy Facts",
        author_creator="Space Agency"
    )
    
    kr.add_fact(
        fact_id="fact4",
        fact_statement="Jupiter is the largest planet in our solar system",
        category="Astronomy",
        tags=["Jupiter", "planet", "solar system"],
        reliability_rating=ReliabilityRating.VERIFIED,
        source_title="Planetary Science",
        author_creator="Planetary Institute"
    )
    
    kr.add_fact(
        fact_id="fact5",
        fact_statement="Jupiter has 79 known moons",
        category="Astronomy",
        tags=["Jupiter", "moons"],
        reliability_rating=ReliabilityRating.LIKELY_TRUE,
        source_title="Recent Discoveries",
        author_creator="Space Observer"
    )
    
    # Add relationships between facts
    kr.knowledge_graph.add_relationship("fact1", "fact2", "related_to", weight=0.9)
    kr.knowledge_graph.add_relationship("fact2", "fact3", "supports", weight=0.8)
    kr.knowledge_graph.add_relationship("fact4", "fact5", "related_to", weight=0.9)
    
    # Visualize the knowledge graph
    fig = kr.visualize(title="Astronomy Knowledge Graph")
    plt.savefig("astronomy_graph.png")
    plt.close(fig)
    
    # Get statistics about the graph
    stats = kr.get_statistics()
    print("Knowledge Graph Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Find central facts
    central_facts = kr.get_central_facts(method="betweenness")
    print("\nMost Central Facts (Betweenness Centrality):")
    for fact_id, score in central_facts:
        fact = kr.knowledge_graph.get_fact(fact_id)
        print(f"  {fact['fact_statement']} (Score: {score:.4f})")
    
    # Find similar facts
    similar_facts = kr.find_similar_facts("fact2", threshold=0.1)
    print("\nFacts Similar to 'The Moon orbits the Earth':")
    for fact_id, score in similar_facts:
        if fact_id != "fact2":  # Skip the reference fact
            fact = kr.knowledge_graph.get_fact(fact_id)
            print(f"  {fact['fact_statement']} (Similarity: {score:.4f})")
    
    # Use the query interface
    query_results = kr.query().filter_by_category("Astronomy").filter_by_text("Jupiter").execute()
    print("\nFacts about Jupiter:")
    for fact_id, _ in query_results:
        fact = kr.knowledge_graph.get_fact(fact_id)
        print(f"  {fact['fact_statement']}")
    
    # Find facts with relationships
    related = kr.get_related("fact1", max_depth=2)
    print("\nFacts Related to 'The Earth orbits the Sun':")
    for fact_id in related:
        fact = kr.knowledge_graph.get_fact(fact_id)
        print(f"  {fact['fact_statement']}")
    
    # Save the knowledge graph to a file
    kr.save_to_file("astronomy_knowledge.gexf")
    print("\nKnowledge graph saved to 'astronomy_knowledge.gexf'")
    
    # Create a new knowledge graph from text
    text = """
    Mars is the fourth planet from the Sun. Mars is a terrestrial planet with a thin atmosphere.
    Mars has two moons named Phobos and Deimos. Mars is often called the Red Planet.
    """
    
    kr2 = KnowledgeReduceFramework()
    kr2 = kr2.create_from_text(text)
    
    # Merge the two knowledge graphs
    kr.merge_with(kr2)
    
    # Visualize the merged knowledge graph
    fig = kr.visualize(title="Merged Astronomy Knowledge Graph")
    plt.savefig("merged_astronomy_graph.png")
    plt.close(fig)
    
    print("\nMerged knowledge graph saved to 'merged_astronomy_graph.png'")
    
    # Analyze categories
    categories = kr.analyze_categories()
    print("\nCategory Analysis:")
    for category, count in categories.items():
        print(f"  {category}: {count} facts")

if __name__ == "__main__":
    main()
