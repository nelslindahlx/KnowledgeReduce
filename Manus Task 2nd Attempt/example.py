"""
Example usage of the KnowledgeReduce framework.

This script demonstrates how to use the KnowledgeReduce framework to build
a knowledge graph from web sources, clean it, and serialize it.
"""

import os
from knowledge_reduce.graph import ReliabilityRating
from knowledge_reduce.main import (
    create_knowledge_graph,
    build_knowledge_graph_from_urls,
    save_knowledge_graph,
    load_knowledge_graph
)


def main():
    """Run the example."""
    print("KnowledgeReduce Example")
    print("======================\n")
    
    # Define URLs to scrape
    urls = {
        "CivicHonors": "https://civichonors.com/",
        "NelsLindahl": "https://www.nelslindahl.com/"
    }
    
    print(f"Building knowledge graph from {len(urls)} URLs...")
    
    # Build knowledge graph from URLs
    kg, stats = build_knowledge_graph_from_urls(
        urls,
        category="Example",
        tags=["Example", "WebScraped"],
        reliability_rating=ReliabilityRating.LIKELY_TRUE,
        clean=True
    )
    
    # Print statistics
    print("\nKnowledge Graph Statistics:")
    print(f"- Initial facts extracted: {stats['initial_count']}")
    print(f"- Duplicates removed: {stats['duplicates_removed']}")
    print(f"- Short facts removed: {stats['short_removed']}")
    print(f"- Similar facts removed: {stats['similar_removed']}")
    print(f"- Semantically similar facts removed: {stats['semantic_removed']}")
    print(f"- Final fact count: {stats['final_count']}")
    
    # Create output directory if it doesn't exist
    os.makedirs("output", exist_ok=True)
    
    # Save knowledge graph
    output_file = "output/example_knowledge_graph.json"
    success = save_knowledge_graph(kg, output_file)
    
    if success:
        print(f"\nKnowledge graph saved to {output_file}")
    else:
        print("\nFailed to save knowledge graph")
        return
    
    # Load knowledge graph
    loaded_kg = load_knowledge_graph(output_file)
    
    if loaded_kg is not None:
        print(f"\nSuccessfully loaded knowledge graph with {len(loaded_kg.get_all_facts())} facts")
        
        # Print some facts
        facts = loaded_kg.get_all_facts()
        print("\nSample facts:")
        for i, fact in enumerate(facts[:5]):
            print(f"{i+1}. {fact['fact_statement'][:100]}...")
    else:
        print("\nFailed to load knowledge graph")


if __name__ == "__main__":
    main()
