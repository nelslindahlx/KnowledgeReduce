"""
Mapping Engine module for KnowledgeReduce.

This module handles the extraction of entities and relationships from preprocessed data
and creates intermediate representations for the KnowledgeReduce framework.
"""

from typing import Dict, List, Any, Optional
import os
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MappingEngine:
    """
    Engine for the mapping phase in the KnowledgeReduce framework.
    
    This class handles the extraction of entities and relationships from preprocessed data
    and creates intermediate representations for further processing.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the MappingEngine.
        
        Args:
            config: Optional configuration dictionary for customizing mapping behavior.
        """
        self.config = config or {}
        self.entity_extractors = []
        self.relationship_extractors = []
        self.disambiguation_engine = None
        logger.info("MappingEngine initialized")
    
    def register_entity_extractor(self, extractor):
        """
        Register an entity extractor.
        
        Args:
            extractor: An entity extractor object that implements an extract method.
        """
        self.entity_extractors.append(extractor)
        logger.info(f"Registered entity extractor: {extractor.__class__.__name__}")
        return extractor
    
    def register_relationship_extractor(self, extractor):
        """
        Register a relationship extractor.
        
        Args:
            extractor: A relationship extractor object that implements an extract method.
        """
        self.relationship_extractors.append(extractor)
        logger.info(f"Registered relationship extractor: {extractor.__class__.__name__}")
        return extractor
    
    def set_disambiguation_engine(self, engine):
        """
        Set the disambiguation engine.
        
        Args:
            engine: A disambiguation engine object that implements a disambiguate method.
        """
        self.disambiguation_engine = engine
        logger.info(f"Set disambiguation engine: {engine.__class__.__name__}")
        return engine
    
    def map(self, processed_data: List[Dict[str, Any]]):
        """
        Map preprocessed data to entities and relationships.
        
        Args:
            processed_data: List of preprocessed data objects.
            
        Returns:
            Dictionary containing extracted entities and relationships.
        """
        logger.info("Starting mapping phase")
        
        entities = []
        relationships = []
        
        for data_item in processed_data:
            source = data_item['source']
            data_type = data_item['type']
            data = data_item['data']
            
            logger.info(f"Mapping data from {source} (type: {data_type})")
            
            # Extract entities
            item_entities = self._extract_entities(data, source, data_type)
            entities.extend(item_entities)
            
            # Extract relationships
            item_relationships = self._extract_relationships(data, item_entities, source, data_type)
            relationships.extend(item_relationships)
        
        # Disambiguate entities if a disambiguation engine is set
        if self.disambiguation_engine:
            entities = self.disambiguation_engine.disambiguate(entities)
        
        logger.info(f"Mapping phase completed: {len(entities)} entities, {len(relationships)} relationships")
        
        return {
            'entities': entities,
            'relationships': relationships
        }
    
    def _extract_entities(self, data, source, data_type):
        """
        Extract entities from data.
        
        Args:
            data: Data to extract entities from.
            source: Source of the data.
            data_type: Type of the data.
            
        Returns:
            List of extracted entities.
        """
        entities = []
        
        for extractor in self.entity_extractors:
            try:
                extracted = extractor.extract(data, {'source': source, 'type': data_type})
                if extracted:
                    entities.extend(extracted)
            except Exception as e:
                logger.error(f"Error extracting entities with {extractor.__class__.__name__}: {str(e)}")
        
        return entities
    
    def _extract_relationships(self, data, entities, source, data_type):
        """
        Extract relationships from data.
        
        Args:
            data: Data to extract relationships from.
            entities: Entities extracted from the same data.
            source: Source of the data.
            data_type: Type of the data.
            
        Returns:
            List of extracted relationships.
        """
        relationships = []
        
        for extractor in self.relationship_extractors:
            try:
                extracted = extractor.extract(data, entities, {'source': source, 'type': data_type})
                if extracted:
                    relationships.extend(extracted)
            except Exception as e:
                logger.error(f"Error extracting relationships with {extractor.__class__.__name__}: {str(e)}")
        
        return relationships
    
    def save_state(self, path: str):
        """
        Save the current state of the MappingEngine.
        
        Args:
            path: Directory path where the state will be saved.
        """
        os.makedirs(path, exist_ok=True)
        
        # Save configuration
        with open(os.path.join(path, 'config.json'), 'w') as f:
            json.dump(self.config, f, indent=2)
        
        logger.info(f"MappingEngine state saved to {path}")
    
    def load_state(self, path: str):
        """
        Load a previously saved state of the MappingEngine.
        
        Args:
            path: Directory path where the state was saved.
        """
        # Load configuration
        with open(os.path.join(path, 'config.json'), 'r') as f:
            self.config = json.load(f)
        
        logger.info(f"MappingEngine state loaded from {path}")
