#!/usr/bin/env python3
"""
Database Integration Components for KnowledgeReduce

This module implements the database integration components of the KnowledgeReduce framework,
which is responsible for storing, retrieving, and querying the knowledge graph.
"""

import os
import json
import networkx as nx
from typing import List, Dict, Tuple, Any, Optional, Set
from neo4j import GraphDatabase
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Neo4jConnector:
    """
    Component for connecting to and interacting with a Neo4j graph database.
    """
    
    def __init__(self, uri: str, username: str, password: str):
        """
        Initialize the Neo4j connector.
        
        Args:
            uri: URI of the Neo4j database
            username: Username for authentication
            password: Password for authentication
        """
        self.uri = uri
        self.username = username
        self.password = password
        self.driver = None
        
    def connect(self) -> bool:
        """
        Connect to the Neo4j database.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
            # Test connection
            with self.driver.session() as session:
                result = session.run("RETURN 1 AS test")
                record = result.single()
                if record and record["test"] == 1:
                    logger.info("Successfully connected to Neo4j database")
                    return True
                else:
                    logger.error("Failed to verify Neo4j connection")
                    return False
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j database: {e}")
            return False
    
    def close(self) -> None:
        """
        Close the connection to the Neo4j database.
        """
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
    
    def clear_database(self) -> bool:
        """
        Clear all data from the Neo4j database.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
                logger.info("Database cleared successfully")
                return True
        except Exception as e:
            logger.error(f"Failed to clear database: {e}")
            return False


class GraphDatabaseManager:
    """
    Component for managing the storage and retrieval of knowledge graphs in a graph database.
    """
    
    def __init__(self, connector: Neo4jConnector):
        """
        Initialize the graph database manager.
        
        Args:
            connector: Neo4j connector instance
        """
        self.connector = connector
    
    def store_knowledge_graph(self, graph: nx.DiGraph) -> bool:
        """
        Store a knowledge graph in the Neo4j database.
        
        Args:
            graph: NetworkX DiGraph representing the knowledge graph
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Clear existing data
            self.connector.clear_database()
            
            # Create nodes
            self._create_nodes(graph)
            
            # Create relationships
            self._create_relationships(graph)
            
            logger.info("Knowledge graph stored successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to store knowledge graph: {e}")
            return False
    
    def _create_nodes(self, graph: nx.DiGraph) -> None:
        """
        Create nodes in the Neo4j database from the knowledge graph.
        
        Args:
            graph: NetworkX DiGraph representing the knowledge graph
        """
        with self.connector.driver.session() as session:
            for node_id, node_data in graph.nodes(data=True):
                # Extract node properties
                properties = {k: v for k, v in node_data.items() if k != 'id'}
                
                # Create node
                node_type = properties.get('type', 'Entity')
                
                # Create Cypher query
                query = (
                    f"CREATE (n:{node_type} {{id: $id}}) "
                    "SET n += $properties "
                    "RETURN n"
                )
                
                # Execute query
                session.run(query, id=node_id, properties=properties)
    
    def _create_relationships(self, graph: nx.DiGraph) -> None:
        """
        Create relationships in the Neo4j database from the knowledge graph.
        
        Args:
            graph: NetworkX DiGraph representing the knowledge graph
        """
        with self.connector.driver.session() as session:
            for source, target, edge_data in graph.edges(data=True):
                # Extract relationship properties
                properties = {k: v for k, v in edge_data.items() if k not in ['source', 'target', 'type']}
                
                # Get relationship type
                rel_type = edge_data.get('type', 'RELATED_TO').upper()
                
                # Create Cypher query
                query = (
                    "MATCH (source {id: $source}), (target {id: $target}) "
                    f"CREATE (source)-[r:{rel_type} $properties]->(target) "
                    "RETURN r"
                )
                
                # Execute query
                session.run(query, source=source, target=target, properties=properties)


class QueryInterface:
    """
    Component for querying the knowledge graph stored in the Neo4j database.
    """
    
    def __init__(self, connector: Neo4jConnector):
        """
        Initialize the query interface.
        
        Args:
            connector: Neo4j connector instance
        """
        self.connector = connector
    
    def get_entity_by_id(self, entity_id: str) -> Dict[str, Any]:
        """
        Get an entity by its ID.
        
        Args:
            entity_id: ID of the entity to retrieve
            
        Returns:
            Dictionary containing entity properties
        """
        with self.connector.driver.session() as session:
            result = session.run(
                "MATCH (n {id: $id}) RETURN n",
                id=entity_id
            )
            record = result.single()
            if record:
                return dict(record["n"])
            else:
                return {}
    
    def get_entity_by_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Get entities by their text.
        
        Args:
            text: Text of the entities to retrieve
            
        Returns:
            List of dictionaries containing entity properties
        """
        with self.connector.driver.session() as session:
            result = session.run(
                "MATCH (n) WHERE n.text = $text RETURN n",
                text=text
            )
            return [dict(record["n"]) for record in result]
    
    def get_entities_by_type(self, entity_type: str) -> List[Dict[str, Any]]:
        """
        Get entities by their type.
        
        Args:
            entity_type: Type of the entities to retrieve
            
        Returns:
            List of dictionaries containing entity properties
        """
        with self.connector.driver.session() as session:
            result = session.run(
                f"MATCH (n:{entity_type}) RETURN n"
            )
            return [dict(record["n"]) for record in result]
    
    def get_relationships(self, source_id: str = None, target_id: str = None, rel_type: str = None) -> List[Dict[str, Any]]:
        """
        Get relationships between entities.
        
        Args:
            source_id: ID of the source entity (optional)
            target_id: ID of the target entity (optional)
            rel_type: Type of the relationship (optional)
            
        Returns:
            List of dictionaries containing relationship properties
        """
        query_parts = ["MATCH (source)-[r"]
        if rel_type:
            query_parts.append(f":{rel_type}")
        query_parts.append("]->(target)")
        
        conditions = []
        params = {}
        
        if source_id:
            conditions.append("source.id = $source_id")
            params["source_id"] = source_id
        
        if target_id:
            conditions.append("target.id = $target_id")
            params["target_id"] = target_id
        
        if conditions:
            query_parts.append("WHERE " + " AND ".join(conditions))
        
        query_parts.append("RETURN source.id AS source, target.id AS target, type(r) AS type, properties(r) AS properties")
        
        query = " ".join(query_parts)
        
        with self.connector.driver.session() as session:
            result = session.run(query, **params)
            relationships = []
            for record in result:
                rel = {
                    "source": record["source"],
                    "target": record["target"],
                    "type": record["type"]
                }
                rel.update(record["properties"])
                relationships.append(rel)
            return relationships
    
    def execute_custom_query(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Execute a custom Cypher query.
        
        Args:
            query: Cypher query to execute
            params: Parameters for the query (optional)
            
        Returns:
            List of dictionaries containing query results
        """
        params = params or {}
        with self.connector.driver.session() as session:
            result = session.run(query, **params)
            return [dict(record) for record in result]


class DataPersistenceLayer:
    """
    Component for managing the persistence of knowledge graphs between the application and the database.
    """
    
    def __init__(self, db_manager: GraphDatabaseManager, query_interface: QueryInterface):
        """
        Initialize the data persistence layer.
        
        Args:
            db_manager: Graph database manager instance
            query_interface: Query interface instance
        """
        self.db_manager = db_manager
        self.query_interface = query_interface
    
    def import_from_json(self, json_file: str) -> bool:
        """
        Import a knowledge graph from a JSON file into the database.
        
        Args:
            json_file: Path to the JSON file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Load JSON file
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Create NetworkX graph
            graph = nx.DiGraph()
            
            # Add nodes
            for node in data.get('nodes', []):
                node_id = node.pop('id', None)
                if node_id:
                    graph.add_node(node_id, **node)
            
            # Add edges
            for edge in data.get('edges', []):
                source = edge.pop('source', None)
                target = edge.pop('target', None)
                if source and target:
                    graph.add_edge(source, target, **edge)
            
            # Store graph in database
            return self.db_manager.store_knowledge_graph(graph)
        except Exception as e:
            logger.error(f"Failed to import knowledge graph from JSON: {e}")
            return False
    
    def export_to_json(self, output_file: str) -> bool:
        """
        Export the knowledge graph from the database to a JSON file.
        
        Args:
            output_file: Path to the output file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create graph dictionary
            graph_dict = {
                'nodes': [],
                'edges': []
            }
            
            # Get all node types
            with self.db_manager.connector.driver.session() as session:
                result = session.run("CALL db.labels()")
                node_types = [record["label"] for record in result]
            
            # Get nodes for each type
            for node_type in node_types:
                entities = self.query_interface.get_entities_by_type(node_type)
                for entity in entities:
                    node_dict = {'id': entity.pop('id', None)}
                    node_dict.update(entity)
                    graph_dict['nodes'].append(node_dict)
            
            # Get all relationships
            relationships = self.query_interface.execute_custom_query(
                "MATCH (source)-[r]->(target) "
                "RETURN source.id AS source, target.id AS target, type(r) AS type, properties(r) AS properties"
            )
            
            for rel in relationships:
                edge_dict = {
                    'source': rel['source'],
                    'target': rel['target'],
                    'type': rel['type'].lower()
                }
                edge_dict.update(rel['properties'])
                graph_dict['edges'].append(edge_dict)
            
            # Write to file
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(graph_dict, f, indent=2)
            
            logger.info(f"Knowledge graph exported to {output_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to export knowledge graph to JSON: {e}")
            return False


class DatabaseIntegration:
    """
    Main class for integrating the knowledge graph with a database, combining
    database connection, management, querying, and persistence.
    """
    
    def __init__(self, uri: str, username: str, password: str):
        """
        Initialize the database integration.
        
        Args:
            uri: URI of the Neo4j database
            username: Username for authentication
            password: Password for authentication
        """
        self.connector = Neo4jConnector(uri, username, password)
        self.db_manager = GraphDatabaseManager(self.connector)
        self.query_interface = QueryInterface(self.connector)
        self.persistence_layer = DataPersistenceLayer(self.db_manager, self.query_interface)
    
    def connect(self) -> bool:
        """
        Connect to the database.
        
        Returns:
            True if successful, False otherwise
        """
        return self.connector.connect()
    
    def close(self) -> None:
        """
        Close the connection to the database.
        """
        self.connector.close()
    
    def import_knowledge_graph(self, json_file: str) -> bool:
        """
        Import a knowledge graph from a JSON file.
        
        Args:
            json_file: Path to the JSON file
            
        Returns:
            True if successful, False otherwise
        """
        return self.persistence_layer.import_from_json(json_file)
    
    def export_knowledge_graph(self, output_file: str) -> bool:
        """
        Export the knowledge graph to a JSON file.
        
        Args:
            output_file: Path to the output file
            
        Returns:
            True if successful, False otherwise
        """
        return self.persistence_layer.export_to_json(output_file<response clipped><NOTE>To save on context only part of this file has been shown to you. You should retry this tool after you have searched inside the file with `grep -n` in order to find the line numbers of what you are looking for.</NOTE>