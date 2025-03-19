"""
Entity extractors for the KnowledgeReduce mapping engine.

This module provides classes for extracting entities from various data formats.
"""

from typing import Dict, List, Any, Optional
import logging
import re
import spacy
from abc import ABC, abstractmethod

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BaseEntityExtractor(ABC):
    """Base class for all entity extractors."""
    
    @abstractmethod
    def extract(self, data, context=None):
        """
        Extract entities from data.
        
        Args:
            data: Data to extract entities from.
            context: Optional context information.
            
        Returns:
            List of extracted entities.
        """
        pass


class NLPEntityExtractor(BaseEntityExtractor):
    """Entity extractor using NLP techniques."""
    
    def __init__(self, model="en_core_web_sm"):
        """
        Initialize an NLPEntityExtractor.
        
        Args:
            model: spaCy model to use for NER.
        """
        try:
            self.nlp = spacy.load(model)
        except OSError:
            logger.info(f"Downloading spaCy model: {model}")
            spacy.cli.download(model)
            self.nlp = spacy.load(model)
        
        logger.info(f"NLPEntityExtractor initialized with model: {model}")
    
    def extract(self, data, context=None):
        """
        Extract entities from text data using NLP.
        
        Args:
            data: Text data to extract entities from.
            context: Optional context information.
            
        Returns:
            List of extracted entities.
        """
        if not isinstance(data, str):
            logger.warning("NLPEntityExtractor expects string data, got %s", type(data))
            return []
        
        logger.info("Extracting entities using NLP")
        
        doc = self.nlp(data)
        entities = []
        
        for ent in doc.ents:
            entity = {
                'id': f"{ent.text.lower().replace(' ', '_')}_{len(entities)}",
                'text': ent.text,
                'type': ent.label_,
                'start': ent.start_char,
                'end': ent.end_char,
                'source': context.get('source') if context else None,
                'confidence': 0.8  # Placeholder confidence score
            }
            entities.append(entity)
        
        logger.info(f"Extracted {len(entities)} entities using NLP")
        return entities


class RegexEntityExtractor(BaseEntityExtractor):
    """Entity extractor using regular expressions."""
    
    def __init__(self, patterns=None):
        """
        Initialize a RegexEntityExtractor.
        
        Args:
            patterns: Dictionary mapping entity types to regex patterns.
        """
        self.patterns = patterns or {}
        logger.info(f"RegexEntityExtractor initialized with {len(self.patterns)} patterns")
    
    def add_pattern(self, entity_type, pattern):
        """
        Add a regex pattern for an entity type.
        
        Args:
            entity_type: Type of entity to extract.
            pattern: Regex pattern to match entities of this type.
        """
        self.patterns[entity_type] = pattern
        logger.info(f"Added pattern for entity type: {entity_type}")
    
    def extract(self, data, context=None):
        """
        Extract entities from text data using regex patterns.
        
        Args:
            data: Text data to extract entities from.
            context: Optional context information.
            
        Returns:
            List of extracted entities.
        """
        if not isinstance(data, str):
            logger.warning("RegexEntityExtractor expects string data, got %s", type(data))
            return []
        
        logger.info("Extracting entities using regex patterns")
        
        entities = []
        
        for entity_type, pattern in self.patterns.items():
            matches = re.finditer(pattern, data)
            for match in matches:
                entity = {
                    'id': f"{match.group().lower().replace(' ', '_')}_{len(entities)}",
                    'text': match.group(),
                    'type': entity_type,
                    'start': match.start(),
                    'end': match.end(),
                    'source': context.get('source') if context else None,
                    'confidence': 0.7  # Placeholder confidence score
                }
                entities.append(entity)
        
        logger.info(f"Extracted {len(entities)} entities using regex patterns")
        return entities


class StructuredDataEntityExtractor(BaseEntityExtractor):
    """Entity extractor for structured data (JSON, CSV, etc.)."""
    
    def __init__(self, entity_mappings=None):
        """
        Initialize a StructuredDataEntityExtractor.
        
        Args:
            entity_mappings: Dictionary mapping data fields to entity properties.
        """
        self.entity_mappings = entity_mappings or {}
        logger.info(f"StructuredDataEntityExtractor initialized with {len(self.entity_mappings)} mappings")
    
    def add_mapping(self, entity_type, id_field, text_field, additional_fields=None):
        """
        Add a mapping for an entity type.
        
        Args:
            entity_type: Type of entity to extract.
            id_field: Field to use as entity ID.
            text_field: Field to use as entity text.
            additional_fields: Additional fields to include in the entity.
        """
        self.entity_mappings[entity_type] = {
            'id_field': id_field,
            'text_field': text_field,
            'additional_fields': additional_fields or []
        }
        logger.info(f"Added mapping for entity type: {entity_type}")
    
    def extract(self, data, context=None):
        """
        Extract entities from structured data.
        
        Args:
            data: Structured data to extract entities from (list of dictionaries).
            context: Optional context information.
            
        Returns:
            List of extracted entities.
        """
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            logger.warning("StructuredDataEntityExtractor expects list of dictionaries, got %s", type(data))
            return []
        
        logger.info("Extracting entities from structured data")
        
        entities = []
        
        for item in data:
            for entity_type, mapping in self.entity_mappings.items():
                id_field = mapping['id_field']
                text_field = mapping['text_field']
                additional_fields = mapping['additional_fields']
                
                if id_field in item and text_field in item:
                    entity = {
                        'id': str(item[id_field]),
                        'text': str(item[text_field]),
                        'type': entity_type,
                        'source': context.get('source') if context else None,
                        'confidence': 0.9  # Placeholder confidence score
                    }
                    
                    # Add additional fields
                    for field in additional_fields:
                        if field in item:
                            entity[field] = item[field]
                    
                    entities.append(entity)
        
        logger.info(f"Extracted {len(entities)} entities from structured data")
        return entities
