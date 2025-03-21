"""
Knowledge reduction module for the KnowledgeReduce prototype.

This module implements the reducing phase of KnowledgeReduce, resolving entities and
synthesizing the knowledge graph.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Set, Any
from collections import defaultdict
from fuzzywuzzy import fuzz
import networkx as nx

import config


class EntityResolver:
    """Resolves and merges duplicate entities."""
    
    def __init__(self, similarity_threshold=None, max_edit_distance=None):
        """
        Initialize the entity resolver.
        
        Args:
            similarity_threshold: Threshold for fuzzy matching (0.0-1.0)
            max_edit_distance: Maximum edit distance for name matching
        """
        self.similarity_threshold = similarity_threshold or config.SIMILARITY_THRESHOLD
        self.max_edit_distance = max_edit_distance or config.MAX_EDIT_DISTANCE
    
    def resolve(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Resolve duplicate entities by identifying and merging them.
        
        Args:
            entities: List of entities to resolve
            
        Returns:
            List of resolved entities
        """
        if not entities:
            return []
        
        # Group entities by type for more efficient comparison
        entities_by_type = defaultdict(list)
        for entity in entities:
            entities_by_type[entity["type"]].append(entity)
        
        resolved_entities = []
        entity_groups = []
        
        # Find duplicate groups within each entity type
        for entity_type, type_entities in entities_by_type.items():
            # Create groups of duplicate entities
            type_entity_groups = self._find_duplicate_groups(type_entities)
            entity_groups.extend(type_entity_groups)
        
        # Merge each group of duplicates
        for group in entity_groups:
            merged_entity = self._merge_entities(group)
            resolved_entities.append(merged_entity)
        
        return resolved_entities
    
    def _find_duplicate_groups(self, entities: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        Find groups of duplicate entities.
        
        Args:
            entities: List of entities to check for duplicates
            
        Returns:
            List of entity groups, where each group contains duplicate entities
        """
        # Initialize each entity as its own group
        groups = [[entity] for entity in entities]
        
        # Merge groups if they contain similar entities
        i = 0
        while i < len(groups):
            j = i + 1
            while j < len(groups):
                if self._groups_contain_similar_entities(groups[i], groups[j]):
                    # Merge groups
                    groups[i].extend(groups[j])
                    groups.pop(j)
                else:
                    j += 1
            i += 1
        
        # Filter out groups with only one entity (no duplicates)
        duplicate_groups = [group for group in groups if len(group) > 1]
        
        # Add remaining single entities
        single_entities = [group[0] for group in groups if len(group) == 1]
        duplicate_groups.extend([[entity] for entity in single_entities])
        
        return duplicate_groups
    
    def _groups_contain_similar_entities(self, group1: List[Dict[str, Any]], group2: List[Dict[str, Any]]) -> bool:
        """
        Check if two groups contain similar entities.
        
        Args:
            group1: First group of entities
            group2: Second group of entities
            
        Returns:
            True if the groups contain similar entities, False otherwise
        """
        for entity1 in group1:
            for entity2 in group2:
                if self._are_similar_entities(entity1, entity2):
                    return True
        return False
    
    def _are_similar_entities(self, entity1: Dict[str, Any], entity2: Dict[str, Any]) -> bool:
        """
        Check if two entities are similar based on name and attributes.
        
        Args:
            entity1: First entity
            entity2: Second entity
            
        Returns:
            True if the entities are similar, False otherwise
        """
        # Check for exact ID match
        if "id" in entity1 and "id" in entity2 and entity1["id"] == entity2["id"]:
            return True
        
        # Check for name similarity
        name1 = entity1.get("name", "").lower()
        name2 = entity2.get("name", "").lower()
        
        # Exact name match
        if name1 == name2 and name1:
            return True
        
        # Fuzzy name match
        similarity = fuzz.ratio(name1, name2) / 100.0
        if similarity >= self.similarity_threshold:
            return True
        
        return False
    
    def _merge_entities(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge a group of duplicate entities into a single entity.
        
        Args:
            entities: List of duplicate entities to merge
            
        Returns:
            Merged entity
        """
        if not entities:
            return {}
        
        if len(entities) == 1:
            return entities[0]
        
        # Start with the first entity as the base
        merged = entities[0].copy()
        
        # Track all IDs that this entity represents
        merged["original_ids"] = [entities[0].get("id")]
        
        # Merge attributes from other entities
        for entity in entities[1:]:
            # Add original ID
            if "id" in entity:
                merged["original_ids"].append(entity["id"])
            
            # Merge other attributes
            for key, value in entity.items():
                if key not in merged or not merged[key]:
                    merged[key] = value
                elif key == "description" and value and value != merged[key]:
                    # Concatenate descriptions
                    merged[key] = f"{merged[key]}; {value}"
        
        return merged


class RelationshipAggregator:
    """Aggregates relationships from multiple sources."""
    
    def __init__(self):
        """Initialize the relationship aggregator."""
        pass
    
    def aggregate(self, relationships: List[Dict[str, Any]], entity_id_map: Dict[Any, Any]) -> List[Dict[str, Any]]:
        """
        Aggregate relationships, updating entity references and removing duplicates.
        
        Args:
            relationships: List of relationships to aggregate
            entity_id_map: Mapping from original entity IDs to resolved entity IDs
            
        Returns:
            List of aggregated relationships
        """
        if not relationships:
            return []
        
        # Update entity references
        updated_relationships = []
        for rel in relationships:
            # Skip if source or target entity was removed during resolution
            if rel["source_id"] not in entity_id_map or rel["target_id"] not in entity_id_map:
                continue
            
            # Create updated relationship with resolved entity IDs
            updated_rel = rel.copy()
            updated_rel["source_id"] = entity_id_map[rel["source_id"]]
            updated_rel["target_id"] = entity_id_map[rel["target_id"]]
            
            # Skip self-relationships (after resolution)
            if updated_rel["source_id"] == updated_rel["target_id"]:
                continue
            
            updated_relationships.append(updated_rel)
        
        # Remove duplicate relationships
        aggregated = self._remove_duplicates(updated_relationships)
        
        return aggregated
    
    def _remove_duplicates(self, relationships: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate relationships.
        
        Args:
            relationships: List of relationships to deduplicate
            
        Returns:
            List of unique relationships
        """
        # Use a set to track unique relationship keys
        unique_keys = set()
        unique_relationships = []
        
        for rel in relationships:
            # Create a key for the relationship
            key = (rel["source_id"], rel["target_id"], rel["type"])
            
            if key not in unique_keys:
                unique_keys.add(key)
                unique_relationships.append(rel)
        
        return unique_relationships


class GraphSynthesizer:
    """Synthesizes the knowledge graph from entities and relationships."""
    
    def __init__(self):
        """Initialize the graph synthesizer."""
        self.graph = nx.DiGraph()
    
    def synthesize(self, entities: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> nx.DiGraph:
        """
        Synthesize a knowledge graph from entities and relationships.
        
        Args:
            entities: List of entities to add as nodes
            relationships: List of relationships to add as edges
            
        Returns:
            NetworkX DiGraph representing the knowledge graph
        """
        # Create a new graph
        self.graph = nx.DiGraph()
        
        # Add entities as nodes
        for entity in entities:
            self.graph.add_node(
                entity["id"],
                name=entity.get("name", ""),
                type=entity.get("type", ""),
                description=entity.get("description", ""),
                layer=entity.get("layer", "Raw"),
                attributes={k: v for k, v in entity.items() if k not in ["id", "name", "type", "description", "layer"]}
            )
        
        # Add relationships as edges
        for rel in relationships:
            self.graph.add_edge(
                rel["source_id"],
                rel["target_id"],
                type=rel["type"],
                description=rel.get("description", ""),
                attributes={k: v for k, v in rel.items() if k not in ["source_id", "target_id", "type", "description"]}
            )
        
        return self.graph
    
    def get_graph(self) -> nx.DiGraph:
        """
        Get the synthesized knowledge graph.
        
        Returns:
            NetworkX DiGraph representing the knowledge graph
        """
        return self.graph
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the knowledge graph.
        
        Returns:
            Dictionary of graph statistics
        """
        stats = {
            "num_nodes": self.graph.number_of_nodes(),
            "num_edges": self.graph.number_of_edges(),
            "node_types": defaultdict(int),
            "edge_types": defaultdict(int),
            "avg_degree": sum(dict(self.graph.degree()).values()) / max(1, self.graph.number_of_nodes())
        }
        
        # Count node types
        for node, data in self.graph.nodes(data=True):
            node_type = data.get("type", "Unknown")
            stats["node_types"][node_type] += 1
        
        # Count edge types
        for _, _, data in self.graph.edges(data=True):
            edge_type = data.get("type", "Unknown")
            stats["edge_types"][edge_type] += 1
        
        return stats


class KnowledgeReducer:
    """Implements the reducing phase of KnowledgeReduce."""
    
    def __init__(self):
        """Initialize the knowledge reducer."""
        self.entity_resolver = EntityResolver()
        self.relationship_aggregator = RelationshipAggregator()
        self.graph_synthesizer = GraphSynthesizer()
    
    def reduce(self, entities: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], nx.DiGraph]:
        """
        Reduce mapped knowledge by resolving entities, aggregating relationships, and synthesizing the graph.
        
        Args:
            entities: List of entities from the mapping phase
            relationships: List of relationships from the mapping phase
            
        Returns:
            Tuple of (resolved_entities, aggregated_relationships, knowledge_graph)
        """
        # Resolve entities
        resolved_entities = self.entity_resolver.resolve(entities)
        
        # Create mapping from original entity IDs to resolved entity IDs
        entity_id_map = {}
        for entity in resolved_entities:
            for original_id in entity.get("original_ids", [entity["id"]]):
                entity_id_map[original_id] = entity["id"]
        
        # Aggregate relationships
        aggregated_relationships = self.relationship_aggregator.aggregate(relationships, entity_id_map)
        
        # Synthesize knowledge graph
        knowledge_graph = self.graph_synthesizer.synthesize(resolved_entities, aggregated_relationships)
        
        return resolved_entities, aggregated_relationships, knowledge_graph


if __name__ == "__main__":
    # Test the module
    from data_ingestion import DataIngestionPipeline, create_sample_data
    from knowledge_mapping import KnowledgeMapper
    
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
    
    print(f"Reduced {len(entities)} entities to {len(resolved_entities)} entities")
    print(f"Reduced {len(relationships)} relationships to {len(aggregated_relationships)} relationships")
    
    # Print graph statistics
    stats = reducer.graph_synthesizer.get_statistics()
    print(f"Graph statistics: {stats}")
