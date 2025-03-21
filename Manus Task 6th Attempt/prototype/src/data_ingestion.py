"""
Data ingestion module for the KnowledgeReduce prototype.

This module handles loading and preprocessing data from various sources.
"""

import os
import pandas as pd
import json
import csv
from typing import Dict, List, Any, Tuple

import config

class DataLoader:
    """Loads data from various file formats."""
    
    @staticmethod
    def load_csv(file_path: str) -> pd.DataFrame:
        """
        Load data from a CSV file.
        
        Args:
            file_path: Path to the CSV file
            
        Returns:
            DataFrame containing the loaded data
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        return pd.read_csv(file_path)
    
    @staticmethod
    def load_json(file_path: str) -> Dict:
        """
        Load data from a JSON file.
        
        Args:
            file_path: Path to the JSON file
            
        Returns:
            Dictionary containing the loaded data
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(file_path, 'r') as f:
            return json.load(f)


class DataPreprocessor:
    """Preprocesses data for knowledge mapping."""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """
        Clean text data by removing extra whitespace and normalizing case.
        
        Args:
            text: Input text to clean
            
        Returns:
            Cleaned text
        """
        if not text or not isinstance(text, str):
            return ""
        
        # Remove extra whitespace and normalize case
        return " ".join(text.strip().split()).lower()
    
    @staticmethod
    def normalize_entities(entities_df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize entity data by cleaning text fields and ensuring required columns.
        
        Args:
            entities_df: DataFrame containing entity data
            
        Returns:
            Normalized DataFrame
        """
        # Ensure required columns exist
        required_columns = ['id', 'name', 'type']
        for col in required_columns:
            if col not in entities_df.columns:
                raise ValueError(f"Required column '{col}' not found in entities data")
        
        # Create a copy to avoid modifying the original
        df = entities_df.copy()
        
        # Clean text fields
        if 'name' in df.columns:
            df['name'] = df['name'].apply(DataPreprocessor.clean_text)
        
        if 'description' in df.columns:
            df['description'] = df['description'].apply(DataPreprocessor.clean_text)
        
        return df
    
    @staticmethod
    def normalize_relationships(relationships_df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize relationship data by cleaning text fields and ensuring required columns.
        
        Args:
            relationships_df: DataFrame containing relationship data
            
        Returns:
            Normalized DataFrame
        """
        # Ensure required columns exist
        required_columns = ['source_id', 'target_id', 'type']
        for col in required_columns:
            if col not in relationships_df.columns:
                raise ValueError(f"Required column '{col}' not found in relationships data")
        
        # Create a copy to avoid modifying the original
        df = relationships_df.copy()
        
        # Clean text fields
        if 'description' in df.columns:
            df['description'] = df['description'].apply(DataPreprocessor.clean_text)
        
        return df


class DataIngestionPipeline:
    """Pipeline for ingesting and preprocessing data."""
    
    def __init__(self, entities_path: str = None, relationships_path: str = None):
        """
        Initialize the data ingestion pipeline.
        
        Args:
            entities_path: Path to the entities data file
            relationships_path: Path to the relationships data file
        """
        self.entities_path = entities_path or config.ENTITIES_FILE
        self.relationships_path = relationships_path or config.RELATIONSHIPS_FILE
        self.loader = DataLoader()
        self.preprocessor = DataPreprocessor()
    
    def ingest(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Ingest and preprocess data.
        
        Returns:
            Tuple of (entities_df, relationships_df)
        """
        # Load data
        entities_df = self.loader.load_csv(self.entities_path)
        relationships_df = self.loader.load_csv(self.relationships_path)
        
        # Preprocess data
        entities_df = self.preprocessor.normalize_entities(entities_df)
        relationships_df = self.preprocessor.normalize_relationships(relationships_df)
        
        return entities_df, relationships_df


def create_sample_data():
    """
    Create sample data files for demonstration purposes.
    """
    # Create sample entities
    entities = [
        {"id": 1, "name": "John Smith", "type": "Person", "description": "Software Engineer"},
        {"id": 2, "name": "Jane Doe", "type": "Person", "description": "Data Scientist"},
        {"id": 3, "name": "Acme Corporation", "type": "Organization", "description": "Technology company"},
        {"id": 4, "name": "TechCorp", "type": "Organization", "description": "Software development firm"},
        {"id": 5, "name": "Machine Learning", "type": "Concept", "description": "Field of AI"},
        {"id": 6, "name": "San Francisco", "type": "Location", "description": "City in California"},
        {"id": 7, "name": "John Smith", "type": "Person", "description": "CTO at TechCorp"},  # Duplicate for resolution
        {"id": 8, "name": "J. Smith", "type": "Person", "description": "Engineer"}  # Similar for resolution
    ]
    
    # Create sample relationships
    relationships = [
        {"source_id": 1, "target_id": 3, "type": "WORKS_FOR", "description": "Employed since 2020"},
        {"source_id": 2, "target_id": 4, "type": "WORKS_FOR", "description": "Senior position"},
        {"source_id": 1, "target_id": 2, "type": "KNOWS", "description": "Colleagues"},
        {"source_id": 1, "target_id": 5, "type": "RELATED_TO", "description": "Expertise"},
        {"source_id": 2, "target_id": 5, "type": "RELATED_TO", "description": "Expertise"},
        {"source_id": 3, "target_id": 6, "type": "LOCATED_IN", "description": "Headquarters"},
        {"source_id": 7, "target_id": 4, "type": "WORKS_FOR", "description": "Executive role"}
    ]
    
    # Save to CSV files
    entities_df = pd.DataFrame(entities)
    relationships_df = pd.DataFrame(relationships)
    
    os.makedirs(os.path.dirname(config.ENTITIES_FILE), exist_ok=True)
    os.makedirs(os.path.dirname(config.RELATIONSHIPS_FILE), exist_ok=True)
    
    entities_df.to_csv(config.ENTITIES_FILE, index=False)
    relationships_df.to_csv(config.RELATIONSHIPS_FILE, index=False)
    
    return entities_df, relationships_df


if __name__ == "__main__":
    # Test the module
    create_sample_data()
    pipeline = DataIngestionPipeline()
    entities, relationships = pipeline.ingest()
    print(f"Loaded {len(entities)} entities and {len(relationships)} relationships")
    print(entities.head())
    print(relationships.head())
