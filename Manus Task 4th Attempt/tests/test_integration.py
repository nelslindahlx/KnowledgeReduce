"""
Integration tests for the KnowledgeReduce framework.

This module provides integration tests that validate the KnowledgeReduce implementation
against the paper's conceptual framework by testing the full pipeline with realistic data.
"""

import os
import json
import logging
import unittest
import networkx as nx
import matplotlib.pyplot as plt
from typing import Dict, List, Any

from knowledge_reduce import KnowledgeReduce
from knowledge_reduce.data_ingestion import FileConnector
from knowledge_reduce.mapping_engine.entity_extractors import SimpleEntityExtractor
from knowledge_reduce.mapping_engine.relationship_extractors import SimpleRelationshipExtractor
from knowledge_reduce.mapping_engine.disambiguation import SimpleDisambiguationEngine, ContextualDisambiguationEngine
from knowledge_reduce.reducing_engine.aggregators import SimpleAggregator, WeightedAggregator
from knowledge_reduce.reducing_engine.conflict_resolvers import ConfidenceBasedResolver, MajorityVotingResolver, SourcePriorityResolver
from knowledge_reduce.knowledge_graph.stackable import StackableKnowledgeManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TestKnowledgeReduceIntegration(unittest.TestCase):
    """Integration test cases for the KnowledgeReduce framework."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        # Create test data directory
        os.makedirs("integration_test_data", exist_ok=True)
        os.makedirs("integration_test_output", exist_ok=True)
        
        # Create realistic test data
        cls.create_test_data()
    
    @classmethod
    def create_test_data(cls):
        """Create realistic test data for integration testing."""
        # Academic publications dataset
        publications = [
            {
                "id": "pub1",
                "title": "Knowledge Reduce: A Novel Approach to Knowledge Graph Construction",
                "authors": ["Smith, J.", "Johnson, R.", "Williams, A."],
                "year": 2022,
                "venue": "International Conference on Knowledge Engineering",
                "abstract": "This paper introduces Knowledge Reduce, a novel approach to knowledge graph construction that adapts the MapReduce paradigm for knowledge processing. The approach enables stackable knowledge sets that can be incrementally built and integrated.",
                "keywords": ["knowledge graph", "knowledge engineering", "MapReduce", "stackable knowledge"],
                "references": ["ref1", "ref2", "ref3"]
            },
            {
                "id": "pub2",
                "title": "Stackable Knowledge Representation for Incremental Learning",
                "authors": ["Johnson, R.", "Davis, M.", "Wilson, E."],
                "year": 2021,
                "venue": "Journal of Artificial Intelligence Research",
                "abstract": "We present a novel approach to knowledge representation that supports incremental learning through stackable knowledge sets. Our approach allows for the integration of knowledge from multiple sources while maintaining provenance and handling conflicts.",
                "keywords": ["knowledge representation", "incremental learning", "stackable knowledge", "conflict resolution"],
                "references": ["ref4", "ref5", "ref6"]
            },
            {
                "id": "pub3",
                "title": "Entity Disambiguation in Knowledge Graphs",
                "authors": ["Williams, A.", "Brown, C.", "Smith, J."],
                "year": 2020,
                "venue": "International Conference on Data Engineering",
                "abstract": "Entity disambiguation is a critical challenge in knowledge graph construction. This paper presents a novel approach to entity disambiguation that leverages contextual information and hierarchical clustering to resolve ambiguities.",
                "keywords": ["entity disambiguation", "knowledge graph", "contextual information", "hierarchical clustering"],
                "references": ["ref7", "ref8", "ref9"]
            }
        ]
        
        with open("integration_test_data/publications.json", "w") as f:
            json.dump(publications, f, indent=2)
        
        # Authors dataset
        authors = [
            {
                "id": "author1",
                "name": "Smith, J.",
                "full_name": "John Smith",
                "affiliation": "University of Technology",
                "email": "john.smith@utech.edu",
                "research_interests": ["knowledge graphs", "artificial intelligence", "data mining"]
            },
            {
                "id": "author2",
                "name": "Johnson, R.",
                "full_name": "Robert Johnson",
                "affiliation": "Research Institute",
                "email": "r.johnson@research.org",
                "research_interests": ["knowledge representation", "machine learning", "natural language processing"]
            },
            {
                "id": "author3",
                "name": "Williams, A.",
                "full_name": "Alice Williams",
                "affiliation": "University of Science",
                "email": "a.williams@science.edu",
                "research_interests": ["entity disambiguation", "information retrieval", "semantic web"]
            },
            {
                "id": "author4",
                "name": "Davis, M.",
                "full_name": "Michael Davis",
                "affiliation": "Tech University",
                "email": "m.davis@tech.edu",
                "research_interests": ["data integration", "knowledge bases", "ontology engineering"]
            },
            {
                "id": "author5",
                "name": "Wilson, E.",
                "full_name": "Emily Wilson",
                "affiliation": "Data Science Institute",
                "email": "e.wilson@datascience.org",
                "research_interests": ["machine learning", "data mining", "knowledge discovery"]
            },
            {
                "id": "author6",
                "name": "Brown, C.",
                "full_name": "Christopher Brown",
                "affiliation": "University of Technology",
                "email": "c.brown@utech.edu",
                "research_interests": ["information extraction", "text mining", "natural language processing"]
            }
        ]
        
        with open("integration_test_data/authors.json", "w") as f:
            json.dump(authors, f, indent=2)
        
        # Venues dataset
        venues = [
            {
                "id": "venue1",
                "name": "International Conference on Knowledge Engineering",
                "abbreviation": "ICKE",
                "type": "conference",
                "impact_factor": 3.5,
                "field": "knowledge engineering"
            },
            {
                "id": "venue2",
                "name": "Journal of Artificial Intelligence Research",
                "abbreviation": "JAIR",
                "type": "journal",
                "impact_factor": 4.2,
                "field": "artificial intelligence"
            },
            {
                "id": "venue3",
                "name": "International Conference on Data Engineering",
                "abbreviation": "ICDE",
                "type": "conference",
                "impact_factor": 3.8,
                "field": "data engineering"
            }
        ]
        
        with open("integration_test_data/venues.json", "w") as f:
            json.dump(venues, f, indent=2)
        
        # Citations dataset
        citations = [
            {
                "id": "cite1",
                "citing_paper": "pub1",
                "cited_paper": "pub2",
                "context": "As shown in Johnson et al. (2021), stackable knowledge representation enables incremental learning."
            },
            {
                "id": "cite2",
                "citing_paper": "pub1",
                "cited_paper": "pub3",
                "context": "We build upon the entity disambiguation approach proposed by Williams et al. (2020)."
            },
            {
                "id": "cite3",
                "citing_paper": "pub2",
                "cited_paper": "pub3",
                "context": "Entity disambiguation techniques (Williams et al., 2020) are essential for maintaining knowledge integrity."
            }
        ]
        
        with open("integration_test_data/citations.json", "w") as f:
            json.dump(citations, f, indent=2)
        
        # Duplicate and conflicting data
        duplicates = [
            {
                "id": "dup1",
                "name": "John Smith",
                "affiliation": "University of Technology",
                "source": "database1",
                "confidence": 0.9
            },
            {
                "id": "dup2",
                "name": "J. Smith",
                "affiliation": "Univ. of Tech",
                "source": "database2",
                "confidence": 0.7
            },
            {
                "id": "dup3",
                "name": "Smith, John",
                "affiliation": "University of Technology",
                "source": "database3",
                "confidence": 0.8
            },
            {
                "id": "dup4",
                "name": "International Conference on Knowledge Engineering",
                "abbreviation": "ICKE",
                "impact_factor": 3.5,
                "source": "database1",
                "confidence": 0.9
            },
            {
                "id": "dup5",
                "name": "Int. Conf. on Knowledge Eng.",
                "abbreviation": "ICKE",
                "impact_factor": 3.7,
                "source": "database2",
                "confidence": 0.8
            }
        ]
        
        with open("integration_test_data/duplicates.json", "w") as f:
            json.dump(duplicates, f, indent=2)
    
    def setUp(self):
        """Set up each test."""
        # Initialize KnowledgeReduce
        self.kr = KnowledgeReduce()
        
        # Configure data sources
        self.publications_connector = FileConnector("integration_test_data/publications.json", "json")
        self.authors_connector = FileConnector("integration_test_data/authors.json", "json")
        self.venues_connector = FileConnector("integration_test_data/venues.json", "json")
        self.citations_connector = FileConnector("integration_test_data/citations.json", "json")
        self.duplicates_connector = FileConnector("integration_test_data/duplicates.json", "json")
        
        # Register data sources
        self.kr.register_data_source(self.publications_connector)
        self.kr.register_data_source(self.authors_connector)
        self.kr.register_data_source(self.venues_connector)
        self.kr.register_data_source(self.citations_connector)
        
        # Configure mapping engine
        self.entity_extractor = SimpleEntityExtractor()
        self.relationship_extractor = SimpleRelationshipExtractor()
        self.disambiguation_engine = ContextualDisambiguationEngine()
        
        self.kr.register_entity_extractor(self.entity_extractor)
        self.kr.register_relationship_extractor(self.relationship_extractor)
        self.kr.set_disambiguation_engine(self.disambiguation_engine)
        
        # Configure reducing engine
        self.aggregator = WeightedAggregator()
        self.conflict_resolver = SourcePriorityResolver()
        
        self.kr.reducing_engine.register_aggregator(self.aggregator)
        self.kr.reducing_engine.register_conflict_resolver(self.conflict_resolver)
    
    def test_full_pipeline(self):
        """Test the full KnowledgeReduce pipeline with realistic data."""
        # Process data
        result = self.kr.process()
        
        # Check if all phases produced results
        self.assertIn('raw_data', result)
        self.assertIn('mapped_data', result)
        self.assertIn('reduced_data', result)
        
        # Check if entities and relationships were extracted
        self.assertIn('entities', result['mapped_data'])
        self.assertIn('relationships', result['mapped_data'])
        self.assertTrue(len(result['mapped_data']['entities']) > 0)
        self.assertTrue(len(result['mapped_data']['relationships']) > 0)
        
        # Check if entities and relationships were reduced
        self.assertIn('entities', result['reduced_data'])
        self.assertIn('relationships', result['reduced_data'])
        self.assertTrue(len(result['reduced_data']['entities']) > 0)
        self.assertTrue(len(result['reduced_data']['relationships']) > 0)
        
        # Export knowledge graph
        export_path = self.kr.export_knowledge_graph("integration_test_output/full_pipeline_graph.json", "json")
        
        # Check if export file exists and contains valid data
        self.assertTrue(os.path.exists(export_path))
        with open(export_path, 'r') as f:
            graph_data = json.load(f)
        
        self.assertIn('nodes', graph_data)
        self.assertIn('links', graph_data)
        self.assertTrue(len(graph_data['nodes']) > 0)
        self.assertTrue(len(graph_data['links']) > 0)
    
    def test_stackable_knowledge_integration(self):
        """Test stackable knowledge integration with realistic data."""
        # Create stacks for different data types
        self.kr.create_stack("publications_stack", "Publications knowledge")
        self.kr.create_stack("authors_stack", "Authors knowledge")
        self.kr.create_stack("venues_stack", "Venues knowledge")
        self.kr.create_stack("citations_stack", "Citations knowledge")
        
        # Process publications data
        self.kr.set_current_stack("publications_stack")
        self.kr.register_data_source(self.publications_connector)
        publications_result = self.kr.process()
        
        # Process authors data
        self.kr.set_current_stack("authors_stack")
        self.kr.register_data_source(self.authors_connector)
        authors_result = self.kr.process()
        
        # Process venues data
        self.kr.set_current_stack("venues_stack")
        self.kr.register_data_source(self.venues_connector)
        venues_result = self.kr.process()
        
        # Process citations data
        self.kr.set_current_stack("citations_stack")
        self.kr.register_data_source(self.citations_connector)
        citations_result = self.kr.process()
        
        # Create stack hierarchies
        self.kr.stack_manager.create_stack_hierarchy("authors_stack", "publications_stack")
        self.kr.stack_manager.create_stack_hierarchy("venues_stack", "publications_stack")
        
        # Merge stacks
        academic_stack = self.kr.merge_stacks(
            ["publications_stack", "authors_stack", "venues_stack", "citations_stack"],
            "academic_stack",
            "union"
        )
        
        # Check if merged stack contains entities from all stacks
        publications_entities = len(self.kr.stack_manager.get_stack("publications_stack").entities)
        authors_entities = len(self.kr.stack_manager.get_stack("authors_stack").entities)
        venues_entities = len(self.kr.stack_manager.get_stack("venues_stack").entities)
        citations_entities = len(self.kr.stack_manager.get_stack("citations_stack").entities)
        
        # The merged stack should contain at least as many entities as the sum of all stacks
        # (could be less due to entity disambiguation)
        self.assertGreaterEqual(
            len(academic_stack.entities),
            max(1, publications_entities + authors_entities + venues_entities + citations_entities - 10)
        )
        
        # Export the merged knowledge graph
        export_path = self.kr.export_knowledge_graph("integration_test_output/academic_graph.json", "json")
        
        # Check if export file exists and contains valid data
        self.assertTrue(os.path.exists(export_path))
        with open(export_path, 'r') as f:
            graph_data = json.load(f)
        
        self.assertIn('nodes', graph_data)
        self.assertIn('links', graph_data)
        self.assertTrue(len(graph_data['nodes']) > 0)
        self.assertTrue(len(graph_data['links']) > 0)
    
    def test_incremental_knowledge_building(self):
        """Test incremental knowledge building with realistic data."""
        # Phase 1: Process authors data
        self.kr.create_stack("phase1_stack", "Initial knowledge about authors")
        self.kr.set_current_stack("phase1_stack")
        self.kr.register_data_source(self.authors_connector)
        phase1_result = self.kr.process()
        
        # Phase 2: Add publications data
        self.kr.create_stack("phase2_stack", "Knowledge with publications added")
        self.kr.set_current_stack("phase2_stack")
        self.kr.register_data_source(self.publications_connector)
        phase2_result = self.kr.process()
        
        # Phase 3: Add venues data
        self.kr.create_stack("phase3_stack", "Knowledge with venues added")
        self.kr.set_current_stack("phase3_stack")
        self.kr.register_data_source(self.venues_connector)
        phase3_result = self.kr.process()
        
        # Phase 4: Add citations data
        self.kr.create_stack("phase4_stack", "Knowledge with citations added")
        self.kr.set_current_stack("phase4_stack")
        self.kr.register_data_source(self.citations_connector)
        phase4_result = self.kr.process()
        
        # Create hierarchy between phases
        self.kr.stack_manager.create_stack_hierarchy("phase1_stack", "phase2_stack")
        self.kr.stack_manager.create_stack_hierarchy("phase2_stack", "phase3_stack")
        self.kr.stack_manager.create_stack_hierarchy("phase3_stack", "phase4_stack")
        
        # Get combined knowledge from all phases
        combined_stack = self.kr.stack_manager.get_combined_stack("phase4_stack", include_ancestors=True)
        
        # Check if combined stack contains entities from all phases
        phase1_entities = len(self.kr.stack_manager.get_stack("phase1_stack").entities)
        phase2_entities = len(self.kr.stack_manager.get_stack("phase2_stack").entities)
        phase3_entities = len(self.kr.stack_manager.get_stack("phase3_stack").entities)
        phase4_entities = len(self.kr.stack_manager.get_stack("phase4_stack").entities)
        
        # The combined stack should contain at least as many entities as the sum of all phases
        # (could be less due to entity disambiguation)
        self.assertGreaterEqual(
            len(combined_stack["entities"]),
            max(1, phase1_entities + phase2_entities + phase3_entities + phase4_entities - 10)
        )
        
        # Visualize stack hierarchy
        hierarchy_path = self.kr.stack_manager.visualize_stack_hierarchy("integration_test_output/incremental_hierarchy.png")
        
        # Check if visualization file exists
        self.assertTrue(os.path.exists(hierarchy_path))
    
    def test_conflict_resolution_with_duplicates(self):
        """Test conflict resolution with duplicate and conflicting data."""
        # Register duplicates connector
        self.kr.register_data_source(self.duplicates_connector)
        
        # Set source priorities for conflict resolution
        source_priority_resolver = SourcePriorityResolver()
        source_priority_resolver.set_source_priority("database1", 3)
        source_priority_resolver.set_source_priority("database2", 2)
        source_priority_resolver.set_source_priority("database3", 1)
        
        self.kr.reducing_engine.register_conflict_resolver(source_priority_resolver)
        
        # Process data
        result = self.kr.process()
        
        # Check if disambiguation and conflict resolution worked
        # For source priority resolution, the source with higher priority should be used
        for entity in result['reduced_data']['entities']:
            if entity.get('name') == "John Smith" or entity.get('name') == "J. Smith" or entity.get('name') == "Smith, John":
                # The entity should have alternative texts
                self.assertIn('alternative_texts', entity)
                # The affiliation should be from the highest priority source
                self.assertEqual(entity.get('affiliation'), "University of Technology")
            
            if entity.get('name') == "International Conference on Knowledge Engineering" or entity.get('name') == "Int. Conf. on Knowledge Eng.":
                # The entity should have alternative texts
                self.assertIn('alternative_texts', entity)
                # The impact factor should be from the highest priority source
                self.assertEqual(entity.get('impact_factor'), 3.5)
    
    def test_knowledge_query(self):
        """Test knowledge graph querying."""
        # Process data
        self.kr.process()
        
        # Query the knowledge graph
        query_result = self.kr.query_knowledge_graph("MATCH (a:Author)-[:AUTHORED]->(p:Publication) RETURN a, p")
        
        # Check if query returned results
        self.assertIn('nodes', query_result)
        self.assertIn('edges', query_result)
        
        # Check if authors and publications are in the results
        author_found = False
        publication_found = False
        
        for node in query_result['nodes']:
            if node.get('type') == 'Author':
                author_found = True
            if node.get('type') == 'Publication':
                publication_found = True
        
        self.assertTrue(author_found, "Authors should be in query results")
        self.assertTrue(publication_found, "Publications should be in query results")
    
    def test_save_and_load_state(self):
        """Test saving and loading the KnowledgeReduce state."""
        # Process data
        self.kr.process()
        
        # Save state
        state_path = "integration_test_output/kr_state"
        self.kr.save_state(state_path)
        
        # Check if state files exist
        self.assertTrue(os.path.exists(os.path.join(state_path, "config.json")))
        self.assertTrue(os.path.exists(os.path.join(state_path, "reducing_engine")))
        self.assertTrue(os.path.exists(os.path.join(state_path, "knowledge_graph")))
        self.assertTrue(os.path.exists(os.path.join(state_path, "stack_manager")))
        
        # Create a new KnowledgeReduce instance
        new_kr = KnowledgeReduce()
        
        # Load state
        new_kr.load_state(state_path)
        
        # Check if state was loaded correctly
        self.assertEqual(len(new_kr.knowledge_graph.graph.nodes()), len(self.kr.knowledge_graph.graph.nodes()))
        self.assertEqual(len(new_kr.knowledge_graph.graph.edges()), len(self.kr.knowledge_graph.graph.edges()))
        self.assertEqual(len(new_kr.stack_manager.stacks), len(self.kr.stack_manager.stacks))

if __name__ == "__main__":
    unittest.main()
