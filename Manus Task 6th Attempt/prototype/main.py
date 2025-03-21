"""
Main entry point for the KnowledgeReduce prototype.

This script demonstrates the complete workflow of the KnowledgeReduce framework:
1. Data ingestion
2. Knowledge mapping
3. Knowledge reduction
4. Graph storage
5. Query and analysis
"""

import os
import sys
import json
import pandas as pd
import networkx as nx
from typing import Dict, List, Any

from src.data_ingestion import DataIngestionPipeline, create_sample_data
from src.knowledge_mapping import KnowledgeMapper
from src.knowledge_reduction import KnowledgeReducer
from src.graph_store import GraphStoreFactory
from src.query_interface import GraphQuery, KnowledgeAnalyzer
import src.config as config


def setup_environment():
    """Set up the environment for the prototype."""
    print("Setting up environment...")
    
    # Create data directory if it doesn't exist
    os.makedirs(os.path.dirname(config.ENTITIES_FILE), exist_ok=True)
    
    # Create sample data if it doesn't exist
    if not os.path.exists(config.ENTITIES_FILE) or not os.path.exists(config.RELATIONSHIPS_FILE):
        print("Creating sample data...")
        create_sample_data()
    
    print("Environment setup complete.")


def run_knowledge_reduce_pipeline():
    """Run the complete KnowledgeReduce pipeline."""
    print("\n=== KnowledgeReduce Pipeline ===\n")
    
    # Step 1: Data Ingestion
    print("Step 1: Data Ingestion")
    pipeline = DataIngestionPipeline()
    entities_df, relationships_df = pipeline.ingest()
    print(f"Loaded {len(entities_df)} entities and {len(relationships_df)} relationships")
    
    # Display sample data
    print("\nSample entities:")
    print(entities_df.head(3))
    print("\nSample relationships:")
    print(relationships_df.head(3))
    
    # Step 2: Knowledge Mapping
    print("\nStep 2: Knowledge Mapping")
    mapper = KnowledgeMapper()
    entities, relationships = mapper.map(entities_df, relationships_df)
    print(f"Mapped {len(entities)} entities and {len(relationships)} relationships")
    
    # Display sample mapped data
    print("\nSample mapped entities:")
    for entity in entities[:3]:
        print(f"  {entity['name']} ({entity['type']})")
    
    print("\nSample mapped relationships:")
    for rel in relationships[:3]:
        print(f"  {rel['source_id']} --[{rel['type']}]--> {rel['target_id']}")
    
    # Step 3: Knowledge Reduction
    print("\nStep 3: Knowledge Reduction")
    reducer = KnowledgeReducer()
    resolved_entities, aggregated_relationships, knowledge_graph = reducer.reduce(entities, relationships)
    print(f"Reduced {len(entities)} entities to {len(resolved_entities)} entities")
    print(f"Reduced {len(relationships)} relationships to {len(aggregated_relationships)} relationships")
    
    # Display sample reduced data
    print("\nSample resolved entities:")
    for entity in resolved_entities[:3]:
        print(f"  {entity['name']} ({entity['type']})")
    
    print("\nSample aggregated relationships:")
    for rel in aggregated_relationships[:3]:
        print(f"  {rel['source_id']} --[{rel['type']}]--> {rel['target_id']}")
    
    # Step 4: Graph Storage
    print("\nStep 4: Graph Storage")
    graph_store = GraphStoreFactory.create_store("memory")
    graph_store.store_graph(knowledge_graph)
    print(f"Stored knowledge graph with {knowledge_graph.number_of_nodes()} nodes and {knowledge_graph.number_of_edges()} edges")
    
    # Export graph to JSON
    export_path = "data/knowledge_graph.json"
    graph_store.export_to_json(export_path)
    print(f"Exported knowledge graph to {export_path}")
    
    # Step 5: Query and Analysis
    print("\nStep 5: Query and Analysis")
    query = GraphQuery(graph_store)
    analyzer = KnowledgeAnalyzer(graph_store)
    
    # Perform sample queries
    print("\nEntities by type:")
    for entity_type in set(entity['type'] for entity in resolved_entities):
        entities_of_type = query.get_entities_by_type(entity_type)
        print(f"  {entity_type}: {len(entities_of_type)} entities")
    
    # Find central entities
    print("\nMost central entities:")
    central_entities = analyzer.get_central_entities(5)
    for entity in central_entities:
        print(f"  {entity['name']} (centrality: {entity['centrality']:.3f})")
    
    # Generate summary
    print("\nKnowledge Graph Summary:")
    summary = analyzer.generate_summary()
    print(f"  Total entities: {summary['entity_statistics']['total_entities']}")
    print(f"  Total relationships: {summary['relationship_statistics']['total_relationships']}")
    print(f"  Entity types: {summary['entity_statistics']['entity_types']}")
    print(f"  Relationship types: {summary['relationship_statistics']['relationship_types']}")
    
    return {
        "entities": resolved_entities,
        "relationships": aggregated_relationships,
        "graph": knowledge_graph,
        "summary": summary
    }


def demonstrate_knowledge_stacking():
    """Demonstrate the concept of stackable knowledge."""
    print("\n=== Knowledge Stacking Demonstration ===\n")
    
    # Load the knowledge graph
    graph_store = GraphStoreFactory.create_store("memory")
    try:
        graph_store.import_from_json("data/knowledge_graph.json")
        graph = graph_store.get_graph()
    except:
        print("Knowledge graph not found. Please run the pipeline first.")
        return
    
    # Create knowledge layers
    layers = config.KNOWLEDGE_LAYERS
    print(f"Creating {len(layers)} knowledge layers: {', '.join(layers)}")
    
    # Assign entities to layers
    for node_id, data in graph.nodes(data=True):
        # Assign layer based on entity type
        if data.get("type") == "Concept":
            # Concepts go to the Abstract layer
            graph.nodes[node_id]["layer"] = "Abstract"
        elif data.get("type") in ["Person", "Organization"]:
            # People and organizations go to the Processed layer
            graph.nodes[node_id]["layer"] = "Processed"
        else:
            # Everything else goes to the Raw layer
            graph.nodes[node_id]["layer"] = "Raw"
    
    # Count entities by layer
    layer_counts = {}
    for layer in layers:
        count = sum(1 for _, data in graph.nodes(data=True) if data.get("layer") == layer)
        layer_counts[layer] = count
    
    print("\nEntities by layer:")
    for layer, count in layer_counts.items():
        print(f"  {layer}: {count} entities")
    
    # Create layer relationships
    print("\nCreating layer relationships...")
    for layer_idx in range(len(layers) - 1):
        lower_layer = layers[layer_idx]
        upper_layer = layers[layer_idx + 1]
        
        print(f"  {lower_layer} -> {upper_layer}")
    
    # Demonstrate cross-layer query
    print("\nDemonstrating cross-layer query:")
    query = GraphQuery(graph_store)
    
    # Find concepts (Abstract layer) related to people (Processed layer)
    print("  Concepts related to people:")
    
    # Get all people
    people = query.get_entities_by_type("Person")
    
    # For each person, find related concepts
    for person in people:
        neighbors = query.get_neighbors(person["id"])
        concepts = [n for n in neighbors if n.get("type") == "Concept"]
        
        if concepts:
            print(f"  {person['name']} is related to concepts:")
            for concept in concepts:
                print(f"    - {concept['name']}")
    
    print("\nKnowledge stacking demonstration complete.")


def run_interactive_query():
    """Run an interactive query session."""
    print("\n=== Interactive Query Session ===\n")
    
    # Load the knowledge graph
    graph_store = GraphStoreFactory.create_store("memory")
    try:
        graph_store.import_from_json("data/knowledge_graph.json")
    except:
        print("Knowledge graph not found. Please run the pipeline first.")
        return
    
    query = GraphQuery(graph_store)
    
    print("Available query types:")
    print("1. Get entities by type")
    print("2. Find entity by name")
    print("3. Get entity neighbors")
    print("4. Find paths between entities")
    print("5. Exit")
    
    while True:
        try:
            choice = input("\nEnter query type (1-5): ")
            
            if choice == "1":
                entity_type = input("Enter entity type (e.g., Person, Organization, Concept): ")
                entities = query.get_entities_by_type(entity_type)
                print(f"\nFound {len(entities)} entities of type '{entity_type}':")
                for entity in entities:
                    print(f"  {entity['name']} ({entity['id']})")
            
            elif choice == "2":
                name = input("Enter entity name: ")
                entity = query.get_entity_by_name(name)
                if entity:
                    print(f"\nFound entity: {entity['name']} ({entity['type']})")
                    if "description" in entity:
                        print(f"  Description: {entity['description']}")
                else:
                    print(f"\nNo entity found with name '{name}'")
            
            elif choice == "3":
                name = input("Enter entity name: ")
                entity = query.get_entity_by_name(name)
                if entity:
                    neighbors = query.get_neighbors(entity['id'])
                    print(f"\nNeighbors of {entity['name']}:")
                    for neighbor in neighbors:
                        print(f"  {neighbor['name']} ({neighbor['type']})")
                else:
                    print(f"\nNo entity found with name '{name}'")
            
            elif choice == "4":
                source_name = input("Enter source entity name: ")
                target_name = input("Enter target entity name: ")
                
                source = query.get_entity_by_name(source_name)
                target = query.get_entity_by_name(target_name)
                
                if not source or not target:
                    print("\nOne or both entities not found")
                    continue
                
                paths = query.find_paths(source['id'], target['id'])
                
                if paths:
                    print(f"\nFound {len(paths)} paths from {source['name']} to {target['name']}:")
                    for i, path in enumerate(paths):
                        path_str = " -> ".join(node['name'] for node in path)
                        print(f"  Path {i+1}: {path_str}")
                else:
                    print(f"\nNo paths found from {source['name']} to {target['name']}")
            
            elif choice == "5":
                print("\nExiting interactive query session.")
                break
            
            else:
                print("\nInvalid choice. Please enter a number between 1 and 5.")
        
        except Exception as e:
            print(f"\nError: {e}")


def main():
    """Main function to run the KnowledgeReduce prototype."""
    print("KnowledgeReduce Prototype")
    print("========================\n")
    
    # Setup environment
    setup_environment()
    
    # Run the pipeline
    results = run_knowledge_reduce_pipeline()
    
    # Demonstrate knowledge stacking
    demonstrate_knowledge_stacking()
    
    # Run interactive query session if in interactive mode
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        run_interactive_query()
    
    print("\nKnowledgeReduce prototype demonstration complete.")


if __name__ == "__main__":
    main()
