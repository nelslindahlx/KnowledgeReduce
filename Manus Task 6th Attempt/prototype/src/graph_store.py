"""
Graph store module for the KnowledgeReduce prototype.

This module provides interfaces for storing and retrieving knowledge graph data.
"""

import networkx as nx
import pandas as pd
import json
from typing import Dict, List, Tuple, Any, Optional
from neo4j import GraphDatabase

import config


class InMemoryGraphStore:
    """In-memory graph store using NetworkX."""
    
    def __init__(self):
        """Initialize the in-memory graph store."""
        self.graph = nx.DiGraph()
    
    def store_graph(self, graph: nx.DiGraph) -> None:
        """
        Store a knowledge graph.
        
        Args:
            graph: NetworkX DiGraph to store
        """
        self.graph = graph.copy()
    
    def get_graph(self) -> nx.DiGraph:
        """
        Get the stored knowledge graph.
        
        Returns:
            NetworkX DiGraph representing the knowledge graph
        """
        return self.graph
    
    def get_node(self, node_id: Any) -> Dict[str, Any]:
        """
        Get a node by ID.
        
        Args:
            node_id: ID of the node to retrieve
            
        Returns:
            Node data dictionary or empty dict if not found
        """
        if node_id in self.graph.nodes:
            return {**{"id": node_id}, **self.graph.nodes[node_id]}
        return {}
    
    def get_nodes_by_type(self, node_type: str) -> List[Dict[str, Any]]:
        """
        Get nodes by type.
        
        Args:
            node_type: Type of nodes to retrieve
            
        Returns:
            List of node data dictionaries
        """
        nodes = []
        for node_id, data in self.graph.nodes(data=True):
            if data.get("type") == node_type:
                nodes.append({**{"id": node_id}, **data})
        return nodes
    
    def get_relationships(self, source_id: Any = None, target_id: Any = None, rel_type: str = None) -> List[Dict[str, Any]]:
        """
        Get relationships, optionally filtered by source, target, or type.
        
        Args:
            source_id: Optional source node ID filter
            target_id: Optional target node ID filter
            rel_type: Optional relationship type filter
            
        Returns:
            List of relationship data dictionaries
        """
        relationships = []
        
        for source, target, data in self.graph.edges(data=True):
            # Apply filters
            if source_id is not None and source != source_id:
                continue
            if target_id is not None and target != target_id:
                continue
            if rel_type is not None and data.get("type") != rel_type:
                continue
            
            relationships.append({
                "source_id": source,
                "target_id": target,
                **data
            })
        
        return relationships
    
    def get_neighbors(self, node_id: Any, direction: str = "both") -> List[Dict[str, Any]]:
        """
        Get neighboring nodes of a given node.
        
        Args:
            node_id: ID of the node to get neighbors for
            direction: Direction of relationships to consider ("in", "out", or "both")
            
        Returns:
            List of neighboring node data dictionaries
        """
        if node_id not in self.graph.nodes:
            return []
        
        neighbors = []
        
        if direction in ["out", "both"]:
            for target in self.graph.successors(node_id):
                neighbors.append({**{"id": target}, **self.graph.nodes[target]})
        
        if direction in ["in", "both"]:
            for source in self.graph.predecessors(node_id):
                if {**{"id": source}, **self.graph.nodes[source]} not in neighbors:
                    neighbors.append({**{"id": source}, **self.graph.nodes[source]})
        
        return neighbors
    
    def export_to_json(self, file_path: str) -> None:
        """
        Export the graph to a JSON file.
        
        Args:
            file_path: Path to save the JSON file
        """
        # Convert graph to a serializable format
        graph_data = {
            "nodes": [],
            "edges": []
        }
        
        for node_id, data in self.graph.nodes(data=True):
            graph_data["nodes"].append({**{"id": node_id}, **data})
        
        for source, target, data in self.graph.edges(data=True):
            graph_data["edges"].append({
                "source": source,
                "target": target,
                **data
            })
        
        with open(file_path, 'w') as f:
            json.dump(graph_data, f, indent=2)
    
    def import_from_json(self, file_path: str) -> None:
        """
        Import a graph from a JSON file.
        
        Args:
            file_path: Path to the JSON file
        """
        with open(file_path, 'r') as f:
            graph_data = json.load(f)
        
        # Create a new graph
        self.graph = nx.DiGraph()
        
        # Add nodes
        for node in graph_data["nodes"]:
            node_id = node.pop("id")
            self.graph.add_node(node_id, **node)
        
        # Add edges
        for edge in graph_data["edges"]:
            source = edge.pop("source")
            target = edge.pop("target")
            self.graph.add_edge(source, target, **edge)


class Neo4jGraphStore:
    """Neo4j graph database store."""
    
    def __init__(self, uri=None, user=None, password=None):
        """
        Initialize the Neo4j graph store.
        
        Args:
            uri: Neo4j connection URI
            user: Neo4j username
            password: Neo4j password
        """
        self.uri = uri or config.NEO4J_URI
        self.user = user or config.NEO4J_USER
        self.password = password or config.NEO4J_PASSWORD
        self.driver = None
    
    def connect(self) -> None:
        """Connect to the Neo4j database."""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        except Exception as e:
            print(f"Error connecting to Neo4j: {e}")
    
    def close(self) -> None:
        """Close the Neo4j connection."""
        if self.driver:
            self.driver.close()
    
    def store_graph(self, graph: nx.DiGraph) -> None:
        """
        Store a knowledge graph in Neo4j.
        
        Args:
            graph: NetworkX DiGraph to store
        """
        if not self.driver:
            self.connect()
        
        if not self.driver:
            print("Failed to connect to Neo4j, cannot store graph")
            return
        
        with self.driver.session() as session:
            # Clear existing data
            session.run("MATCH (n) DETACH DELETE n")
            
            # Create nodes
            for node_id, data in graph.nodes(data=True):
                node_type = data.get("type", "Entity")
                properties = {k: v for k, v in data.items() if k != "type"}
                properties["id"] = str(node_id)  # Ensure ID is a string for Neo4j
                
                # Convert any non-primitive types to strings
                for key, value in properties.items():
                    if not isinstance(value, (str, int, float, bool, type(None))):
                        properties[key] = str(value)
                
                cypher = f"CREATE (n:{node_type} $properties)"
                session.run(cypher, properties=properties)
            
            # Create relationships
            for source, target, data in graph.edges(data=True):
                rel_type = data.get("type", "RELATED_TO")
                properties = {k: v for k, v in data.items() if k != "type"}
                
                # Convert any non-primitive types to strings
                for key, value in properties.items():
                    if not isinstance(value, (str, int, float, bool, type(None))):
                        properties[key] = str(value)
                
                cypher = f"""
                MATCH (source) WHERE source.id = $source_id
                MATCH (target) WHERE target.id = $target_id
                CREATE (source)-[r:{rel_type} $properties]->(target)
                """
                session.run(cypher, source_id=str(source), target_id=str(target), properties=properties)
    
    def get_graph(self) -> nx.DiGraph:
        """
        Get the stored knowledge graph from Neo4j.
        
        Returns:
            NetworkX DiGraph representing the knowledge graph
        """
        graph = nx.DiGraph()
        
        if not self.driver:
            self.connect()
        
        if not self.driver:
            print("Failed to connect to Neo4j, returning empty graph")
            return graph
        
        with self.driver.session() as session:
            # Get nodes
            result = session.run("MATCH (n) RETURN n")
            for record in result:
                node = record["n"]
                node_id = node.get("id")
                if node_id:
                    # Remove id from properties as it becomes the node ID
                    properties = dict(node.items())
                    properties.pop("id", None)
                    # Add node type from labels
                    properties["type"] = list(node.labels)[0] if node.labels else "Entity"
                    graph.add_node(node_id, **properties)
            
            # Get relationships
            result = session.run("MATCH (s)-[r]->(t) RETURN s.id as source, t.id as target, type(r) as type, r")
            for record in result:
                source = record["source"]
                target = record["target"]
                rel_type = record["type"]
                rel = record["r"]
                
                properties = dict(rel.items())
                properties["type"] = rel_type
                
                graph.add_edge(source, target, **properties)
        
        return graph
    
    def execute_query(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Execute a Cypher query against the Neo4j database.
        
        Args:
            query: Cypher query string
            parameters: Query parameters
            
        Returns:
            List of result records as dictionaries
        """
        if not self.driver:
            self.connect()
        
        if not self.driver:
            print("Failed to connect to Neo4j, cannot execute query")
            return []
        
        parameters = parameters or {}
        results = []
        
        with self.driver.session() as session:
            result = session.run(query, parameters)
            for record in result:
                results.append(dict(record))
        
        return results


class GraphStoreFactory:
    """Factory for creating graph stores."""
    
    @staticmethod
    def create_store(store_type: str = "memory", **kwargs) -> Any:
        """
        Create a graph store of the specified type.
        
        Args:
            store_type: Type of graph store to create ("memory" or "neo4j")
            **kwargs: Additional arguments for the graph store
            
        Returns:
            Graph store instance
        """
        if store_type == "neo4j":
            return Neo4jGraphStore(**kwargs)
        else:
            return InMemoryGraphStore()


if __name__ == "__main__":
    # Test the module
    from data_ingestion import DataIngestionPipeline, create_sample_data
    from knowledge_mapping import KnowledgeMapper
    from knowledge_reduction import KnowledgeReducer
    
    # Create and load sample data
    create_sample_data()
    pipeline = DataIngestionPipeline()
    entities_df, relationships_df = pipeline.ingest()
    
    # Map data to entities and relationships
    mapper = KnowledgeMapper()
    entities, relationships = mapper.map(entities_df, relationships_df)
    
    # Reduce mapped knowledge
    reducer = KnowledgeReducer()
    resolved_entities, aggregated_relationships, knowledge_graph = reducer.reduce(entities, relationships)
    
    # Store the graph
    graph_store = GraphStoreFactory.create_store("memory")
    graph_store.store_graph(knowledge_graph)
    
    # Test retrieval
    print("Nodes by type 'Person':")
    person_nodes = graph_store.get_nodes_by_type("Person")
    for node in person_nodes:
        print(f"  {node['name']} ({node['id']})")
    
    print("\nRelationships of type 'WORKS_FOR':")
    works_for_rels = graph_store.get_relationships(rel_type="WORKS_FOR")
    for rel in works_for_rels:
        source = graph_store.get_node(rel["source_id"])
        target = graph_store.get_node(rel["target_id"])
        print(f"  {source['name']} -> {target['name']}")
    
    # Export to JSON
    graph_store.export_to_json("data/knowledge_graph.json")
    print("\nGraph exported to data/knowledge_graph.json")
