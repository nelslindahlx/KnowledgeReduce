"""
Data Ingestion module for KnowledgeReduce.

This module handles the acquisition, preprocessing, and quality assurance of data
from various sources for the KnowledgeReduce framework.
"""

from typing import Dict, List, Any, Optional
import os
import json
import logging
from .data_source import DataSource
from .connectors import get_connector

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataIngestionManager:
    """
    Manager class for data ingestion in the KnowledgeReduce framework.
    
    This class handles the registration, processing, and management of data sources.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the DataIngestionManager.
        
        Args:
            config: Optional configuration dictionary for customizing data ingestion behavior.
        """
        self.config = config or {}
        self.sources = []
        self.preprocessors = []
        logger.info("DataIngestionManager initialized")
    
    def register_source(self, source: str, source_type: str, options: Optional[Dict[str, Any]] = None):
        """
        Register a data source for processing.
        
        Args:
            source: Path or URL to the data source.
            source_type: Type of the data source (e.g., 'csv', 'json', 'text', 'api').
            options: Optional configuration for processing this specific data source.
        """
        connector = get_connector(source_type)
        data_source = DataSource(source, connector, options or {})
        self.sources.append(data_source)
        logger.info(f"Registered data source: {source} (type: {source_type})")
        return data_source
    
    def register_preprocessor(self, preprocessor):
        """
        Register a data preprocessor.
        
        Args:
            preprocessor: A preprocessor object that implements a process method.
        """
        self.preprocessors.append(preprocessor)
        logger.info(f"Registered preprocessor: {preprocessor.__class__.__name__}")
        return preprocessor
    
    def process_all(self, incremental: bool = False):
        """
        Process all registered data sources.
        
        Args:
            incremental: If True, only process new or changed data since the last run.
            
        Returns:
            List of processed data objects.
        """
        logger.info(f"Processing all data sources (incremental: {incremental})")
        processed_data = []
        
        for source in self.sources:
            try:
                # Extract data from source
                raw_data = source.extract(incremental)
                
                # Apply all preprocessors
                processed = raw_data
                for preprocessor in self.preprocessors:
                    processed = preprocessor.process(processed)
                
                processed_data.append({
                    'source': source.source,
                    'type': source.connector.source_type,
                    'data': processed
                })
                
                logger.info(f"Successfully processed data from {source.source}")
            except Exception as e:
                logger.error(f"Error processing data from {source.source}: {str(e)}")
        
        return processed_data
    
    def save_state(self, path: str):
        """
        Save the current state of the DataIngestionManager.
        
        Args:
            path: Directory path where the state will be saved.
        """
        os.makedirs(path, exist_ok=True)
        
        # Save sources
        sources_data = []
        for source in self.sources:
            sources_data.append(source.to_dict())
        
        with open(os.path.join(path, 'sources.json'), 'w') as f:
            json.dump(sources_data, f, indent=2)
        
        logger.info(f"DataIngestionManager state saved to {path}")
    
    def load_state(self, path: str):
        """
        Load a previously saved state of the DataIngestionManager.
        
        Args:
            path: Directory path where the state was saved.
        """
        # Load sources
        with open(os.path.join(path, 'sources.json'), 'r') as f:
            sources_data = json.load(f)
        
        self.sources = []
        for source_data in sources_data:
            connector = get_connector(source_data['type'])
            data_source = DataSource(
                source_data['source'],
                connector,
                source_data.get('options', {})
            )
            self.sources.append(data_source)
        
        logger.info(f"DataIngestionManager state loaded from {path}")
