"""
Connectors module for KnowledgeReduce data ingestion.

This module provides connectors for different types of data sources.
"""

from typing import Dict, Any, Optional
import logging
import csv
import json
import requests
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BaseConnector:
    """Base class for all data source connectors."""
    
    def __init__(self, source_type: str):
        """
        Initialize a BaseConnector.
        
        Args:
            source_type: Type of the data source this connector handles.
        """
        self.source_type = source_type
    
    def extract(self, source: str, options: Dict[str, Any]):
        """
        Extract data from the source.
        
        Args:
            source: Path or URL to the data source.
            options: Configuration options for extraction.
            
        Returns:
            Extracted data.
        """
        raise NotImplementedError("Subclasses must implement extract method")


class CSVConnector(BaseConnector):
    """Connector for CSV data sources."""
    
    def __init__(self):
        """Initialize a CSVConnector."""
        super().__init__('csv')
    
    def extract(self, source: str, options: Dict[str, Any]):
        """
        Extract data from a CSV file.
        
        Args:
            source: Path to the CSV file.
            options: Configuration options for extraction.
            
        Returns:
            Extracted data as a list of dictionaries.
        """
        logger.info(f"Extracting data from CSV file: {source}")
        
        delimiter = options.get('delimiter', ',')
        encoding = options.get('encoding', 'utf-8')
        
        try:
            df = pd.read_csv(source, delimiter=delimiter, encoding=encoding)
            return df.to_dict('records')
        except Exception as e:
            logger.error(f"Error extracting data from CSV file {source}: {str(e)}")
            raise


class JSONConnector(BaseConnector):
    """Connector for JSON data sources."""
    
    def __init__(self):
        """Initialize a JSONConnector."""
        super().__init__('json')
    
    def extract(self, source: str, options: Dict[str, Any]):
        """
        Extract data from a JSON file.
        
        Args:
            source: Path to the JSON file.
            options: Configuration options for extraction.
            
        Returns:
            Extracted data as a Python object.
        """
        logger.info(f"Extracting data from JSON file: {source}")
        
        encoding = options.get('encoding', 'utf-8')
        
        try:
            with open(source, 'r', encoding=encoding) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error extracting data from JSON file {source}: {str(e)}")
            raise


class TextConnector(BaseConnector):
    """Connector for text data sources."""
    
    def __init__(self):
        """Initialize a TextConnector."""
        super().__init__('text')
    
    def extract(self, source: str, options: Dict[str, Any]):
        """
        Extract data from a text file.
        
        Args:
            source: Path to the text file.
            options: Configuration options for extraction.
            
        Returns:
            Extracted text as a string.
        """
        logger.info(f"Extracting data from text file: {source}")
        
        encoding = options.get('encoding', 'utf-8')
        
        try:
            with open(source, 'r', encoding=encoding) as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error extracting data from text file {source}: {str(e)}")
            raise


class APIConnector(BaseConnector):
    """Connector for API data sources."""
    
    def __init__(self):
        """Initialize an APIConnector."""
        super().__init__('api')
    
    def extract(self, source: str, options: Dict[str, Any]):
        """
        Extract data from an API endpoint.
        
        Args:
            source: URL of the API endpoint.
            options: Configuration options for extraction.
            
        Returns:
            Extracted data as a Python object.
        """
        logger.info(f"Extracting data from API: {source}")
        
        method = options.get('method', 'GET')
        headers = options.get('headers', {})
        params = options.get('params', {})
        data = options.get('data', None)
        auth = options.get('auth', None)
        
        try:
            response = requests.request(
                method=method,
                url=source,
                headers=headers,
                params=params,
                data=data,
                auth=auth
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error extracting data from API {source}: {str(e)}")
            raise


class DatabaseConnector(BaseConnector):
    """Connector for database data sources."""
    
    def __init__(self):
        """Initialize a DatabaseConnector."""
        super().__init__('database')
    
    def extract(self, source: str, options: Dict[str, Any]):
        """
        Extract data from a database.
        
        Args:
            source: Connection string or identifier for the database.
            options: Configuration options for extraction.
            
        Returns:
            Extracted data as a list of dictionaries.
        """
        logger.info(f"Extracting data from database: {source}")
        
        query = options.get('query')
        if not query:
            raise ValueError("Query is required for database extraction")
        
        # This is a simplified implementation
        # In a real implementation, you would use a database library like SQLAlchemy
        try:
            import sqlalchemy
            engine = sqlalchemy.create_engine(source)
            df = pd.read_sql(query, engine)
            return df.to_dict('records')
        except Exception as e:
            logger.error(f"Error extracting data from database {source}: {str(e)}")
            raise


# Registry of available connectors
_CONNECTORS = {
    'csv': CSVConnector(),
    'json': JSONConnector(),
    'text': TextConnector(),
    'api': APIConnector(),
    'database': DatabaseConnector()
}


def get_connector(source_type: str):
    """
    Get a connector for the specified source type.
    
    Args:
        source_type: Type of the data source.
        
    Returns:
        Connector object for the specified source type.
        
    Raises:
        ValueError: If no connector is available for the specified source type.
    """
    connector = _CONNECTORS.get(source_type.lower())
    if not connector:
        raise ValueError(f"No connector available for source type: {source_type}")
    return connector


def register_connector(source_type: str, connector):
    """
    Register a new connector for a source type.
    
    Args:
        source_type: Type of the data source.
        connector: Connector object for the source type.
    """
    _CONNECTORS[source_type.lower()] = connector
    logger.info(f"Registered connector for source type: {source_type}")
