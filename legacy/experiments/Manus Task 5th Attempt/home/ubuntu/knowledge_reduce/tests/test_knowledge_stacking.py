#!/usr/bin/env python3
"""
Test script for the knowledge stacking algorithm of KnowledgeReduce
"""

import os
import json
import sys
import networkx as nx
from knowledge_reduce.knowledge_stacking import KnowledgeStacker

def main():
    """
    Main function to test the knowledge stacking algorithm
    """
    # Define input and output paths
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output')
    
    # Input fact file
    facts_file = os.path.join(output_dir, 'tech_companies_facts.json')
    
    # Check if facts file exists
    if not os.path.exists(facts_file):
        print(f"Error: Facts file {facts_file} not found.")
        print("Please run the fact extraction test first.")
        return
    
    print(f"Loading facts from {facts_file}...")
    
    # Create a duplicate of the facts file to simulate multiple sources
    facts_file2 = os.path.join(output_dir, 'tech_companies_facts_copy.json')
    
    # Read the original facts
    with open(facts_file, 'r', encoding='utf-8') as f:
        facts = json.load(f)
    
    # Modify some data to create conflicts for testing
    for edge in facts['edges']:
        if edge['type'] == 'release':
            edge['type'] = 'launched'  # Create a conflict
    
    # Save the modified facts
    with open(facts_file2, 'w', encoding='utf-8') as f:
        json.dump(facts, f, indent=2)
    
    print(f"Created modified facts file {facts_file2} for testing conflicts")
    
    # Create knowledge stacker with trust scores
    trust_scores = {
        facts_file: 0.8,  # Higher trust for original source
        facts_file2: 0.5  # Lower trust for modified source
    }
    knowledge_stacker = KnowledgeStacker(trust_scores)
    
    # Stack knowledge from the two fact files
    print("Stacking knowledge from multiple sources...")
    knowledge_graph = knowledge_stacker.stack_knowledge_from_files([facts_file, facts_file2])
    
    # Print graph information
    print(f"\nKnowledge graph has {knowledge_graph.number_of_nodes()} nodes and {knowledge_graph.number_of_edges()} edges")
    
    # Export the stacked knowledge graph
    stacked_graph_file = os.path.join(output_dir, 'stacked_knowledge_graph.json')
    knowledge_stacker.export_graph(stacked_graph_file)
    print(f"Stacked knowledge graph saved to {stacked_graph_file}")
    
    # Print some statistics about the graph
    print("\nTop entities by mentions:")
    top_entities = sorted(
        [(node, data.get('mentions', 0)) for node, data in knowledge_graph.nodes(data=True)],
        key=lambda x: x[1],
        reverse=True
    )[:5]
    
    for entity, mentions in top_entities:
        node_data = knowledge_graph.nodes[entity]
        print(f"  - {node_data.get('text', entity)}: {mentions} mentions")
    
    print("\nRelationship types:")
    edge_types = {}
    for _, _, data in knowledge_graph.edges(data=True):
        edge_type = data.get('type', 'unknown')
        edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
    
    for edge_type, count in edge_types.items():
        print(f"  - {edge_type}: {count} edges")

if __name__ == "__main__":
    main()
