"""
Relationship extractors for the KnowledgeReduce mapping engine.

This module provides classes for extracting relationships between entities from various data formats.
"""

from typing import Dict, List, Any, Optional
import logging
import re
import spacy
from abc import ABC, abstractmethod

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BaseRelationshipExtractor(ABC):
    """Base class for all relationship extractors."""
    
    @abstractmethod
    def extract(self, data, entities, context=None):
        """
        Extract relationships from data.
        
        Args:
            data: Data to extract relationships from.
            entities: Entities extracted from the same data.
            context: Optional context information.
            
        Returns:
            List of extracted relationships.
        """
        pass


class NLPRelationshipExtractor(BaseRelationshipExtractor):
    """Relationship extractor using NLP techniques."""
    
    def __init__(self, model="en_core_web_sm"):
        """
        Initialize an NLPRelationshipExtractor.
        
        Args:
            model: spaCy model to use for dependency parsing.
        """
        try:
            self.nlp = spacy.load(model)
        except OSError:
            logger.info(f"Downloading spaCy model: {model}")
            spacy.cli.download(model)
            self.nlp = spacy.load(model)
        
        logger.info(f"NLPRelationshipExtractor initialized with model: {model}")
    
    def extract(self, data, entities, context=None):
        """
        Extract relationships from text data using NLP.
        
        Args:
            data: Text data to extract relationships from.
            entities: Entities extracted from the same data.
            context: Optional context information.
            
        Returns:
            List of extracted relationships.
        """
        if not isinstance(data, str):
            logger.warning("NLPRelationshipExtractor expects string data, got %s", type(data))
            return []
        
        if not entities:
            logger.warning("No entities provided for relationship extraction")
            return []
        
        logger.info("Extracting relationships using NLP")
        
        # Create a mapping of entity spans to entity IDs
        entity_spans = {}
        for entity in entities:
            if 'start' in entity and 'end' in entity:
                span = (entity['start'], entity['end'])
                entity_spans[span] = entity['id']
        
        doc = self.nlp(data)
        relationships = []
        
        # Extract subject-verb-object relationships
        for sent in doc.sents:
            for token in sent:
                # Check if token is a verb
                if token.pos_ == "VERB":
                    # Find subject
                    subjects = [child for child in token.children if child.dep_ in ("nsubj", "nsubjpass")]
                    # Find object
                    objects = [child for child in token.children if child.dep_ in ("dobj", "pobj", "attr")]
                    
                    for subj in subjects:
                        for obj in objects:
                            # Find entity IDs for subject and object
                            subj_entity_id = self._find_entity_for_token(subj, entity_spans)
                            obj_entity_id = self._find_entity_for_token(obj, entity_spans)
                            
                            if subj_entity_id and obj_entity_id:
                                relationship = {
                                    'id': f"rel_{len(relationships)}",
                                    'source': subj_entity_id,
                                    'target': obj_entity_id,
                                    'type': token.lemma_,
                                    'text': token.text,
                                    'data_source': context.get('source') if context else None,
                                    'confidence': 0.7  # Placeholder confidence score
                                }
                                relationships.append(relationship)
        
        logger.info(f"Extracted {len(relationships)} relationships using NLP")
        return relationships
    
    def _find_entity_for_token(self, token, entity_spans):
        """
        Find the entity ID for a token.
        
        Args:
            token: spaCy token.
            entity_spans: Mapping of entity spans to entity IDs.
            
        Returns:
            Entity ID if found, None otherwise.
        """
        # Check if token is part of an entity
        for span, entity_id in entity_spans.items():
            start, end = span
            if token.idx >= start and token.idx + len(token.text) <= end:
                return entity_id
        
        return None


class CooccurrenceRelationshipExtractor(BaseRelationshipExtractor):
    """Relationship extractor based on entity co-occurrence."""
    
    def __init__(self, window_size=50, relationship_type="co_occurs_with"):
        """
        Initialize a CooccurrenceRelationshipExtractor.
        
        Args:
            window_size: Size of the text window to consider for co-occurrence.
            relationship_type: Type to assign to the extracted relationships.
        """
        self.window_size = window_size
        self.relationship_type = relationship_type
        logger.info(f"CooccurrenceRelationshipExtractor initialized with window size: {window_size}")
    
    def extract(self, data, entities, context=None):
        """
        Extract relationships based on entity co-occurrence.
        
        Args:
            data: Text data to extract relationships from.
            entities: Entities extracted from the same data.
            context: Optional context information.
            
        Returns:
            List of extracted relationships.
        """
        if not isinstance(data, str):
            logger.warning("CooccurrenceRelationshipExtractor expects string data, got %s", type(data))
            return []
        
        if not entities:
            logger.warning("No entities provided for relationship extraction")
            return []
        
        logger.info("Extracting relationships based on co-occurrence")
        
        # Sort entities by their position in the text
        sorted_entities = sorted(
            [e for e in entities if 'start' in e and 'end' in e],
            key=lambda e: e['start']
        )
        
        relationships = []
        
        # Check for co-occurrence within the window
        for i, entity1 in enumerate(sorted_entities):
            for j in range(i + 1, len(sorted_entities)):
                entity2 = sorted_entities[j]
                
                # Check if entities are within the window
                if entity2['start'] - entity1['end'] <= self.window_size:
                    relationship = {
                        'id': f"rel_{len(relationships)}",
                        'source': entity1['id'],
                        'target': entity2['id'],
                        'type': self.relationship_type,
                        'data_source': context.get('source') if context else None,
                        'confidence': 0.6  # Placeholder confidence score
                    }
                    relationships.append(relationship)
                else:
                    # If we've gone beyond the window, no need to check further entities
                    break
        
        logger.info(f"Extracted {len(relationships)} relationships based on co-occurrence")
        return relationships


class StructuredDataRelationshipExtractor(BaseRelationshipExtractor):
    """Relationship extractor for structured data (JSON, CSV, etc.)."""
    
    def __init__(self, relationship_mappings=None):
        """
        Initialize a StructuredDataRelationshipExtractor.
        
        Args:
            relationship_mappings: Dictionary mapping data fields to relationship properties.
        """
        self.relationship_mappings = relationship_mappings or []
        logger.info(f"StructuredDataRelationshipExtractor initialized with {len(self.relationship_mappings)} mappings")
    
    def add_mapping(self, source_field, target_field, type_field=None, relationship_type=None):
        """
        Add a mapping for a relationship type.
        
        Args:
            source_field: Field to use as relationship source.
            target_field: Field to use as relationship target.
            type_field: Field to use as relationship type (optional).
            relationship_type: Static relationship type to use if type_field is not provided.
        """
        self.relationship_mappings.append({
            'source_field': source_field,
            'target_field': target_field,
            'type_field': type_field,
            'relationship_type': relationship_type
        })
        logger.info(f"Added relationship mapping: {source_field} -> {target_field}")
    
    def extract(self, data, entities, context=None):
        """
        Extract relationships from structured data.
        
        Args:
            data: Structured data to extract relationships from (list of dictionaries).
            entities: Entities extracted from the same data.
            context: Optional context information.
            
        Returns:
            List of extracted relationships.
        """
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            logger.warning("StructuredDataRelationshipExtractor expects list of dictionaries, got %s", type(data))
            return []
        
        if not entities:
            logger.warning("No entities provided for relationship extraction")
            return []
        
        logger.info("Extracting relationships from structured data")
        
        # Create a mapping of entity IDs to entity objects
        entity_map = {entity['id']: entity for entity in entities}
        
        relationships = []
        
        for item in data:
            for mapping in self.relationship_mappings:
                source_field = mapping['source_field']
                target_field = mapping['target_field']
                type_field = mapping['type_field']
                relationship_type = mapping['relationship_type']
                
                if source_field in item and target_field in item:
                    source_value = str(item[source_field])
                    target_value = str(item[target_field])
                    
                    # Find entities with matching values
                    source_entities = [e for e in entities if e.get('text') == source_value]
                    target_entities = [e for e in entities if e.get('text') == target_value]
                    
                    for source_entity in source_entities:
                        for target_entity in target_entities:
                            # Determine relationship type
                            rel_type = None
                            if type_field and type_field in item:
                                rel_type = str(item[type_field])
                            elif relationship_type:
                                rel_type = relationship_type
                            else:
                                rel_type = "related_to"
                            
                            relationship = {
                                'id': f"rel_{len(relationships)}",
                                'source': source_entity['id'],
                                'target': target_entity['id'],
                                'type': rel_type,
                                'data_source': context.get('source') if context else None,
                                'confidence': 0.8  # Placeholder confidence score
                            }
                            relationships.append(relationship)
        
        logger.info(f"Extracted {len(relationships)} relationships from structured data")
        return relationships
