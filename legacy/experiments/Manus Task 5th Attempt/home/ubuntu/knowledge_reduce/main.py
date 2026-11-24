#!/usr/bin/env python3
"""
Main script for the KnowledgeReduce system

This script integrates all components of the KnowledgeReduce system
and provides a complete workflow for extracting facts from text data,
stacking knowledge, and storing it in a database.
"""

import os
import sys
import json
import argparse
import logging
from typing import List, Dict, Any

# Import KnowledgeReduce components
from knowledge_reduce.fact_extraction import FactExtractor
from knowledge_reduce.knowledge_stacking import KnowledgeStacker
from knowledge_reduce.database_integration import DatabaseIntegration

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KnowledgeReduceSystem:
    """
    Main class for the KnowledgeReduce system, integrating all components.
    """
    
    def __init__(self, use_mock_db: bool = True, db_uri: str = None, db_username: str = None, db_password: str = None):
        """
        Initialize the KnowledgeReduce system.
        
        Args:
            use_mock_db: Whether to use a mock database (for testing)
            db_uri: URI of the Neo4j database (if not using mock)
            db_username: Username for the Neo4j database (if not using mock)
            db_password: Password for the Neo4j database (if not using mock)
        """
        self.fact_extractor = FactExtractor()
        self.knowledge_stacker = KnowledgeStacker()
        
        self.use_mock_db = use_mock_db
        self.db_uri = db_uri
        self.db_username = db_username
        self.db_password = db_password
        self.db_integration = None
        
        # Output directories
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.output_dir = os.path.join(self.base_dir, 'output')
        os.makedirs(self.output_dir, exist_ok=True)
    
    def connect_to_database(self) -> bool:
        """
        Connect to the database.
        
        Returns:
            True if connection is successful, False otherwise
        """
        if self.use_mock_db:
            # Use mock database for testing
            self.db_integration = MockDatabaseIntegration()
            return self.db_integration.connect()
        else:
            # Use real Neo4j database
            if not all([self.db_uri, self.db_username, self.db_password]):
                logger.error("Database connection parameters are missing")
                return False
            
            self.db_integration = DatabaseIntegration(
                uri=self.db_uri,
                username=self.db_username,
                password=self.db_password
            )
            return self.db_integration.connect()
    
    def close_database_connection(self) -> None:
        """
        Close the connection to the database.
        """
        if self.db_integration:
            self.db_integration.close()
    
    def process_text_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        Process text files to extract facts and build a knowledge graph.
        
        Args:
            file_paths: List of paths to text files
            
        Returns:
            Dictionary containing the knowledge graph
        """
        # Extract facts from each file
        fact_sets = []
        for file_path in file_paths:
            logger.info(f"Extracting facts from {file_path}")
            facts = self.fact_extractor.extract_facts_from_file(file_path)
            
            # Save extracted facts
            file_name = os.path.basename(file_path)
            facts_file = os.path.join(self.output_dir, f"{os.path.splitext(file_name)[0]}_facts.json")
            self.fact_extractor.save_facts(facts, facts_file)
            logger.info(f"Facts saved to {facts_file}")
            
            fact_sets.append(facts)
        
        # Stack knowledge from all fact sets
        logger.info("Stacking knowledge from all fact sets")
        knowledge_graph = self.knowledge_stacker.stack_knowledge(fact_sets)
        
        # Convert NetworkX graph to dictionary
        graph_dict = {
            'nodes': [],
            'edges': []
        }
        
        # Add nodes
        for node_id, node_data in knowledge_graph.nodes(data=True):
            node_dict = {'id': node_id}
            node_dict.update(node_data)
            graph_dict['nodes'].append(node_dict)
        
        # Add edges
        for source, target, edge_data in knowledge_graph.edges(data=True):
            edge_dict = {
                'source': source,
                'target': target
            }
            edge_dict.update(edge_data)
            graph_dict['edges'].append(edge_dict)
        
        # Save stacked knowledge graph
        stacked_graph_file = os.path.join(self.output_dir, 'stacked_knowledge_graph.json')
        with open(stacked_graph_file, 'w', encoding='utf-8') as f:
            json.dump(graph_dict, f, indent=2)
        logger.info(f"Stacked knowledge graph saved to {stacked_graph_file}")
        
        return graph_dict
    
    def store_knowledge_graph(self, graph_dict: Dict[str, Any]) -> bool:
        """
        Store the knowledge graph in the database.
        
        Args:
            graph_dict: Dictionary containing the knowledge graph
            
        Returns:
            True if successful, False otherwise
        """
        if not self.db_integration:
            logger.error("Database connection not established")
            return False
        
        # Store knowledge graph in database
        logger.info("Storing knowledge graph in database")
        
        # Convert graph dictionary to JSON file for import
        temp_file = os.path.join(self.output_dir, 'temp_graph.json')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(graph_dict, f, indent=2)
        
        # Import knowledge graph
        result = self.db_integration.import_knowledge_graph(temp_file)
        
        # Clean up temporary file
        if os.path.exists(temp_file):
            os.remove(temp_file)
        
        return result
    
    def query_knowledge_graph(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Query the knowledge graph.
        
        Args:
            query: Query to execute
            params: Parameters for the query (optional)
            
        Returns:
            List of dictionaries containing query results
        """
        if not self.db_integration:
            logger.error("Database connection not established")
            return []
        
        logger.info(f"Executing query: {query}")
        return self.db_integration.query(query, params)
    
    def run_complete_workflow(self, file_paths: List[str]) -> bool:
        """
        Run the complete KnowledgeReduce workflow.
        
        Args:
            file_paths: List of paths to text files
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Connect to database
            if not self.connect_to_database():
                logger.error("Failed to connect to database")
                return False
            
            # Process text files
            graph_dict = self.process_text_files(file_paths)
            
            # Store knowledge graph
            if not self.store_knowledge_graph(graph_dict):
                logger.error("Failed to store knowledge graph")
                return False
            
            # Run example queries
            self._run_example_queries()
            
            # Close database connection
            self.close_database_connection()
            
            logger.info("Complete workflow executed successfully")
            return True
        except Exception as e:
            logger.error(f"Error in workflow execution: {e}")
            return False
    
    def _run_example_queries(self) -> None:
        """
        Run example queries on the knowledge graph.
        """
        logger.info("Running example queries")
        
        # Query for person entities
        logger.info("Query for person entities:")
        results = self.query_knowledge_graph("MATCH (n:person) RETURN n LIMIT 5")
        for i, result in enumerate(results):
            logger.info(f"  {i+1}. {result.get('n', {}).get('text', 'Unknown')}")
        
        # Query for organization entities
        logger.info("Query for organization entities:")
        results = self.query_knowledge_graph("MATCH (n:organization) RETURN n LIMIT 5")
        for i, result in enumerate(results):
            logger.info(f"  {i+1}. {result.get('n', {}).get('text', 'Unknown')}")
        
        # Query for relationships
        logger.info("Query for relationships:")
        results = self.query_knowledge_graph(
            "MATCH (source)-[r]->(target) RETURN source, target, type(r) LIMIT 5"
        )
        for i, result in enumerate(results):
            source = result.get('source', {}).get('id', 'Unknown')
            target = result.get('target', {}).get('id', 'Unknown')
            rel_type = result.get('type(r)', 'Unknown')
            logger.info(f"  {i+1}. {source} --[{rel_type}]--> {target}")


# Mock database implementation for testing
class MockDatabaseIntegration:
    """
    Mock implementation of the database integration for testing.
    """
    
    def __init__(self):
        """
        Initialize the mock database integration.
        """
        self.graph_data = None
        self.node_index = {}
        self.edge_index = {}
    
    def connect(self) -> bool:
        """
        Connect to the mock database.
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("Connected to mock database")
        return True
    
    def close(self) -> None:
        """
        Close the connection to the mock database.
        """
        logger.info("Closed connection to mock database")
    
    def import_knowledge_graph(self, json_file: str) -> bool:
        """
        Import a knowledge graph from a JSON file.
        
        Args:
            json_file: Path to the JSON file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
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
            
            logger.info(f"Imported knowledge graph from {json_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to import knowledge graph: {e}")
            return False
    
    def export_knowledge_graph(self, output_file: str) -> bool:
        """
        Export the knowledge graph to a JSON file.
        
        Args:
            output_file: Path to the output file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.graph_data:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(self.graph_data, f, indent=2)
                logger.info(f"Exported knowledge graph to {output_file}")
                return True
            else:
                logger.error("No graph data to export")
                return False
        except Exception as e:
            logger.error(f"Failed to export knowledge graph: {e}")
            return False
    
    def query(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Execute a query on the mock database.
        
        Args:
            query: Query to execute
            params: Parameters for the query (optional)
            
        Returns:
            List of dictionaries containing query results
        """
        if not self.graph_data:
            return []
        
        # Simulate a simple query for entities by type
        if "MATCH (n:" in query:
            entity_type = query.split("MATCH (n:")[1].split(")")[0].lower()
            results = []
            for node in self.graph_data.get('nodes', []):
                if node.get('type', '').lower() == entity_type:
                    results.append({'n': node})
            
            # Apply limit if specified
            if "LIMIT" in query:
                limit = int(query.split("LIMIT")[1].strip())
                results = results[:limit]
            
            return results
        
        # Simulate a query for relationships
        elif "MATCH (source)-[r]->(target)" in query:
            results = []
            for edge in self.graph_data.get('edges', []):
                source_id = edge.get('source')
                target_id = edge.get('target')
                
                if source_id in self.node_index and target_id in self.node_index:
                    result = {
                        'source': self.node_index[source_id],
                        'target': self.node_index[target_id],
                        'type(r)': edge.get('type', '').upper()
                    }
                    results.append(result)
            
            # Apply limit if specified
            if "LIMIT" in query:
                limit = int(query.split("LIMIT")[1].strip())
                results = results[:limit]
            
            return results
        
        # Default empty result
        return []


def main():
    """
    Main function to run the KnowledgeReduce system.
    """
    parser = argparse.ArgumentParser(description='KnowledgeReduce System')
    parser.add_argument('--files', nargs='+', help='Paths to text files to process')
    parser.add_argument('--use-mock-db', action='store_true', help='Use mock database for testing')
    parser.add_argument('--db-uri', help='URI of the Neo4j database')
    parser.add_argument('--db-username', help='Username for the Neo4j database')
    parser.add_argument('--db-password', help='Password for the Neo4j database')
    
    args = parser.parse_args()
    
    # Use default files if none provided
    if not args.files:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(base_dir, 'data')
        # Check if the file exists
        default_file = os.path.join(data_dir, 'tech_companies.txt')
        if not os.path.exists(default_file):
            logger.warning(f"Default file {default_file} not found, using absolute path")
            default_file = '/home/ubuntu/knowledge_reduce/data/tech_companies.txt'
        args.files = [default_file]
    
    # Create KnowledgeReduce system
    system = KnowledgeReduceSystem(
        use_mock_db=args.use_mock_db or not all([args.db_uri, args.db_username, args.db_password]),
        db_uri=args.db_uri,
        db_username=args.db_username,
        db_password=args.db_password
    )
    
    # Run complete workflow
    success = system.run_complete_workflow(args.files)
    
    if success:
        logger.info("KnowledgeReduce system executed successfully")
        return 0
    else:
        logger.error("KnowledgeReduce system execution failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
