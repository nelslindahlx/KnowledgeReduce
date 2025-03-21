"""
Knowledge mapping module for the KnowledgeReduce prototype.

This module implements the mapping phase of KnowledgeReduce, extracting entities and relationships from data.
"""

import pandas as pd
import re
import spacy
from typing import Dict, List, Tuple, Set, Any
from collections import defaultdict

import config

# Load spaCy model for NLP processing
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    # If model not found, download it
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")


class EntityExtractor:
    """Extracts entities from text data."""
    
    def __init__(self, entity_types=None):
        """
        Initialize the entity extractor.
        
        Args:
            entity_types: List of entity types to extract
        """
        self.entity_types = entity_types or config.DEFAULT_ENTITY_TYPES
    
    def extract_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract entities from text using NLP.
        
        Args:
            text: Input text to process
            
        Returns:
            List of extracted entities with their attributes
        """
        if not text:
            return []
        
        doc = nlp(text)
        entities = []
        
        # Extract named entities
        for ent in doc.ents:
            entity_type = self._map_spacy_entity_type(ent.label_)
            if entity_type in self.entity_types:
                entities.append({
                    "name": ent.text,
                    "type": entity_type,
                    "start": ent.start_char,
                    "end": ent.end_char
                })
        
        return entities
    
    def _map_spacy_entity_type(self, spacy_type: str) -> str:
        """
        Map spaCy entity types to our entity types.
        
        Args:
            spacy_type: Entity type from spaCy
            
        Returns:
            Mapped entity type
        """
        # Mapping from spaCy entity types to our types
        mapping = {
            "PERSON": "Person",
            "ORG": "Organization",
            "GPE": "Location",
            "LOC": "Location",
            "PRODUCT": "Concept",
            "WORK_OF_ART": "Concept",
            "EVENT": "Concept"
        }
        
        return mapping.get(spacy_type, "Concept")
    
    def extract_from_structured_data(self, entities_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Process structured entity data.
        
        Args:
            entities_df: DataFrame containing entity data
            
        Returns:
            List of processed entities
        """
        entities = []
        
        for _, row in entities_df.iterrows():
            entity = {
                "id": row["id"],
                "name": row["name"],
                "type": row["type"]
            }
            
            # Add any additional attributes
            for col in entities_df.columns:
                if col not in ["id", "name", "type"] and not pd.isna(row[col]):
                    entity[col] = row[col]
            
            entities.append(entity)
        
        return entities


class RelationshipExtractor:
    """Extracts relationships between entities."""
    
    def __init__(self, relationship_types=None):
        """
        Initialize the relationship extractor.
        
        Args:
            relationship_types: List of relationship types to extract
        """
        self.relationship_types = relationship_types or config.DEFAULT_RELATIONSHIP_TYPES
    
    def extract_from_text(self, text: str, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract relationships from text using NLP.
        
        Args:
            text: Input text to process
            entities: List of entities to find relationships between
            
        Returns:
            List of extracted relationships
        """
        if not text or not entities:
            return []
        
        doc = nlp(text)
        relationships = []
        
        # Create a map of entity spans
        entity_spans = {}
        for entity in entities:
            if "start" in entity and "end" in entity:
                span = (entity["start"], entity["end"])
                entity_spans[span] = entity
        
        # Extract relationships based on dependency parsing
        for token in doc:
            if token.dep_ in ["nsubj", "nsubjpass"] and token.head.dep_ in ["ROOT", "ccomp"]:
                # Find subject and object entities
                subject_span = self._find_entity_span(token.i, doc, entity_spans)
                object_span = self._find_entity_span(token.head.i, doc, entity_spans)
                
                if subject_span and object_span and subject_span != object_span:
                    subject = entity_spans[subject_span]
                    obj = entity_spans[object_span]
                    
                    # Determine relationship type
                    rel_type = self._determine_relationship_type(token.head.lemma_)
                    
                    relationships.append({
                        "source_id": subject.get("id", subject["name"]),
                        "target_id": obj.get("id", obj["name"]),
                        "type": rel_type,
                        "description": f"{subject['name']} {token.head.text} {obj['name']}"
                    })
        
        return relationships
    
    def _find_entity_span(self, token_idx: int, doc, entity_spans: Dict[Tuple[int, int], Dict[str, Any]]) -> Tuple[int, int]:
        """
        Find the entity span that contains the given token.
        
        Args:
            token_idx: Index of the token
            doc: spaCy document
            entity_spans: Map of entity spans to entities
            
        Returns:
            Entity span tuple or None
        """
        token = doc[token_idx]
        token_start = token.idx
        token_end = token_start + len(token.text)
        
        for (start, end), entity in entity_spans.items():
            if start <= token_start and end >= token_end:
                return (start, end)
        
        return None
    
    def _determine_relationship_type(self, verb: str) -> str:
        """
        Determine relationship type based on the verb.
        
        Args:
            verb: Verb lemma
            
        Returns:
            Relationship type
        """
        # Map common verbs to relationship types
        verb_mapping = {
            "work": "WORKS_FOR",
            "employ": "WORKS_FOR",
            "locate": "LOCATED_IN",
            "live": "LOCATED_IN",
            "know": "KNOWS",
            "meet": "KNOWS",
            "relate": "RELATED_TO",
            "associate": "RELATED_TO"
        }
        
        return verb_mapping.get(verb, "RELATED_TO")
    
    def extract_from_structured_data(self, relationships_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Process structured relationship data.
        
        Args:
            relationships_df: DataFrame containing relationship data
            
        Returns:
            List of processed relationships
        """
        relationships = []
        
        for _, row in relationships_df.iterrows():
            relationship = {
                "source_id": row["source_id"],
                "target_id": row["target_id"],
                "type": row["type"]
            }
            
            # Add any additional attributes
            for col in relationships_df.columns:
                if col not in ["source_id", "target_id", "type"] and not pd.isna(row[col]):
                    relationship[col] = row[col]
            
            relationships.append(relationship)
        
        return relationships


class KnowledgeMapper:
    """Implements the mapping phase of KnowledgeReduce."""
    
    def __init__(self):
        """Initialize the knowledge mapper."""
        self.entity_extractor = EntityExtractor()
        self.relationship_extractor = RelationshipExtractor()
    
    def map(self, entities_df: pd.DataFrame, relationships_df: pd.DataFrame) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Map raw data to entities and relationships.
        
        Args:
            entities_df: DataFrame containing entity data
            relationships_df: DataFrame containing relationship data
            
        Returns:
            Tuple of (entities, relationships)
        """
        # Process structured data
        entities = self.entity_extractor.extract_from_structured_data(entities_df)
        relationships = self.relationship_extractor.extract_from_structured_data(relationships_df)
        
        # Extract additional entities and relationships from text descriptions
        self._enrich_from_text(entities, relationships)
        
        return entities, relationships
    
    def _enrich_from_text(self, entities: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> None:
        """
        Enrich entities and relationships with information extracted from text descriptions.
        
        Args:
            entities: List of entities to enrich
            relationships: List of relationships to enrich
        """
        # Extract additional information from entity descriptions
        for entity in entities:
            if "description" in entity:
                # Extract additional entities from description
                extracted_entities = self.entity_extractor.extract_from_text(entity["description"])
                
                # Extract relationships between the entity and extracted entities
                extracted_relationships = self.relationship_extractor.extract_from_text(
                    entity["description"], 
                    [{"id": entity["id"], "name": entity["name"], "type": entity["type"]}] + extracted_entities
                )
                
                # Add new entities and relationships (would need deduplication in a real system)
                # This is simplified for the prototype
                pass


if __name__ == "__main__":
    # Test the module
    from data_ingestion import DataIngestionPipeline, create_sample_data
    
    # Create and load sample data
    create_sample_data()
    pipeline = DataIngestionPipeline()
    entities_df, relationships_df = pipeline.ingest()
    
    # Map data to entities and relationships
    mapper = KnowledgeMapper()
    entities, relationships = mapper.map(entities_df, relationships_df)
    
    print(f"Mapped {len(entities)} entities and {len(relationships)} relationships")
    for entity in entities[:3]:
        print(f"Entity: {entity['name']} ({entity['type']})")
    
    for relationship in relationships[:3]:
        print(f"Relationship: {relationship['source_id']} --[{relationship['type']}]--> {relationship['target_id']}")
