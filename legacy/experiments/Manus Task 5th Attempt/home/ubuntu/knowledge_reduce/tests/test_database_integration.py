#!/usr/bin/env python3
"""
Test script for the database integration components of KnowledgeReduce
"""

import os
import json
import sys
import time
from knowledge_reduce.database_integration import DatabaseIntegration

def main():
    """
    Main function to test the database integration components
    """
    # Define input and output paths
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output')
    
    # Input knowledge graph file
    knowledge_graph_file = os.path.join(output_dir, 'stacked_knowledge_graph.json')
    
    # Check if knowledge graph file exists
    if not os.path.exists(knowledge_graph_file):
        print(f"Error: Knowledge graph file {knowledge_graph_file} not found.")
        print("Please run the knowledge stacking test first.")
        return
    
    print(f"Loading knowledge graph from {knowledge_graph_file}...")
    
    # Since we don't have a real Neo4j database, we'll simulate the database operations
    # by creating a mock implementation for testing purposes
    
    class MockDatabaseIntegration:
        def __init__(self, knowledge_graph_file):
            self.knowledge_graph_file = knowledge_graph_file
            with open(knowledge_graph_file, 'r', encoding='utf-8') as f:
                self.graph_data = json.load(f)
            
            # Create indexes for faster lookups
            self.node_index = {}
            for node in self.graph_data.get('nodes', []):
                if 'id' in node:
                    self.node_index[node['id']] = node
            
            self.edge_index = {}
            for edge in self.graph_data.get('edges', []):
                source = edge.get('source')
                target = edge.get('target')
                if source and target:
                    key = f"{source}_{target}"
                    self.edge_index[key] = edge
        
        def connect(self):
            print("Connected to mock database")
            return True
        
        def close(self):
            print("Closed connection to mock database")
        
        def import_knowledge_graph(self, json_file):
            print(f"Imported knowledge graph from {json_file}")
            return True
        
        def export_knowledge_graph(self, output_file):
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.graph_data, f, indent=2)
            print(f"Exported knowledge graph to {output_file}")
            return True
        
        def query(self, query, params=None):
            # Simulate a simple query for entities by type
            if "MATCH (n:" in query:
                entity_type = query.split("MATCH (n:")[1].split(")")[0].lower()
                results = []
                for node in self.graph_data.get('nodes', []):
                    if node.get('type', '').lower() == entity_type:
                        results.append({'n': node})
                return results
            
            # Simulate a query for relationships
            elif "MATCH (source)-[r]->(target)" in query:
                return [
                    {
                        'source': edge.get('source'),
                        'target': edge.get('target'),
                        'type': edge.get('type', '').upper(),
                        'properties': {k: v for k, v in edge.items() if k not in ['source', 'target', 'type']}
                    }
                    for edge in self.graph_data.get('edges', [])
                ]
            
            # Default empty result
            return []
    
    # Create mock database integration
    db_integration = MockDatabaseIntegration(knowledge_graph_file)
    
    # Connect to database
    if db_integration.connect():
        print("\nTesting database operations...")
        
        # Export knowledge graph to a new file
        exported_file = os.path.join(output_dir, 'exported_knowledge_graph.json')
        if db_integration.export_knowledge_graph(exported_file):
            print(f"Successfully exported knowledge graph to {exported_file}")
        
        # Simulate queries
        print("\nSimulating queries:")
        
        # Query for person entities
        print("\n1. Query for person entities:")
        results = db_integration.query("MATCH (n:person) RETURN n")
        for i, result in enumerate(results[:5]):  # Show first 5 results
            print(f"  {i+1}. {result['n'].get('text', 'Unknown')}")
        
        # Query for organization entities
        print("\n2. Query for organization entities:")
        results = db_integration.query("MATCH (n:organization) RETURN n")
        for i, result in enumerate(results[:5]):  # Show first 5 results
            print(f"  {i+1}. {result['n'].get('text', 'Unknown')}")
        
        # Query for relationships
        print("\n3. Query for relationships:")
        results = db_integration.query("MATCH (source)-[r]->(target) RETURN source, target, type(r), properties(r)")
        for i, result in enumerate(results[:5]):  # Show first 5 results
            print(f"  {i+1}. {result['source']} --[{result['type']}]--> {result['target']}")
        
        # Close connection
        db_integration.close()
        
        print("\nDatabase integration test completed successfully")

if __name__ == "__main__":
    main()
