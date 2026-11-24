"""
Conflict resolvers for the KnowledgeReduce reducing engine.

This module provides classes for resolving conflicts between entities and relationships
during the reducing phase of the KnowledgeReduce framework.
"""

from typing import Dict, List, Any, Optional
import logging
from abc import ABC, abstractmethod

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BaseConflictResolver(ABC):
    """Base class for all conflict resolvers."""
    
    @abstractmethod
    def resolve_entity_conflicts(self, entities, aggregated):
        """
        Resolve conflicts between entities with the same ID.
        
        Args:
            entities: List of entities with the same ID.
            aggregated: Initial aggregated entity.
            
        Returns:
            Aggregated entity with conflicts resolved.
        """
        pass
    
    @abstractmethod
    def resolve_relationship_conflicts(self, relationships, aggregated):
        """
        Resolve conflicts between relationships with the same source, target, and type.
        
        Args:
            relationships: List of relationships with the same source, target, and type.
            aggregated: Initial aggregated relationship.
            
        Returns:
            Aggregated relationship with conflicts resolved.
        """
        pass


class ConfidenceBasedResolver(BaseConflictResolver):
    """Conflict resolver that uses confidence scores to resolve conflicts."""
    
    def __init__(self):
        """Initialize a ConfidenceBasedResolver."""
        logger.info("ConfidenceBasedResolver initialized")
    
    def resolve_entity_conflicts(self, entities, aggregated):
        """
        Resolve conflicts between entities based on confidence scores.
        
        Args:
            entities: List of entities with the same ID.
            aggregated: Initial aggregated entity.
            
        Returns:
            Aggregated entity with conflicts resolved.
        """
        # Sort entities by confidence (highest first)
        sorted_entities = sorted(
            entities,
            key=lambda e: e.get('confidence', 0),
            reverse=True
        )
        
        # Use the entity with highest confidence as the base
        highest_confidence_entity = sorted_entities[0]
        
        # Start with a copy of the highest confidence entity
        resolved = highest_confidence_entity.copy()
        
        # Collect alternative texts from all entities
        alternative_texts = set()
        for entity in entities:
            if entity.get('text') != resolved.get('text'):
                alternative_texts.add(entity.get('text'))
            
            # Add any existing alternative texts
            if 'alternative_texts' in entity:
                if isinstance(entity['alternative_texts'], list):
                    alternative_texts.update(entity['alternative_texts'])
                else:
                    alternative_texts.add(entity['alternative_texts'])
        
        # Set alternative texts
        if alternative_texts:
            resolved['alternative_texts'] = list(alternative_texts)
        
        # Collect sources from all entities
        sources = set()
        for entity in entities:
            if 'source' in entity and entity['source']:
                if isinstance(entity['source'], list):
                    sources.update(entity['source'])
                else:
                    sources.add(entity['source'])
        
        # Set sources
        if sources:
            resolved['sources'] = list(sources)
        
        return resolved
    
    def resolve_relationship_conflicts(self, relationships, aggregated):
        """
        Resolve conflicts between relationships based on confidence scores.
        
        Args:
            relationships: List of relationships with the same source, target, and type.
            aggregated: Initial aggregated relationship.
            
        Returns:
            Aggregated relationship with conflicts resolved.
        """
        # Sort relationships by confidence (highest first)
        sorted_relationships = sorted(
            relationships,
            key=lambda r: r.get('confidence', 0),
            reverse=True
        )
        
        # Use the relationship with highest confidence as the base
        highest_confidence_rel = sorted_relationships[0]
        
        # Start with a copy of the highest confidence relationship
        resolved = highest_confidence_rel.copy()
        
        # Collect sources from all relationships
        sources = set()
        for rel in relationships:
            if 'data_source' in rel and rel['data_source']:
                if isinstance(rel['data_source'], list):
                    sources.update(rel['data_source'])
                else:
                    sources.add(rel['data_source'])
        
        # Set sources
        if sources:
            resolved['data_sources'] = list(sources)
        
        # Calculate average confidence
        total_confidence = sum(rel.get('confidence', 0) for rel in relationships)
        avg_confidence = total_confidence / len(relationships)
        resolved['confidence'] = avg_confidence
        
        return resolved


class MajorityVotingResolver(BaseConflictResolver):
    """Conflict resolver that uses majority voting to resolve conflicts."""
    
    def __init__(self):
        """Initialize a MajorityVotingResolver."""
        logger.info("MajorityVotingResolver initialized")
    
    def resolve_entity_conflicts(self, entities, aggregated):
        """
        Resolve conflicts between entities based on majority voting.
        
        Args:
            entities: List of entities with the same ID.
            aggregated: Initial aggregated entity.
            
        Returns:
            Aggregated entity with conflicts resolved.
        """
        # Count occurrences of each text
        text_counts = {}
        for entity in entities:
            text = entity.get('text', '')
            if text not in text_counts:
                text_counts[text] = 0
            text_counts[text] += 1
        
        # Find the most common text
        most_common_text = max(text_counts.items(), key=lambda x: x[1])[0]
        
        # Start with a copy of the aggregated entity
        resolved = aggregated.copy()
        
        # Set the most common text
        resolved['text'] = most_common_text
        
        # Collect alternative texts (all texts except the most common one)
        alternative_texts = set()
        for text in text_counts.keys():
            if text != most_common_text:
                alternative_texts.add(text)
        
        # Add existing alternative texts
        for entity in entities:
            if 'alternative_texts' in entity:
                if isinstance(entity['alternative_texts'], list):
                    alternative_texts.update(entity['alternative_texts'])
                else:
                    alternative_texts.add(entity['alternative_texts'])
        
        # Set alternative texts
        if alternative_texts:
            resolved['alternative_texts'] = list(alternative_texts)
        
        # Collect sources from all entities
        sources = set()
        for entity in entities:
            if 'source' in entity and entity['source']:
                if isinstance(entity['source'], list):
                    sources.update(entity['source'])
                else:
                    sources.add(entity['source'])
        
        # Set sources
        if sources:
            resolved['sources'] = list(sources)
        
        return resolved
    
    def resolve_relationship_conflicts(self, relationships, aggregated):
        """
        Resolve conflicts between relationships based on majority voting.
        
        Args:
            relationships: List of relationships with the same source, target, and type.
            aggregated: Initial aggregated relationship.
            
        Returns:
            Aggregated relationship with conflicts resolved.
        """
        # For relationships, there's not much to vote on since they have the same source, target, and type
        # Just collect sources and calculate average confidence
        
        # Start with a copy of the aggregated relationship
        resolved = aggregated.copy()
        
        # Collect sources from all relationships
        sources = set()
        for rel in relationships:
            if 'data_source' in rel and rel['data_source']:
                if isinstance(rel['data_source'], list):
                    sources.update(rel['data_source'])
                else:
                    sources.add(rel['data_source'])
        
        # Set sources
        if sources:
            resolved['data_sources'] = list(sources)
        
        # Calculate average confidence
        total_confidence = sum(rel.get('confidence', 0) for rel in relationships)
        avg_confidence = total_confidence / len(relationships)
        resolved['confidence'] = avg_confidence
        
        return resolved


class SourcePriorityResolver(BaseConflictResolver):
    """Conflict resolver that uses source priorities to resolve conflicts."""
    
    def __init__(self, source_priorities=None):
        """
        Initialize a SourcePriorityResolver.
        
        Args:
            source_priorities: Dictionary mapping source names to priority values (higher is better).
        """
        self.source_priorities = source_priorities or {}
        logger.info(f"SourcePriorityResolver initialized with {len(self.source_priorities)} priorities")
    
    def set_source_priority(self, source, priority):
        """
        Set the priority for a source.
        
        Args:
            source: Source name.
            priority: Priority value (higher is better).
        """
        self.source_priorities[source] = priority
        logger.info(f"Set priority {priority} for source: {source}")
    
    def resolve_entity_conflicts(self, entities, aggregated):
        """
        Resolve conflicts between entities based on source priorities.
        
        Args:
            entities: List of entities with the same ID.
            aggregated: Initial aggregated entity.
            
        Returns:
            Aggregated entity with conflicts resolved.
        """
        # Calculate priority for each entity
        entity_priorities = []
        for entity in entities:
            priority = 0
            source = entity.get('source')
            
            if source:
                if isinstance(source, list):
                    # If multiple sources, use the highest priority
                    priority = max(self.source_priorities.get(s, 0) for s in source)
                else:
                    priority = self.source_priorities.get(source, 0)
            
            entity_priorities.append((entity, priority))
        
        # Sort entities by priority (highest first)
        sorted_entities = sorted(entity_priorities, key=lambda x: x[1], reverse=True)
        
        # Use the entity with highest priority as the base
        highest_priority_entity = sorted_entities[0][0]
        
        # Start with a copy of the highest priority entity
        resolved = highest_priority_entity.copy()
        
        # Collect alternative texts from all entities
        alternative_texts = set()
        for entity, _ in sorted_entities:
            if entity.get('text') != resolved.get('text'):
                alternative_texts.add(entity.get('text'))
            
            # Add any existing alternative texts
            if 'alternative_texts' in entity:
                if isinstance(entity['alternative_texts'], list):
                    alternative_texts.update(entity['alternative_texts'])
                else:
                    alternative_texts.add(entity['alternative_texts'])
        
        # Set alternative texts
        if alternative_texts:
            resolved['alternative_texts'] = list(alternative_texts)
        
        # Collect sources from all entities
        sources = set()
        for entity, _ in sorted_entities:
            if 'source' in entity and entity['source']:
                if isinstance(entity['source'], list):
                    sources.update(entity['source'])
                else:
                    sources.add(entity['source'])
        
        # Set sources
        if sources:
            resolved['sources'] = list(sources)
        
        return resolved
    
    def resolve_relationship_conflicts(self, relationships, aggregated):
        """
        Resolve conflicts between relationships based on source priorities.
        
        Args:
            relationships: List of relationships with the same source, target, and type.
            aggregated: Initial aggregated relationship.
            
        Returns:
            Aggregated relationship with conflicts resolved.
        """
        # Calculate priority for each relationship
        rel_priorities = []
        for rel in relationships:
            priority = 0
            source = rel.get('data_source')
            
            if source:
                if isinstance(source, list):
                    # If multiple sources, use the highest priority
                    priority = max(self.source_priorities.get(s, 0) for s in source)
                else:
                    priority = self.source_priorities.get(source, 0)
            
            rel_priorities.append((rel, priority))
        
        # Sort relationships by priority (highest first)
        sorted_rels = sorted(rel_priorities, key=lambda x: x[1], reverse=True)
        
        # Use the relationship with highest priority as the base
        highest_priority_rel = sorted_rels[0][0]
        
        # Start with a copy of the highest priority relationship
        resolved = highest_priority_rel.copy()
        
        # Collect sources from all relationships
        sources = set()
        for rel, _ in sorted_rels:
            if 'data_source' in rel and rel['data_source']:
                if isinstance(rel['data_source'], list):
                    sources.update(rel['data_source'])
                else:
                    sources.add(rel['data_source'])
        
        # Set sources
        if sources:
            resolved['data_sources'] = list(sources)
        
        return resolved
