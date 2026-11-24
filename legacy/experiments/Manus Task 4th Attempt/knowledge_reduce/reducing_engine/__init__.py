"""
Reducing Engine module for KnowledgeReduce.

This module handles the aggregation of entity and relationship data, conflict resolution,
and construction of the knowledge graph for the KnowledgeReduce framework.
"""

from typing import Dict, List, Any, Optional
import os
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ReducingEngine:
    """
    Engine for the reducing phase in the KnowledgeReduce framework.
    
    This class handles the aggregation of entity and relationship data, conflict resolution,
    and construction of the knowledge graph.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the ReducingEngine.
        
        Args:
            config: Optional configuration dictionary for customizing reducing behavior.
        """
        self.config = config or {}
        self.conflict_resolvers = []
        self.graph_synthesizers = []
        logger.info("ReducingEngine initialized")
    
    def register_conflict_resolver(self, resolver):
        """
        Register a conflict resolver.
        
        Args:
            resolver: A conflict resolver object that implements a resolve method.
        """
        self.conflict_resolvers.append(resolver)
        logger.info(f"Registered conflict resolver: {resolver.__class__.__name__}")
        return resolver
    
    def register_graph_synthesizer(self, synthesizer):
        """
        Register a graph synthesizer.
        
        Args:
            synthesizer: A graph synthesizer object that implements a synthesize method.
        """
        self.graph_synthesizers.append(synthesizer)
        logger.info(f"Registered graph synthesizer: {synthesizer.__class__.__name__}")
        return synthesizer
    
    def reduce(self, mapped_data: Dict[str, Any]):
        """
        Reduce mapped data to a knowledge graph.
        
        Args:
            mapped_data: Dictionary containing entities and relationships from the mapping phase.
            
        Returns:
            Dictionary containing the reduced knowledge graph data.
        """
        logger.info("Starting reducing phase")
        
        entities = mapped_data.get('entities', [])
        relationships = mapped_data.get('relationships', [])
        
        # Aggregate entities and resolve conflicts
        aggregated_entities = self._aggregate_entities(entities)
        
        # Aggregate relationships and resolve conflicts
        aggregated_relationships = self._aggregate_relationships(relationships, aggregated_entities)
        
        # Synthesize the knowledge graph
        graph_data = self._synthesize_graph(aggregated_entities, aggregated_relationships)
        
        logger.info(f"Reducing phase completed: {len(aggregated_entities)} entities, {len(aggregated_relationships)} relationships")
        
        return {
            'entities': aggregated_entities,
            'relationships': aggregated_relationships,
            'graph': graph_data
        }
    
    def _aggregate_entities(self, entities):
        """
        Aggregate entities and resolve conflicts.
        
        Args:
            entities: List of entities to aggregate.
            
        Returns:
            List of aggregated entities.
        """
        logger.info(f"Aggregating {len(entities)} entities")
        
        # Group entities by ID
        entities_by_id = {}
        for entity in entities:
            entity_id = entity.get('id')
            if entity_id not in entities_by_id:
                entities_by_id[entity_id] = []
            entities_by_id[entity_id].append(entity)
        
        # Aggregate entities with the same ID
        aggregated_entities = []
        for entity_id, id_entities in entities_by_id.items():
            if len(id_entities) == 1:
                # No aggregation needed
                aggregated_entities.append(id_entities[0])
            else:
                # Resolve conflicts and aggregate
                aggregated_entity = self._resolve_entity_conflicts(id_entities)
                aggregated_entities.append(aggregated_entity)
        
        return aggregated_entities
    
    def _resolve_entity_conflicts(self, entities):
        """
        Resolve conflicts between entities with the same ID.
        
        Args:
            entities: List of entities with the same ID.
            
        Returns:
            Aggregated entity with conflicts resolved.
        """
        # Start with the first entity
        aggregated = entities[0].copy()
        
        # Apply conflict resolvers
        for resolver in self.conflict_resolvers:
            try:
                aggregated = resolver.resolve_entity_conflicts(entities, aggregated)
            except Exception as e:
                logger.error(f"Error resolving entity conflicts with {resolver.__class__.__name__}: {str(e)}")
        
        return aggregated
    
    def _aggregate_relationships(self, relationships, entities):
        """
        Aggregate relationships and resolve conflicts.
        
        Args:
            relationships: List of relationships to aggregate.
            entities: List of aggregated entities.
            
        Returns:
            List of aggregated relationships.
        """
        logger.info(f"Aggregating {len(relationships)} relationships")
        
        # Create a set of valid entity IDs
        valid_entity_ids = {entity.get('id') for entity in entities}
        
        # Filter relationships with valid source and target entities
        valid_relationships = []
        for relationship in relationships:
            source_id = relationship.get('source')
            target_id = relationship.get('target')
            
            if source_id in valid_entity_ids and target_id in valid_entity_ids:
                valid_relationships.append(relationship)
            else:
                logger.warning(f"Skipping relationship with invalid source or target: {source_id} -> {target_id}")
        
        # Group relationships by source, target, and type
        relationships_by_key = {}
        for relationship in valid_relationships:
            source_id = relationship.get('source')
            target_id = relationship.get('target')
            rel_type = relationship.get('type')
            
            key = f"{source_id}|{rel_type}|{target_id}"
            if key not in relationships_by_key:
                relationships_by_key[key] = []
            relationships_by_key[key].append(relationship)
        
        # Aggregate relationships with the same key
        aggregated_relationships = []
        for key, key_relationships in relationships_by_key.items():
            if len(key_relationships) == 1:
                # No aggregation needed
                aggregated_relationships.append(key_relationships[0])
            else:
                # Resolve conflicts and aggregate
                aggregated_relationship = self._resolve_relationship_conflicts(key_relationships)
                aggregated_relationships.append(aggregated_relationship)
        
        return aggregated_relationships
    
    def _resolve_relationship_conflicts(self, relationships):
        """
        Resolve conflicts between relationships with the same source, target, and type.
        
        Args:
            relationships: List of relationships with the same source, target, and type.
            
        Returns:
            Aggregated relationship with conflicts resolved.
        """
        # Start with the first relationship
        aggregated = relationships[0].copy()
        
        # Apply conflict resolvers
        for resolver in self.conflict_resolvers:
            try:
                aggregated = resolver.resolve_relationship_conflicts(relationships, aggregated)
            except Exception as e:
                logger.error(f"Error resolving relationship conflicts with {resolver.__class__.__name__}: {str(e)}")
        
        return aggregated
    
    def _synthesize_graph(self, entities, relationships):
        """
        Synthesize the knowledge graph from entities and relationships.
        
        Args:
            entities: List of aggregated entities.
            relationships: List of aggregated relationships.
            
        Returns:
            Dictionary containing the synthesized graph data.
        """
        logger.info("Synthesizing knowledge graph")
        
        graph_data = {
            'nodes': [],
            'edges': []
        }
        
        # Convert entities to nodes
        for entity in entities:
            node = {
                'id': entity.get('id'),
                'label': entity.get('text'),
                'type': entity.get('type'),
                'properties': {}
            }
            
            # Add entity properties to node
            for key, value in entity.items():
                if key not in ['id', 'text', 'type']:
                    node['properties'][key] = value
            
            graph_data['nodes'].append(node)
        
        # Convert relationships to edges
        for relationship in relationships:
            edge = {
                'id': relationship.get('id'),
                'source': relationship.get('source'),
                'target': relationship.get('target'),
                'label': relationship.get('type'),
                'properties': {}
            }
            
            # Add relationship properties to edge
            for key, value in relationship.items():
                if key not in ['id', 'source', 'target', 'type']:
                    edge['properties'][key] = value
            
            graph_data['edges'].append(edge)
        
        # Apply graph synthesizers
        for synthesizer in self.graph_synthesizers:
            try:
                graph_data = synthesizer.synthesize(graph_data)
            except Exception as e:
                logger.error(f"Error synthesizing graph with {synthesizer.__class__.__name__}: {str(e)}")
        
        return graph_data
    
    def save_state(self, path: str):
        """
        Save the current state of the ReducingEngine.
        
        Args:
            path: Directory path where the state will be saved.
        """
        os.makedirs(path, exist_ok=True)
        
        # Save configuration
        with open(os.path.join(path, 'config.json'), 'w') as f:
            json.dump(self.config, f, indent=2)
        
        logger.info(f"ReducingEngine state saved to {path}")
    
    def load_state(self, path: str):
        """
        Load a previously saved state of the ReducingEngine.
        
        Args:
            path: Directory path where the state was saved.
        """
        # Load configuration
        with open(os.path.join(path, 'config.json'), 'r') as f:
            self.config = json.load(f)
        
        logger.info(f"ReducingEngine state loaded from {path}")
