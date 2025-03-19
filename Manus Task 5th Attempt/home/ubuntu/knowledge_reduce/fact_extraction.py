#!/usr/bin/env python3
"""
Fact Extraction Module for KnowledgeReduce

This module implements the entity recognition and relationship extraction components
of the KnowledgeReduce framework, which is responsible for extracting facts from
various data sources and preparing them for the knowledge stacking process.
"""

import os
import json
import spacy
import nltk
from typing import List, Dict, Tuple, Any, Optional, Set
from collections import defaultdict
import re

# Download necessary NLTK data
nltk.download('punkt', quiet=True)
nltk.download('averaged_perceptron_tagger', quiet=True)
nltk.download('maxent_ne_chunker', quiet=True)
nltk.download('words', quiet=True)

class EntityRecognizer:
    """
    Component for identifying entities in text data using various NLP techniques.
    """
    
    def __init__(self, model_name: str = 'en_core_web_sm'):
        """
        Initialize the entity recognizer with the specified language model.
        
        Args:
            model_name: Name of the spaCy model to use
        """
        self.nlp = spacy.load(model_name)
        self.entity_types = {
            'PERSON': 'person',
            'ORG': 'organization',
            'GPE': 'location',
            'LOC': 'location',
            'PRODUCT': 'product',
            'EVENT': 'event',
            'WORK_OF_ART': 'work_of_art',
            'DATE': 'date',
            'TIME': 'time',
            'MONEY': 'money',
            'QUANTITY': 'quantity',
            'PERCENT': 'percent',
            'FACILITY': 'facility',
            'NORP': 'nationality_or_religious_group'
        }
    
    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract entities from the given text.
        
        Args:
            text: Input text to extract entities from
            
        Returns:
            List of dictionaries containing entity information
        """
        doc = self.nlp(text)
        entities = []
        
        for ent in doc.ents:
            entity_type = self.entity_types.get(ent.label_, 'misc')
            entity = {
                'text': ent.text,
                'type': entity_type,
                'start_char': ent.start_char,
                'end_char': ent.end_char,
                'label': ent.label_
            }
            entities.append(entity)
        
        return entities
    
    def extract_entities_batch(self, texts: List[str]) -> List[List[Dict[str, Any]]]:
        """
        Extract entities from a batch of texts.
        
        Args:
            texts: List of input texts
            
        Returns:
            List of lists containing entity information for each text
        """
        return [self.extract_entities(text) for text in texts]


class RelationshipExtractor:
    """
    Component for extracting relationships between entities in text.
    """
    
    def __init__(self, model_name: str = 'en_core_web_sm'):
        """
        Initialize the relationship extractor with the specified language model.
        
        Args:
            model_name: Name of the spaCy model to use
        """
        self.nlp = spacy.load(model_name)
        # Common relationship patterns (subject-verb-object)
        self.relationship_patterns = [
            # Subject-Verb-Object patterns
            [{'DEP': 'nsubj'}, {'DEP': 'ROOT'}, {'DEP': 'dobj'}],
            # Subject-Verb-Prep-Object patterns
            [{'DEP': 'nsubj'}, {'DEP': 'ROOT'}, {'DEP': 'prep'}, {'DEP': 'pobj'}],
            # Noun-Prep-Noun patterns
            [{'POS': 'NOUN'}, {'DEP': 'prep'}, {'DEP': 'pobj'}]
        ]
    
    def extract_relationships(self, text: str, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract relationships between entities in the given text.
        
        Args:
            text: Input text to extract relationships from
            entities: List of entities extracted from the text
            
        Returns:
            List of dictionaries containing relationship information
        """
        doc = self.nlp(text)
        relationships = []
        
        # Create a mapping of token indices to entities
        entity_tokens = {}
        for entity in entities:
            start_char = entity['start_char']
            end_char = entity['end_char']
            for token in doc:
                if token.idx >= start_char and token.idx + len(token.text) <= end_char:
                    entity_tokens[token.i] = entity
        
        # Extract subject-verb-object patterns
        for sent in doc.sents:
            for token in sent:
                # Check if token is a verb
                if token.pos_ == "VERB":
                    # Find subject
                    subjects = [child for child in token.children if child.dep_ in ("nsubj", "nsubjpass")]
                    # Find objects
                    objects = [child for child in token.children if child.dep_ in ("dobj", "pobj", "attr")]
                    # Find prepositional phrases
                    preps = [child for child in token.children if child.dep_ == "prep"]
                    for prep in preps:
                        prep_objects = [child for child in prep.children if child.dep_ == "pobj"]
                        objects.extend(prep_objects)
                    
                    # Create relationships between subjects and objects
                    for subj in subjects:
                        for obj in objects:
                            # Check if subject and object are part of recognized entities
                            subj_entity = entity_tokens.get(subj.i)
                            obj_entity = entity_tokens.get(obj.i)
                            
                            if subj_entity and obj_entity:
                                relationship = {
                                    'subject': subj_entity['text'],
                                    'subject_type': subj_entity['type'],
                                    'predicate': token.lemma_,
                                    'object': obj_entity['text'],
                                    'object_type': obj_entity['type'],
                                    'sentence': sent.text
                                }
                                relationships.append(relationship)
        
        return relationships


class IntermediateRepresentationGenerator:
    """
    Component for generating intermediate key-value representations from extracted entities and relationships.
    """
    
    def generate_representation(self, entities: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate intermediate representation from extracted entities and relationships.
        
        Args:
            entities: List of extracted entities
            relationships: List of extracted relationships
            
        Returns:
            Dictionary containing intermediate representation
        """
        # Create entity nodes
        entity_nodes = {}
        for entity in entities:
            entity_id = f"{entity['type']}:{entity['text'].lower().replace(' ', '_')}"
            if entity_id not in entity_nodes:
                entity_nodes[entity_id] = {
                    'id': entity_id,
                    'text': entity['text'],
                    'type': entity['type'],
                    'mentions': 1
                }
            else:
                entity_nodes[entity_id]['mentions'] += 1
        
        # Create relationship edges
        relationship_edges = []
        for rel in relationships:
            subject_id = f"{rel['subject_type']}:{rel['subject'].lower().replace(' ', '_')}"
            object_id = f"{rel['object_type']}:{rel['object'].lower().replace(' ', '_')}"
            
            if subject_id in entity_nodes and object_id in entity_nodes:
                edge = {
                    'source': subject_id,
                    'target': object_id,
                    'type': rel['predicate'],
                    'sentence': rel['sentence']
                }
                relationship_edges.append(edge)
        
        # Create intermediate representation
        intermediate_rep = {
            'nodes': list(entity_nodes.values()),
            'edges': relationship_edges
        }
        
        return intermediate_rep


class FactExtractor:
    """
    Main class for extracting facts from text data, combining entity recognition and relationship extraction.
    """
    
    def __init__(self, entity_model: str = 'en_core_web_sm', relationship_model: str = 'en_core_web_sm'):
        """
        Initialize the fact extractor with the specified models.
        
        Args:
            entity_model: Name of the spaCy model for entity recognition
            relationship_model: Name of the spaCy model for relationship extraction
        """
        self.entity_recognizer = EntityRecognizer(entity_model)
        self.relationship_extractor = RelationshipExtractor(relationship_model)
        self.representation_generator = IntermediateRepresentationGenerator()
    
    def extract_facts(self, text: str) -> Dict[str, Any]:
        """
        Extract facts from the given text.
        
        Args:
            text: Input text to extract facts from
            
        Returns:
            Dictionary containing extracted facts in intermediate representation
        """
        # Extract entities
        entities = self.entity_recognizer.extract_entities(text)
        
        # Extract relationships
        relationships = self.relationship_extractor.extract_relationships(text, entities)
        
        # Generate intermediate representation
        intermediate_rep = self.representation_generator.generate_representation(entities, relationships)
        
        return intermediate_rep
    
    def extract_facts_from_file(self, file_path: str) -> Dict[str, Any]:
        """
        Extract facts from the given file.
        
        Args:
            file_path: Path to the file to extract facts from
            
        Returns:
            Dictionary containing extracted facts in intermediate representation
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        return self.extract_facts(text)
    
    def extract_facts_from_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        Extract facts from multiple files and merge the results.
        
        Args:
            file_paths: List of paths to files to extract facts from
            
        Returns:
            Dictionary containing merged extracted facts in intermediate representation
        """
        all_nodes = {}
        all_edges = []
        
        for file_path in file_paths:
            facts = self.extract_facts_from_file(file_path)
            
            # Merge nodes
            for node in facts['nodes']:
                node_id = node['id']
                if node_id in all_nodes:
                    all_nodes[node_id]['mentions'] += node['mentions']
                else:
                    all_nodes[node_id] = node
            
            # Add edges
            all_edges.extend(facts['edges'])
        
        # Create merged intermediate representation
        merged_rep = {
            'nodes': list(all_nodes.values()),
            'edges': all_edges
        }
        
        return merged_rep
    
    def save_facts(self, facts: Dict[str, Any], output_file: str) -> None:
        """
        Save extracted facts to a JSON file.
        
        Args:
            facts: Dictionary containing extracted facts
            output_file: Path to the output file
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(facts, f, indent=2)


# Example usage
if __name__ == "__main__":
    # Create fact extractor
    fact_extractor = FactExtractor()
    
    # Example text
    example_text = """
    Apple Inc. was founded by Steve Jobs, Steve Wozniak, and Ronald Wayne in April 1976. 
    The company is headquartered in Cupertino, California. 
    Tim Cook is the current CEO of Apple. 
    Apple released the iPhone in 2007, which revolutionized the smartphone industry.
    """
    
    # Extract facts
    facts = fact_extractor.extract_facts(example_text)
    
    # Print extracted facts
    print(json.dumps(facts, indent=2))
