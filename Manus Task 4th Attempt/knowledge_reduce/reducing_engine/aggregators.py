"""
Aggregators and conflict resolvers for the KnowledgeReduce reducing engine.

This module provides classes for aggregating entities and relationships and resolving conflicts.
"""

from typing import Dict, List, Any, Optional
import logging
from abc import ABC, abstractmethod

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BaseAggregator(ABC):
    """Base class for all aggregators."""
    
    @abstractmethod
    def aggregate(self, entities, base_entity):
        """
        Aggregate multiple entities into one.
        
        Args:
            entities: List of entities to aggregate.
            base_entity: Base entity to aggregate into.
            
        Returns:
            Aggregated entity.
        """
        pass
    
    def aggregate_relationship(self, relationships, base_relationship):
        """
        Aggregate multiple relationships into one.
        
        Args:
            relationships: List of relationships to aggregate.
            base_relationship: Base relationship to aggregate into.
            
        Returns:
            Aggregated relationship.
        """
        pass


class SimpleAggregator(BaseAggregator):
    """Simple aggregator that combines entity attributes."""
    
    def __init__(self):
        """Initialize a SimpleAggregator."""
        logger.info("SimpleAggregator initialized")
    
    def aggregate(self, entities, base_entity):
        """
        Aggregate multiple entities into one.
        
        Args:
            entities: List of entities to aggregate.
            base_entity: Base entity to aggregate into.
            
        Returns:
            Aggregated entity.
        """
        if not entities:
            return base_entity
        
        logger.info(f"Aggregating {len(entities)} entities")
        
        aggregated = base_entity.copy()
        
        # Combine sources
        sources = set()
        if 'source' in aggregated and aggregated['source']:
            if isinstance(aggregated['source'], list):
                sources.update(aggregated['source'])
            else:
                sources.add(aggregated['source'])
        
        # Combine alternative texts
        alt_texts = set()
        if 'alternative_texts' in aggregated:
            alt_texts.update(aggregated['alternative_texts'])
        
        # Aggregate attributes from all entities
        for entity in entities[1:]:  # Skip the base entity (already copied)
            # Add source
            if 'source' in entity and entity['source']:
                if isinstance(entity['source'], list):
                    sources.update(entity['source'])
                else:
                    sources.add(entity['source'])
            
            # Add alternative text if different from main text
            if entity.get('text') != aggregated.get('text'):
                alt_texts.add(entity.get('text'))
            
            # Add alternative texts
            if 'alternative_texts' in entity:
                alt_texts.update(entity['alternative_texts'])
            
            # Update confidence to maximum
            if 'confidence' in entity and entity.get('confidence', 0) > aggregated.get('confidence', 0):
                aggregated['confidence'] = entity['confidence']
            
            # Combine other attributes
            for key, value in entity.items():
                if key not in ['id', 'text', 'source', 'confidence', 'alternative_texts']:
                    if key not in aggregated:
                        aggregated[key] = value
                    elif isinstance(aggregated[key], list) and isinstance(value, list):
                        # Combine lists
                        aggregated[key] = list(set(aggregated[key] + value))
                    elif isinstance(aggregated[key], dict) and isinstance(value, dict):
                        # Combine dictionaries
                        aggregated[key].update(value)
        
        # Update sources and alternative texts
        aggregated['source'] = list(sources) if sources else None
        if alt_texts:
            aggregated['alternative_texts'] = list(alt_texts)
        
        logger.info(f"Entity aggregation complete")
        return aggregated
    
    def aggregate_relationship(self, relationships, base_relationship):
        """
        Aggregate multiple relationships into one.
        
        Args:
            relationships: List of relationships to aggregate.
            base_relationship: Base relationship to aggregate into.
            
        Returns:
            Aggregated relationship.
        """
        if not relationships:
            return base_relationship
        
        logger.info(f"Aggregating {len(relationships)} relationships")
        
        aggregated = base_relationship.copy()
        
        # Combine sources
        sources = set()
        if 'data_source' in aggregated and aggregated['data_source']:
            if isinstance(aggregated['data_source'], list):
                sources.update(aggregated['data_source'])
            else:
                sources.add(aggregated['data_source'])
        
        # Aggregate attributes from all relationships
        for relationship in relationships[1:]:  # Skip the base relationship (already copied)
            # Add source
            if 'data_source' in relationship and relationship['data_source']:
                if isinstance(relationship['data_source'], list):
                    sources.update(relationship['data_source'])
                else:
                    sources.add(relationship['data_source'])
            
            # Update confidence to maximum
            if 'confidence' in relationship and relationship.get('confidence', 0) > aggregated.get('confidence', 0):
                aggregated['confidence'] = relationship['confidence']
            
            # Combine other attributes
            for key, value in relationship.items():
                if key not in ['id', 'source', 'target', 'type', 'data_source', 'confidence']:
                    if key not in aggregated:
                        aggregated[key] = value
                    elif isinstance(aggregated[key], list) and isinstance(value, list):
                        # Combine lists
                        aggregated[key] = list(set(aggregated[key] + value))
                    elif isinstance(aggregated[key], dict) and isinstance(value, dict):
                        # Combine dictionaries
                        aggregated[key].update(value)
        
        # Update sources
        aggregated['data_source'] = list(sources) if sources else None
        
        logger.info(f"Relationship aggregation complete")
        return aggregated


class WeightedAggregator(BaseAggregator):
    """Aggregator that uses weights based on confidence scores."""
    
    def __init__(self):
        """Initialize a WeightedAggregator."""
        logger.info("WeightedAggregator initialized")
    
    def aggregate(self, entities, base_entity):
        """
        Aggregate multiple entities into one using weighted approach.
        
        Args:
            entities: List of entities to aggregate.
            base_entity: Base entity to aggregate into.
            
        Returns:
            Aggregated entity.
        """
        if not entities:
            return base_entity
        
        logger.info(f"Aggregating {len(entities)} entities with weights")
        
        # Sort entities by confidence
        sorted_entities = sorted(entities, key=lambda e: e.get('confidence', 0), reverse=True)
        
        # Start with the highest confidence entity
        aggregated = sorted_entities[0].copy()
        
        # Combine sources
        sources = set()
        if 'source' in aggregated and aggregated['source']:
            if isinstance(aggregated['source'], list):
                sources.update(aggregated['source'])
            else:
                sources.add(aggregated['source'])
        
        # Combine alternative texts
        alt_texts = set()
        if 'alternative_texts' in aggregated:
            alt_texts.update(aggregated['alternative_texts'])
        
        # Aggregate attributes from other entities
        for entity in sorted_entities[1:]:
            # Add source
            if 'source' in entity and entity['source']:
                if isinstance(entity['source'], list):
                    sources.update(entity['source'])
                else:
                    sources.add(entity['source'])
            
            # Add alternative text if different from main text
            if entity.get('text') != aggregated.get('text'):
                alt_texts.add(entity.get('text'))
            
            # Add alternative texts
            if 'alternative_texts' in entity:
                alt_texts.update(entity['alternative_texts'])
            
            # Combine other attributes (only if not already present)
            for key, value in entity.items():
                if key not in ['id', 'text', 'source', 'confidence', 'alternative_texts']:
                    if key not in aggregated:
                        aggregated[key] = value
        
        # Update sources and alternative texts
        aggregated['source'] = list(sources) if sources else None
        if alt_texts:
            aggregated['alternative_texts'] = list(alt_texts)
        
        logger.info(f"Weighted entity aggregation complete")
        return aggregated
    
    def aggregate_relationship(self, relationships, base_relationship):
        """
        Aggregate multiple relationships into one using weighted approach.
        
        Args:
            relationships: List of relationships to aggregate.
            base_relationship: Base relationship to aggregate into.
            
        Returns:
            Aggregated relationship.
        """
        if not relationships:
            return base_relationship
        
        logger.info(f"Aggregating {len(relationships)} relationships with weights")
        
        # Sort relationships by confidence
        sorted_relationships = sorted(relationships, key=lambda r: r.get('confidence', 0), reverse=True)
        
        # Start with the highest confidence relationship
        aggregated = sorted_relationships[0].copy()
        
        # Combine sources
        sources = set()
        if 'data_source' in aggregated and aggregated['data_source']:
            if isinstance(aggregated['data_source'], list):
                sources.update(aggregated['data_source'])
            else:
                sources.add(aggregated['data_source'])
        
        # Aggregate attributes from other relationships
        for relationship in sorted_relationships[1:]:
            # Add source
            if 'data_source' in relationship and relationship['data_source']:
                if isinstance(relationship['data_source'], list):
                    sources.update(relationship['data_source'])
                else:
                    sources.add(relationship['data_source'])
            
            # Combine other attributes (only if not already present)
            for key, value in relationship.items():
                if key not in ['id', 'source', 'target', 'type', 'data_source', 'confidence']:
                    if key not in aggregated:
                        aggregated[key] = value
        
        # Update sources
        aggregated['data_source'] = list(sources) if sources else None
        
        logger.info(f"Weighted relationship aggregation complete")
        return aggregated


class BaseConflictResolver(ABC):
    """Base class for all conflict resolvers."""
    
    @abstractmethod
    def resolve(self, entities):
        """
        Resolve conflicts in entities.
        
        Args:
            entities: List of entities to resolve conflicts in.
            
        Returns:
            List of entities with conflicts resolved.
        """
        pass


class SourcePriorityConflictResolver(BaseConflictResolver):
    """Conflict resolver that prioritizes sources."""
    
    def __init__(self, source_priorities=None):
        """
        Initialize a SourcePriorityConflictResolver.
        
        Args:
            source_priorities: Dictionary mapping source names to priority values.
        """
        self.source_priorities = source_priorities or {}
        logger.info(f"SourcePriorityConflictResolver initialized with {len(self.source_priorities)} priorities")
    
    def set_source_priority(self, source, priority):
        """
        Set the priority for a source.
        
        Args:
            source: Source name.
            priority: Priority value (higher is more trusted).
        """
        self.source_priorities[source] = priority
        logger.info(f"Set priority {priority} for source: {source}")
    
    def resolve(self, entities):
        """
        Resolve conflicts in entities based on source priorities.
        
        Args:
            entities: List of entities to resolve conflicts in.
            
        Returns:
            List of entities with conflicts resolved.
        """
        if not entities:
            return []
        
        logger.info(f"Resolving conflicts in {len(entities)} entities based on source priorities")
        
        resolved_entities = []
        
        for entity in entities:
            # Resolve conflicts in multi-valued attributes
            resolved_entity = entity.copy()
            
            # Resolve source conflicts
            if 'source' in resolved_entity and isinstance(resolved_entity['source'], list) and len(resolved_entity['source']) > 1:
                # Sort sources by priority
                sorted_sources = sorted(
                    resolved_entity['source'],
                    key=lambda s: self.source_priorities.get(s, 0),
                    reverse=True
                )
                
                # Keep all sources but mark the highest priority one
                resolved_entity['source'] = sorted_sources
                resolved_entity['primary_source'] = sorted_sources[0]
            
            resolved_entities.append(resolved_entity)
        
        logger.info(f"Conflict resolution complete based on source priorities")
        return resolved_entities


class ConfidenceBasedConflictResolver(BaseConflictResolver):
    """Conflict resolver that uses confidence scores."""
    
    def __init__(self):
        """Initialize a ConfidenceBasedConflictResolver."""
        logger.info("ConfidenceBasedConflictResolver initialized")
    
    def resolve(self, entities):
        """
        Resolve conflicts in entities based on confidence scores.
        
        Args:
            entities: List of entities to resolve conflicts in.
            
        Returns:
            List of entities with conflicts resolved.
        """
        if not entities:
            return []
        
        logger.info(f"Resolving conflicts in {len(entities)} entities based on confidence scores")
        
        resolved_entities = []
        
        for entity in entities:
            # Resolve conflicts in multi-valued attributes
            resolved_entity = entity.copy()
            
            # No specific conflicts to resolve in this implementation
            # This is a placeholder for more complex conflict resolution logic
            
            resolved_entities.append(resolved_entity)
        
        logger.info(f"Conflict resolution complete based on confidence scores")
        return resolved_entities
