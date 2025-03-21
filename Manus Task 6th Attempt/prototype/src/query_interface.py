"""
Query interface module for the KnowledgeReduce prototype.

This module provides interfaces for querying and analyzing the knowledge graph.
"""

import networkx as nx
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional
import json

from graph_store import GraphStoreFactory


class QueryBuilder:
    """Builder for constructing graph queries."""
    
    def __init__(self):
        """Initialize the query builder."""
        self.query_parts = {
            "match": [],
            "where": [],
            "return": [],
            "order_by": [],
            "limit": None
        }
    
    def match(self, pattern: str) -> 'QueryBuilder':
        """
        Add a MATCH clause to the query.
        
        Args:
            pattern: Pattern to match
            
        Returns:
            Self for chaining
        """
        self.query_parts["match"].append(pattern)
        return self
    
    def where(self, condition: str) -> 'QueryBuilder':
        """
        Add a WHERE condition to the query.
        
        Args:
            condition: Condition to add
            
        Returns:
            Self for chaining
        """
        self.query_parts["where"].append(condition)
        return self
    
    def return_clause(self, variables: str) -> 'QueryBuilder':
        """
        Add a RETURN clause to the query.
        
        Args:
            variables: Variables to return
            
        Returns:
            Self for chaining
        """
        self.query_parts["return"].append(variables)
        return self
    
    def order_by(self, expression: str) -> 'QueryBuilder':
        """
        Add an ORDER BY clause to the query.
        
        Args:
            expression: Expression to order by
            
        Returns:
            Self for chaining
        """
        self.query_parts["order_by"].append(expression)
        return self
    
    def limit(self, count: int) -> 'QueryBuilder':
        """
        Add a LIMIT clause to the query.
        
        Args:
            count: Maximum number of results
            
        Returns:
            Self for chaining
        """
        self.query_parts["limit"] = count
        return self
    
    def build(self) -> str:
        """
        Build the complete query string.
        
        Returns:
            Cypher query string
        """
        query = ""
        
        if self.query_parts["match"]:
            query += "MATCH " + ", ".join(self.query_parts["match"])
        
        if self.query_parts["where"]:
            query += " WHERE " + " AND ".join(self.query_parts["where"])
        
        if self.query_parts["return"]:
            query += " RETURN " + ", ".join(self.query_parts["return"])
        
        if self.query_parts["order_by"]:
            query += " ORDER BY " + ", ".join(self.query_parts["order_by"])
        
        if self.query_parts["limit"] is not None:
            query += f" LIMIT {self.query_parts['limit']}"
        
        return query


class GraphQuery:
    """Interface for querying the knowledge graph."""
    
    def __init__(self, graph_store):
        """
        Initialize the graph query interface.
        
        Args:
            graph_store: Graph store to query
        """
        self.graph_store = graph_store
    
    def get_entities_by_type(self, entity_type: str) -> List[Dict[str, Any]]:
        """
        Get entities of a specific type.
        
        Args:
            entity_type: Type of entities to retrieve
            
        Returns:
            List of entity dictionaries
        """
        return self.graph_store.get_nodes_by_type(entity_type)
    
    def get_entity_by_id(self, entity_id: Any) -> Dict[str, Any]:
        """
        Get an entity by ID.
        
        Args:
            entity_id: ID of the entity to retrieve
            
        Returns:
            Entity dictionary or empty dict if not found
        """
        return self.graph_store.get_node(entity_id)
    
    def get_entity_by_name(self, name: str) -> Dict[str, Any]:
        """
        Get an entity by name (returns first match).
        
        Args:
            name: Name of the entity to retrieve
            
        Returns:
            Entity dictionary or empty dict if not found
        """
        graph = self.graph_store.get_graph()
        for node_id, data in graph.nodes(data=True):
            if data.get("name", "").lower() == name.lower():
                return {**{"id": node_id}, **data}
        return {}
    
    def get_relationships_between(self, source_id: Any, target_id: Any) -> List[Dict[str, Any]]:
        """
        Get relationships between two entities.
        
        Args:
            source_id: Source entity ID
            target_id: Target entity ID
            
        Returns:
            List of relationship dictionaries
        """
        return self.graph_store.get_relationships(source_id=source_id, target_id=target_id)
    
    def get_relationships_by_type(self, rel_type: str) -> List[Dict[str, Any]]:
        """
        Get relationships of a specific type.
        
        Args:
            rel_type: Type of relationships to retrieve
            
        Returns:
            List of relationship dictionaries
        """
        return self.graph_store.get_relationships(rel_type=rel_type)
    
    def get_neighbors(self, entity_id: Any, direction: str = "both") -> List[Dict[str, Any]]:
        """
        Get neighboring entities of a given entity.
        
        Args:
            entity_id: ID of the entity to get neighbors for
            direction: Direction of relationships to consider ("in", "out", or "both")
            
        Returns:
            List of neighboring entity dictionaries
        """
        return self.graph_store.get_neighbors(entity_id, direction)
    
    def execute_cypher(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Execute a Cypher query (for Neo4j store only).
        
        Args:
            query: Cypher query string
            parameters: Query parameters
            
        Returns:
            List of result records as dictionaries
        """
        if hasattr(self.graph_store, "execute_query"):
            return self.graph_store.execute_query(query, parameters)
        else:
            raise NotImplementedError("Cypher queries are only supported with Neo4j graph store")
    
    def find_paths(self, source_id: Any, target_id: Any, max_length: int = 3) -> List[List[Dict[str, Any]]]:
        """
        Find paths between two entities.
        
        Args:
            source_id: Source entity ID
            target_id: Target entity ID
            max_length: Maximum path length
            
        Returns:
            List of paths, where each path is a list of entity dictionaries
        """
        graph = self.graph_store.get_graph()
        
        if source_id not in graph.nodes or target_id not in graph.nodes:
            return []
        
        paths = []
        
        # Find all simple paths up to max_length
        for path in nx.all_simple_paths(graph, source_id, target_id, cutoff=max_length):
            entity_path = []
            for node_id in path:
                entity_path.append({**{"id": node_id}, **graph.nodes[node_id]})
            paths.append(entity_path)
        
        return paths
    
    def find_common_neighbors(self, entity_ids: List[Any]) -> List[Dict[str, Any]]:
        """
        Find common neighbors of multiple entities.
        
        Args:
            entity_ids: List of entity IDs
            
        Returns:
            List of common neighboring entity dictionaries
        """
        if not entity_ids:
            return []
        
        graph = self.graph_store.get_graph()
        
        # Get neighbors for each entity
        all_neighbors = []
        for entity_id in entity_ids:
            if entity_id in graph.nodes:
                # Get both incoming and outgoing neighbors
                neighbors = set(graph.successors(entity_id)) | set(graph.predecessors(entity_id))
                all_neighbors.append(neighbors)
        
        if not all_neighbors:
            return []
        
        # Find intersection of all neighbor sets
        common_ids = set.intersection(*all_neighbors)
        
        # Convert to entity dictionaries
        common_entities = []
        for node_id in common_ids:
            common_entities.append({**{"id": node_id}, **graph.nodes[node_id]})
        
        return common_entities


class KnowledgeAnalyzer:
    """Analyzes the knowledge graph to extract insights."""
    
    def __init__(self, graph_store):
        """
        Initialize the knowledge analyzer.
        
        Args:
            graph_store: Graph store containing the knowledge graph
        """
        self.graph_store = graph_store
    
    def get_central_entities(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most central entities based on degree centrality.
        
        Args:
            top_n: Number of top entities to return
            
        Returns:
            List of entity dictionaries with centrality scores
        """
        graph = self.graph_store.get_graph()
        
        # Calculate degree centrality
        centrality = nx.degree_centrality(graph)
        
        # Sort entities by centrality
        sorted_entities = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:top_n]
        
        # Convert to entity dictionaries with centrality scores
        central_entities = []
        for node_id, score in sorted_entities:
            entity = {**{"id": node_id}, **graph.nodes[node_id], "centrality": score}
            central_entities.append(entity)
        
        return central_entities
    
    def get_entity_clusters(self, num_clusters: int = 5) -> Dict[int, List[Dict[str, Any]]]:
        """
        Cluster entities based on graph structure.
        
        Args:
            num_clusters: Target number of clusters
            
        Returns:
            Dictionary mapping cluster IDs to lists of entity dictionaries
        """
        graph = self.graph_store.get_graph()
        
        # Use community detection to find clusters
        try:
            import community as community_louvain
            partition = community_louvain.best_partition(nx.Graph(graph))
        except ImportError:
            # Fallback to connected components
            clusters = {}
            for i, component in enumerate(nx.weakly_connected_components(graph)):
                if i >= num_clusters:
                    break
                clusters[i] = []
                for node_id in component:
                    clusters[i].append({**{"id": node_id}, **graph.nodes[node_id]})
            return clusters
        
        # Group entities by cluster
        clusters = {}
        for node_id, cluster_id in partition.items():
            if cluster_id not in clusters:
                clusters[cluster_id] = []
            clusters[cluster_id].append({**{"id": node_id}, **graph.nodes[node_id]})
        
        # Limit to top num_clusters by size
        sorted_clusters = sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True)[:num_clusters]
        return dict(sorted_clusters)
    
    def get_entity_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about entities in the knowledge graph.
        
        Returns:
            Dictionary of entity statistics
        """
        graph = self.graph_store.get_graph()
        
        # Count entities by type
        entity_types = {}
        for _, data in graph.nodes(data=True):
            entity_type = data.get("type", "Unknown")
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
        
        # Calculate average number of relationships per entity
        avg_degree = sum(dict(graph.degree()).values()) / max(1, graph.number_of_nodes())
        
        return {
            "total_entities": graph.number_of_nodes(),
            "entity_types": entity_types,
            "avg_relationships": avg_degree
        }
    
    def get_relationship_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about relationships in the knowledge graph.
        
        Returns:
            Dictionary of relationship statistics
        """
        graph = self.graph_store.get_graph()
        
        # Count relationships by type
        relationship_types = {}
        for _, _, data in graph.edges(data=True):
            rel_type = data.get("type", "Unknown")
            relationship_types[rel_type] = relationship_types.get(rel_type, 0) + 1
        
        return {
            "total_relationships": graph.number_of_edges(),
            "relationship_types": relationship_types
        }
    
    def generate_summary(self) -> Dict[str, Any]:
        """
        Generate a summary of the knowledge graph.
        
        Returns:
            Dictionary containing summary information
        """
        entity_stats = self.get_entity_statistics()
        relationship_stats = self.get_relationship_statistics()
        central_entities = self.get_central_entities(5)
        
        return {
            "entity_statistics": entity_stats,
            "relationship_statistics": relationship_stats,
            "central_entities": central_entities
        }


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
    
    # Create query interface
    query = GraphQuery(graph_store)
    
    # Test queries
    print("Entities of type 'Person':")
    persons = query.get_entities_by_type("Person")
    for person in persons:
        print(f"  {person['name']} ({person['id']})")
    
    # Find entity by name
    john = query.get_entity_by_name("John Smith")
    if john:
        print(f"\nFound entity: {john['name']} ({john['id']})")
        
        # Get neighbors
        neighbors = query.get_neighbors(john['id'])
        print(f"\nNeighbors of {john['name']}:")
        for neighbor in neighbors:
            print(f"  {neighbor['name']} ({neighbor['type']})")
    
    # Create analyzer
    analyzer = KnowledgeAnalyzer(graph_store)
    
    # Get central entities
    print("\nMost central entities:")
    central = analyzer.get_central_entities(3)
    for entity in central:
        print(f"  {entity['name']} (centrality: {entity['centrality']:.3f})")
    
    # Generate summary
    summary = analyzer.generate_summary()
    print(f"\nKnowledge Graph Summary:")
    print(f"  Entities: {summary['entity_statistics']['total_entities']}")
    print(f"  Relationships: {summary['relationship_statistics']['total_relationships']}")
    print(f"  Entity types: {summary['entity_statistics']['entity_types']}")
    print(f"  Relationship types: {summary['relationship_statistics']['relationship_types']}")
