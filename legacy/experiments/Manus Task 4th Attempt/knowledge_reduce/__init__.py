"""
Integration module for the KnowledgeReduce framework.

This module provides the main KnowledgeReduce class that orchestrates the entire
knowledge reduction process, from data ingestion to knowledge graph construction.
"""

from typing import Dict, List, Any, Optional, Union
import os
import json
import logging
import importlib
from datetime import datetime

from .data_ingestion import DataSource
from .mapping_engine.entity_extractors import BaseEntityExtractor
from .mapping_engine.relationship_extractors import BaseRelationshipExtractor
from .mapping_engine.disambiguation import BaseDisambiguationEngine
from .reducing_engine import ReducingEngine
from .knowledge_graph import KnowledgeGraph
from .knowledge_graph.stackable import StackableKnowledgeManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KnowledgeReduce:
    """
    Main class for the KnowledgeReduce framework.
    
    This class orchestrates the entire knowledge reduction process, from data ingestion
    to knowledge graph construction, with support for stackable knowledge.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the KnowledgeReduce framework.
        
        Args:
            config: Optional configuration dictionary for customizing framework behavior.
        """
        self.config = config or {}
        self.data_sources = []
        self.entity_extractors = []
        self.relationship_extractors = []
        self.disambiguation_engine = None
        self.reducing_engine = ReducingEngine(self.config.get('reducing_engine', {}))
        self.knowledge_graph = KnowledgeGraph(self.config.get('knowledge_graph', {}))
        self.stack_manager = StackableKnowledgeManager(self.config.get('stack_manager', {}))
        logger.info("KnowledgeReduce framework initialized")
    
    def register_data_source(self, data_source: DataSource):
        """
        Register a data source.
        
        Args:
            data_source: A data source object that implements a get_data method.
        """
        self.data_sources.append(data_source)
        logger.info(f"Registered data source: {data_source.__class__.__name__}")
        return data_source
    
    def register_entity_extractor(self, extractor: BaseEntityExtractor):
        """
        Register an entity extractor.
        
        Args:
            extractor: An entity extractor object that implements an extract method.
        """
        self.entity_extractors.append(extractor)
        logger.info(f"Registered entity extractor: {extractor.__class__.__name__}")
        return extractor
    
    def register_relationship_extractor(self, extractor: BaseRelationshipExtractor):
        """
        Register a relationship extractor.
        
        Args:
            extractor: A relationship extractor object that implements an extract method.
        """
        self.relationship_extractors.append(extractor)
        logger.info(f"Registered relationship extractor: {extractor.__class__.__name__}")
        return extractor
    
    def set_disambiguation_engine(self, engine: BaseDisambiguationEngine):
        """
        Set the disambiguation engine.
        
        Args:
            engine: A disambiguation engine object that implements a disambiguate method.
        """
        self.disambiguation_engine = engine
        logger.info(f"Set disambiguation engine: {engine.__class__.__name__}")
        return engine
    
    def create_stack(self, name: str, description: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        """
        Create a new knowledge stack.
        
        Args:
            name: Name of the knowledge stack.
            description: Optional description of the knowledge stack.
            metadata: Optional metadata for the knowledge stack.
            
        Returns:
            The created knowledge stack.
        """
        return self.stack_manager.create_stack(name, description, metadata)
    
    def set_current_stack(self, name: str):
        """
        Set the current knowledge stack.
        
        Args:
            name: Name of the knowledge stack.
        """
        self.stack_manager.set_current_stack(name)
    
    def process(self, data_source_names: Optional[List[str]] = None, stack_name: Optional[str] = None):
        """
        Process data from registered data sources.
        
        Args:
            data_source_names: Optional list of data source names to process. If None, all registered data sources are processed.
            stack_name: Optional name of the knowledge stack to associate the processed data with.
            
        Returns:
            Dictionary containing the processed data.
        """
        logger.info("Starting KnowledgeReduce process")
        
        # Set current stack if provided
        if stack_name:
            self.set_current_stack(stack_name)
        
        # Data ingestion phase
        raw_data = self._ingest_data(data_source_names)
        
        # Mapping phase
        mapped_data = self._map_data(raw_data)
        
        # Reducing phase
        reduced_data = self._reduce_data(mapped_data)
        
        # Knowledge graph construction
        self._build_knowledge_graph(reduced_data)
        
        logger.info("KnowledgeReduce process completed")
        
        return {
            'raw_data': raw_data,
            'mapped_data': mapped_data,
            'reduced_data': reduced_data
        }
    
    def _ingest_data(self, data_source_names: Optional[List[str]] = None):
        """
        Ingest data from registered data sources.
        
        Args:
            data_source_names: Optional list of data source names to process. If None, all registered data sources are processed.
            
        Returns:
            List of raw data items.
        """
        logger.info("Starting data ingestion phase")
        
        raw_data = []
        
        # Process all data sources if none specified
        if not data_source_names:
            data_sources = self.data_sources
        else:
            # Filter data sources by name
            data_sources = [ds for ds in self.data_sources if ds.__class__.__name__ in data_source_names]
        
        # Ingest data from each data source
        for data_source in data_sources:
            try:
                data = data_source.get_data()
                if isinstance(data, list):
                    raw_data.extend(data)
                else:
                    raw_data.append(data)
            except Exception as e:
                logger.error(f"Error ingesting data from {data_source.__class__.__name__}: {str(e)}")
        
        logger.info(f"Data ingestion phase completed: {len(raw_data)} items")
        
        return raw_data
    
    def _map_data(self, raw_data: List[Any]):
        """
        Map raw data to entities and relationships.
        
        Args:
            raw_data: List of raw data items.
            
        Returns:
            Dictionary containing entities and relationships.
        """
        logger.info("Starting mapping phase")
        
        entities = []
        relationships = []
        
        # Extract entities
        for extractor in self.entity_extractors:
            try:
                extracted_entities = extractor.extract(raw_data)
                entities.extend(extracted_entities)
            except Exception as e:
                logger.error(f"Error extracting entities with {extractor.__class__.__name__}: {str(e)}")
        
        # Disambiguate entities
        if self.disambiguation_engine and entities:
            try:
                entities = self.disambiguation_engine.disambiguate(entities)
            except Exception as e:
                logger.error(f"Error disambiguating entities: {str(e)}")
        
        # Extract relationships
        for extractor in self.relationship_extractors:
            try:
                extracted_relationships = extractor.extract(raw_data, entities)
                relationships.extend(extracted_relationships)
            except Exception as e:
                logger.error(f"Error extracting relationships with {extractor.__class__.__name__}: {str(e)}")
        
        logger.info(f"Mapping phase completed: {len(entities)} entities, {len(relationships)} relationships")
        
        return {
            'entities': entities,
            'relationships': relationships
        }
    
    def _reduce_data(self, mapped_data: Dict[str, Any]):
        """
        Reduce mapped data to a knowledge graph.
        
        Args:
            mapped_data: Dictionary containing entities and relationships.
            
        Returns:
            Dictionary containing reduced data.
        """
        logger.info("Starting reducing phase")
        
        reduced_data = self.reducing_engine.reduce(mapped_data)
        
        logger.info("Reducing phase completed")
        
        return reduced_data
    
    def _build_knowledge_graph(self, reduced_data: Dict[str, Any]):
        """
        Build the knowledge graph from reduced data.
        
        Args:
            reduced_data: Dictionary containing reduced data.
        """
        logger.info("Building knowledge graph")
        
        self.knowledge_graph.build(reduced_data)
        
        # Add to current stack if set
        if self.stack_manager.current_stack:
            self.stack_manager.add_to_current_stack(
                reduced_data.get('entities', []),
                reduced_data.get('relationships', [])
            )
        
        logger.info("Knowledge graph built")
    
    def query_knowledge_graph(self, query_string: str, params: Optional[Dict[str, Any]] = None):
        """
        Query the knowledge graph.
        
        Args:
            query_string: Query string in a graph query language.
            params: Optional parameters for the query.
            
        Returns:
            Query results.
        """
        return self.knowledge_graph.query(query_string, params)
    
    def export_knowledge_graph(self, output_path: str, format: str = 'graphml'):
        """
        Export the knowledge graph to a file.
        
        Args:
            output_path: Path where the exported file will be saved.
            format: Format of the exported file (e.g., 'graphml', 'json', 'gexf').
            
        Returns:
            Path to the exported file.
        """
        return self.knowledge_graph.export(output_path, format)
    
    def merge_stacks(self, stack_names: List[str], new_stack_name: str, merge_type: str = 'union'):
        """
        Merge multiple knowledge stacks into a new stack.
        
        Args:
            stack_names: List of stack names to merge.
            new_stack_name: Name of the new merged stack.
            merge_type: Type of merge operation ('union', 'intersection', 'difference').
            
        Returns:
            The merged knowledge stack.
        """
        return self.stack_manager.merge_stacks(stack_names, new_stack_name, merge_type)
    
    def get_stack_hierarchy(self, stack_name: str):
        """
        Get the hierarchy of a stack (parents and children).
        
        Args:
            stack_name: Name of the stack.
            
        Returns:
            Dictionary containing parent and child stacks.
        """
        return self.stack_manager.get_stack_hierarchy(stack_name)
    
    def save_state(self, path: str):
        """
        Save the current state of the KnowledgeReduce framework.
        
        Args:
            path: Directory path where the state will be saved.
        """
        os.makedirs(path, exist_ok=True)
        
        # Save configuration
        with open(os.path.join(path, 'config.json'), 'w') as f:
            json.dump(self.config, f, indent=2)
        
        # Save reducing engine state
        reducing_engine_path = os.path.join(path, 'reducing_engine')
        os.makedirs(reducing_engine_path, exist_ok=True)
        self.reducing_engine.save_state(reducing_engine_path)
        
        # Save knowledge graph state
        knowledge_graph_path = os.path.join(path, 'knowledge_graph')
        os.makedirs(knowledge_graph_path, exist_ok=True)
        self.knowledge_graph.save_state(knowledge_graph_path)
        
        # Save stack manager state
        stack_manager_path = os.path.join(path, 'stack_manager')
        os.makedirs(stack_manager_path, exist_ok=True)
        self.stack_manager.save_state(stack_manager_path)
        
        logger.info(f"KnowledgeReduce state saved to {path}")
    
    def load_state(self, path: str):
        """
        Load a previously saved state of the KnowledgeReduce framework.
        
        Args:
            path: Directory path where the state was saved.
        """
        # Load configuration
        with open(os.path.join(path, 'config.json'), 'r') as f:
            self.config = json.load(f)
        
        # Load reducing engine state
        reducing_engine_path = os.path.join(path, 'reducing_engine')
        self.reducing_engine.load_state(reducing_engine_path)
        
        # Load knowledge graph state
        knowledge_graph_path = os.path.join(path, 'knowledge_graph')
        self.knowledge_graph.load_state(knowledge_graph_path)
        
        # Load stack manager state
        stack_manager_path = os.path.join(path, 'stack_manager')
        self.stack_manager.load_state(stack_manager_path)
        
        logger.info(f"KnowledgeReduce state loaded from {path}")
