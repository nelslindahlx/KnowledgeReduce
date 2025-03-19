"""
Disambiguation engine for the KnowledgeReduce mapping engine.

This module provides classes for disambiguating entities extracted from data.
"""

from typing import Dict, List, Any, Optional
import logging
from abc import ABC, abstractmethod

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BaseDisambiguationEngine(ABC):
    """Base class for all disambiguation engines."""
    
    @abstractmethod
    def disambiguate(self, entities):
        """
        Disambiguate entities.
        
        Args:
            entities: List of entities to disambiguate.
            
        Returns:
            List of disambiguated entities.
        """
        pass


class SimpleDisambiguationEngine(BaseDisambiguationEngine):
    """Simple disambiguation engine based on text and type matching."""
    
    def __init__(self, threshold=0.8):
        """
        Initialize a SimpleDisambiguationEngine.
        
        Args:
            threshold: Similarity threshold for considering entities as the same.
        """
        self.threshold = threshold
        logger.info(f"SimpleDisambiguationEngine initialized with threshold: {threshold}")
    
    def disambiguate(self, entities):
        """
        Disambiguate entities based on text and type similarity.
        
        Args:
            entities: List of entities to disambiguate.
            
        Returns:
            List of disambiguated entities.
        """
        if not entities:
            return []
        
        logger.info(f"Disambiguating {len(entities)} entities")
        
        # Group entities by type
        entities_by_type = {}
        for entity in entities:
            entity_type = entity.get('type', 'unknown')
            if entity_type not in entities_by_type:
                entities_by_type[entity_type] = []
            entities_by_type[entity_type].append(entity)
        
        # Disambiguate entities within each type
        disambiguated_entities = []
        for entity_type, type_entities in entities_by_type.items():
            # Sort entities by confidence (if available)
            sorted_entities = sorted(
                type_entities,
                key=lambda e: e.get('confidence', 0),
                reverse=True
            )
            
            # Keep track of which entities have been merged
            merged = set()
            
            for i, entity1 in enumerate(sorted_entities):
                if i in merged:
                    continue
                
                # Create a new disambiguated entity
                disambiguated_entity = entity1.copy()
                
                # Find similar entities and merge them
                for j, entity2 in enumerate(sorted_entities):
                    if i == j or j in merged:
                        continue
                    
                    if self._are_similar(entity1, entity2):
                        # Merge entity2 into disambiguated_entity
                        self._merge_entities(disambiguated_entity, entity2)
                        merged.add(j)
                
                disambiguated_entities.append(disambiguated_entity)
        
        logger.info(f"Disambiguation complete: {len(entities)} entities reduced to {len(disambiguated_entities)}")
        return disambiguated_entities
    
    def _are_similar(self, entity1, entity2):
        """
        Check if two entities are similar enough to be considered the same.
        
        Args:
            entity1: First entity.
            entity2: Second entity.
            
        Returns:
            True if entities are similar, False otherwise.
        """
        # Check if entities have the same type
        if entity1.get('type') != entity2.get('type'):
            return False
        
        # Check if entities have similar text
        text1 = entity1.get('text', '').lower()
        text2 = entity2.get('text', '').lower()
        
        # Simple string similarity (can be replaced with more sophisticated methods)
        if text1 == text2:
            return True
        
        # Check if one is a substring of the other
        if text1 in text2 or text2 in text1:
            return True
        
        return False
    
    def _merge_entities(self, target, source):
        """
        Merge source entity into target entity.
        
        Args:
            target: Target entity to merge into.
            source: Source entity to merge from.
        """
        # Update confidence if source has higher confidence
        if source.get('confidence', 0) > target.get('confidence', 0):
            target['confidence'] = source['confidence']
        
        # Add alternative text if different
        if source.get('text') != target.get('text'):
            if 'alternative_texts' not in target:
                target['alternative_texts'] = []
            target['alternative_texts'].append(source['text'])
        
        # Add source to sources list
        if 'sources' not in target:
            target['sources'] = [target.get('source')]
        
        source_source = source.get('source')
        if source_source and source_source not in target['sources']:
            target['sources'].append(source_source)
        
        # Merge any additional fields
        for key, value in source.items():
            if key not in ['id', 'text', 'type', 'confidence', 'source', 'start', 'end']:
                if key not in target:
                    target[key] = value
                elif isinstance(target[key], list) and isinstance(value, list):
                    target[key].extend(value)


class ContextualDisambiguationEngine(BaseDisambiguationEngine):
    """Disambiguation engine that uses context for entity disambiguation."""
    
    def __init__(self, context_window=100):
        """
        Initialize a ContextualDisambiguationEngine.
        
        Args:
            context_window: Size of the context window to consider.
        """
        self.context_window = context_window
        logger.info(f"ContextualDisambiguationEngine initialized with context window: {context_window}")
    
    def disambiguate(self, entities):
        """
        Disambiguate entities based on their context.
        
        Args:
            entities: List of entities to disambiguate.
            
        Returns:
            List of disambiguated entities.
        """
        if not entities:
            return []
        
        logger.info(f"Disambiguating {len(entities)} entities using context")
        
        # Group entities by text (case-insensitive)
        entities_by_text = {}
        for entity in entities:
            text = entity.get('text', '').lower()
            if text not in entities_by_text:
                entities_by_text[text] = []
            entities_by_text[text].append(entity)
        
        # Disambiguate entities with the same text
        disambiguated_entities = []
        for text, text_entities in entities_by_text.items():
            # If there's only one entity with this text, no disambiguation needed
            if len(text_entities) == 1:
                disambiguated_entities.append(text_entities[0])
                continue
            
            # Group by type
            entities_by_type = {}
            for entity in text_entities:
                entity_type = entity.get('type', 'unknown')
                if entity_type not in entities_by_type:
                    entities_by_type[entity_type] = []
                entities_by_type[entity_type].append(entity)
            
            # For each type, create a disambiguated entity
            for entity_type, type_entities in entities_by_type.items():
                # Create a new disambiguated entity from the first one
                disambiguated_entity = type_entities[0].copy()
                
                # Merge the rest
                for entity in type_entities[1:]:
                    self._merge_entities(disambiguated_entity, entity)
                
                disambiguated_entities.append(disambiguated_entity)
        
        logger.info(f"Contextual disambiguation complete: {len(entities)} entities reduced to {len(disambiguated_entities)}")
        return disambiguated_entities
    
    def _merge_entities(self, target, source):
        """
        Merge source entity into target entity.
        
        Args:
            target: Target entity to merge into.
            source: Source entity to merge from.
        """
        # Update confidence if source has higher confidence
        if source.get('confidence', 0) > target.get('confidence', 0):
            target['confidence'] = source['confidence']
        
        # Add source to sources list
        if 'sources' not in target:
            target['sources'] = [target.get('source')]
        
        source_source = source.get('source')
        if source_source and source_source not in target['sources']:
            target['sources'].append(source_source)
        
        # Merge contexts
        if 'context' not in target:
            target['context'] = []
        
        if 'start' in source and 'end' in source and 'data' in source:
            context_start = max(0, source['start'] - self.context_window)
            context_end = min(len(source['data']), source['end'] + self.context_window)
            context = source['data'][context_start:context_end]
            target['context'].append(context)
        
        # Merge any additional fields
        for key, value in source.items():
            if key not in ['id', 'text', 'type', 'confidence', 'source', 'start', 'end', 'data', 'context']:
                if key not in target:
                    target[key] = value
                elif isinstance(target[key], list) and isinstance(value, list):
                    target[key].extend(value)
