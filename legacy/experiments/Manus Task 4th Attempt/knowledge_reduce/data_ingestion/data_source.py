"""
Data Source module for KnowledgeReduce.

This module defines the DataSource class which represents a data source
to be processed by the KnowledgeReduce framework.
"""

from typing import Dict, Any, Optional
import logging
import hashlib
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataSource:
    """
    Class representing a data source in the KnowledgeReduce framework.
    
    A data source is a source of data (file, API, database, etc.) that can be
    processed by the KnowledgeReduce framework.
    """
    
    def __init__(self, source: str, connector, options: Optional[Dict[str, Any]] = None):
        """
        Initialize a DataSource.
        
        Args:
            source: Path or URL to the data source.
            connector: Connector object for accessing the data source.
            options: Optional configuration for processing this specific data source.
        """
        self.source = source
        self.connector = connector
        self.options = options or {}
        self.last_processed = None
        self.checksum = None
        logger.info(f"DataSource initialized: {source}")
    
    def extract(self, incremental: bool = False):
        """
        Extract data from the source.
        
        Args:
            incremental: If True, only extract new or changed data since the last run.
            
        Returns:
            Extracted data.
        """
        logger.info(f"Extracting data from {self.source}")
        
        if incremental and self._is_unchanged():
            logger.info(f"Source {self.source} is unchanged, skipping extraction")
            return None
        
        data = self.connector.extract(self.source, self.options)
        self._update_metadata(data)
        
        return data
    
    def _is_unchanged(self):
        """
        Check if the source has changed since the last extraction.
        
        Returns:
            True if the source is unchanged, False otherwise.
        """
        if not self.checksum:
            return False
        
        current_checksum = self._calculate_checksum()
        return current_checksum == self.checksum
    
    def _calculate_checksum(self):
        """
        Calculate a checksum for the source to detect changes.
        
        Returns:
            Checksum string.
        """
        if os.path.isfile(self.source):
            with open(self.source, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        else:
            # For non-file sources, use the source string itself
            return hashlib.md5(self.source.encode()).hexdigest()
    
    def _update_metadata(self, data):
        """
        Update metadata after extraction.
        
        Args:
            data: Extracted data.
        """
        import datetime
        self.last_processed = datetime.datetime.now().isoformat()
        self.checksum = self._calculate_checksum()
    
    def to_dict(self):
        """
        Convert the DataSource to a dictionary for serialization.
        
        Returns:
            Dictionary representation of the DataSource.
        """
        return {
            'source': self.source,
            'type': self.connector.source_type,
            'options': self.options,
            'last_processed': self.last_processed,
            'checksum': self.checksum
        }
