"""
Test suite for the KnowledgeReduce framework.

This module provides tests for validating the KnowledgeReduce implementation
against the paper's conceptual framework.
"""

import os
import json
import logging
import unittest
import networkx as nx
import matplotlib.pyplot as plt
from typing import Dict, List, Any

import sys
sys.path.append('..')

from knowledge_reduce import KnowledgeReduce
from knowledge_reduce.data_ingestion import FileConnector
from knowledge_reduce.mapping_engine.entity_extractors import SimpleEntityExtractor
from knowledge_reduce.mapping_engine.relationship_extractors import SimpleRelationshipExtractor
from knowledge_reduce.mapping_engine.disambiguation import SimpleDisambiguationEngine
from knowledge_reduce.reducing_engine.aggregators import SimpleAggregator, WeightedAggregator
from knowledge_reduce.reducing_engine.conflict_resolvers import ConfidenceBasedResolver, MajorityVotingResolver
from knowledge_reduce.knowledge_graph.stackable import StackableKnowledgeManager, KnowledgeStack

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TestDataIngestion(unittest.TestCase):
    """Test cases for the data ingestion phase."""
    
    def setUp(self):
        """Set up test environment."""
        # Create sample data
        os.makedirs("test_data", exist_ok=True)
        
        self.test_data = [
            {"id": "entity1", "name": "Test Entity 1", "type": "test"},
            {"id": "entity2", "name": "Test Entity 2", "type": "test"},
            {"id": "entity3", "name": "Test Entity 3", "type": "test"}
        ]
        
        with open("test_data/test_entities.json", "w") as f:
            json.dump(self.test_data, f, indent=2)
        
        # Initialize KnowledgeReduce
        self.kr = KnowledgeReduce()
    
    def test_file_connector(self):
        """Test FileConnector for data ingestion."""
        # Register file connector
        file_connector = FileConnector("test_data/test_entities.json", "json")
        self.kr.register_data_source(file_connector)
        
        # Ingest data
        raw_data = self.kr._ingest_data()
        
        # Verify data was ingested correctly
        self.assertEqual(len(raw_data), 3)
        self.assertEqual(raw_data[0]["id"], "entity1")
        self.assertEqual(raw_data[1]["name"], "Test Entity 2")
        self.assertEqual(raw_data[2]["type"], "test")
    
    def tearDown(self):
        """Clean up test environment."""
        # Remove test data
        if os.path.exists("test_data/test_entities.json"):
            os.remove("test_data/test_entities.json")
        
        if os.path.exists("test_data"):
            os.rmdir("test_data")

class TestMappingEngine(unittest.TestCase):
    """Test cases for the mapping engine."""
    
    def setUp(self):
        """Set up test environment."""
        # Create test data
        self.test_data = [
            {
                "id": "doc1",
                "text": "John Smith works at TechCorp as CEO.",
                "metadata": {"source": "test"}
            },
            {
                "id": "doc2",
                "text": "Jane Doe is the CTO of TechCorp.",
                "metadata": {"source": "test"}
            }
        ]
        
        # Initialize KnowledgeReduce
        self.kr = KnowledgeReduce()
        
        # Register entity and relationship extractors
        self.entity_extractor = SimpleEntityExtractor()
        self.relationship_extractor = SimpleRelationshipExtractor()
        self.kr.register_entity_extractor(self.entity_extractor)
        self.kr.register_relationship_extractor(self.relationship_extractor)
    
    def test_entity_extraction(self):
        """Test entity extraction."""
        # Extract entities
        entities = self.entity_extractor.extract(self.test_data)
        
        # Verify entities were extracted correctly
        self.assertGreaterEqual(len(entities), 4)  # At least 4 entities (John Smith, TechCorp, Jane Doe, CTO)
        
        # Check if key entities are present
        entity_texts = [entity.get("text") for entity in entities]
        self.assertIn("John Smith", entity_texts)
        self.assertIn("TechCorp", entity_texts)
        self.assertIn("Jane Doe", entity_texts)
    
    def test_relationship_extraction(self):
        """Test relationship extraction."""
        # Extract entities first
        entities = self.entity_extractor.extract(self.test_data)
        
        # Extract relationships
        relationships = self.relationship_extractor.extract(self.test_data, entities)
        
        # Verify relationships were extracted correctly
        self.assertGreaterEqual(len(relationships), 2)  # At least 2 relationships
        
        # Check if key relationships are present
        for relationship in relationships:
            source_id = relationship.get("source")
            target_id = relationship.get("target")
            rel_type = relationship.get("type")
            
            source_entity = next((e for e in entities if e.get("id") == source_id), None)
            target_entity = next((e for e in entities if e.get("id") == target_id), None)
            
            if source_entity and target_entity:
                if source_entity.get("text") == "John Smith" and target_entity.get("text") == "TechCorp":
                    self.assertEqual(rel_type, "works_at")
                elif source_entity.get("text") == "Jane Doe" and target_entity.get("text") == "TechCorp":
                    self.assertEqual(rel_type, "works_at")
    
    def test_disambiguation(self):
        """Test entity disambiguation."""
        # Create test data with duplicate entities
        test_data_with_duplicates = [
            {
                "id": "doc1",
                "text": "TechCorp is a technology company.",
                "metadata": {"source": "test"}
            },
            {
                "id": "doc2",
                "text": "TechCorp Inc. is based in San Francisco.",
                "metadata": {"source": "test"}
            }
        ]
        
        # Extract entities
        entities = self.entity_extractor.extract(test_data_with_duplicates)
        
        # Check if TechCorp appears multiple times
        techcorp_entities = [e for e in entities if e.get("text") in ["TechCorp", "TechCorp Inc."]]
        self.assertGreaterEqual(len(techcorp_entities), 2)
        
        # Set up disambiguation engine
        disambiguation_engine = SimpleDisambiguationEngine()
        self.kr.set_disambiguation_engine(disambiguation_engine)
        
        # Disambiguate entities
        disambiguated_entities = disambiguation_engine.disambiguate(entities)
        
        # Check if duplicates were merged
        techcorp_entities_after = [e for e in disambiguated_entities if e.get("text") in ["TechCorp", "TechCorp Inc."]]
        self.assertLessEqual(len(techcorp_entities_after), len(techcorp_entities))

class TestReducingEngine(unittest.TestCase):
    """Test cases for the reducing engine."""
    
    def setUp(self):
        """Set up test environment."""
        # Create test data
        self.entities = [
            {"id": "e1", "text": "TechCorp", "type": "company", "confidence": 0.8, "source": "source1"},
            {"id": "e1", "text": "TechCorp Inc.", "type": "company", "confidence": 0.7, "source": "source2"},
            {"id": "e2", "text": "John Smith", "type": "person", "confidence": 0.9, "source": "source1"},
            {"id": "e3", "text": "Jane Doe", "type": "person", "confidence": 0.85, "source": "source2"}
        ]
        
        self.relationships = [
            {"id": "r1", "source": "e2", "target": "e1", "type": "works_at", "confidence": 0.8, "data_source": "source1"},
            {"id": "r2", "source": "e3", "target": "e1", "type": "works_at", "confidence": 0.75, "data_source": "source2"}
        ]
        
        self.mapped_data = {
            "entities": self.entities,
            "relationships": self.relationships
        }
        
        # Initialize KnowledgeReduce
        self.kr = KnowledgeReduce()
        
        # Set up reducing engine
        self.reducing_engine = self.kr.reducing_engine
    
    def test_entity_aggregation(self):
        """Test entity aggregation."""
        # Register aggregator
        aggregator = SimpleAggregator()
        self.reducing_engine.register_aggregator(aggregator)
        
        # Reduce data
        reduced_data = self.reducing_engine.reduce(self.mapped_data)
        
        # Verify entities were aggregated correctly
        self.assertEqual(len(reduced_data["entities"]), 3)  # 3 unique entities after aggregation
        
        # Check if TechCorp entities were merged
        techcorp_entity = next((e for e in reduced_data["entities"] if e.get("id") == "e1"), None)
        self.assertIsNotNone(techcorp_entity)
        self.assertEqual(techcorp_entity.get("text"), "TechCorp")  # Should keep the text from the higher confidence entity
    
    def test_conflict_resolution(self):
        """Test conflict resolution."""
        # Register conflict resolver
        conflict_resolver = ConfidenceBasedResolver()
        self.reducing_engine.register_conflict_resolver(conflict_resolver)
        
        # Reduce data
        reduced_data = self.reducing_engine.reduce(self.mapped_data)
        
        # Verify conflicts were resolved correctly
        techcorp_entity = next((e for e in reduced_data["entities"] if e.get("id") == "e1"), None)
        self.assertIsNotNone(techcorp_entity)
        self.assertEqual(techcorp_entity.get("confidence"), 0.8)  # Should keep the higher confidence value
    
    def test_weighted_aggregation(self):
        """Test weighted aggregation."""
        # Register weighted aggregator
        aggregator = WeightedAggregator()
        self.reducing_engine.register_aggregator(aggregator)
        
        # Reduce data
        reduced_data = self.reducing_engine.reduce(self.mapped_data)
        
        # Verify entities were aggregated with weights
        techcorp_entity = next((e for e in reduced_data["entities"] if e.get("id") == "e1"), None)
        self.assertIsNotNone(techcorp_entity)
        self.assertEqual(techcorp_entity.get("confidence"), 0.8)  # Should keep the higher confidence value

class TestKnowledgeGraph(unittest.TestCase):
    """Test cases for the knowledge graph."""
    
    def setUp(self):
        """Set up test environment."""
        # Create test data
        self.entities = [
            {"id": "e1", "text": "TechCorp", "type": "company"},
            {"id": "e2", "text": "John Smith", "type": "person"},
            {"id": "e3", "text": "Jane Doe", "type": "person"}
        ]
        
        self.relationships = [
            {"id": "r1", "source": "e2", "target": "e1", "type": "works_at"},
            {"id": "r2", "source": "e3", "target": "e1", "type": "works_at"}
        ]
        
        self.reduced_data = {
            "entities": self.entities,
            "relationships": self.relationships
        }
        
        # Initialize KnowledgeReduce
        self.kr = KnowledgeReduce()
        
        # Set up knowledge graph
        self.knowledge_graph = self.kr.knowledge_graph
    
    def test_graph_building(self):
        """Test knowledge graph building."""
        # Build knowledge graph
        self.knowledge_graph.build(self.reduced_data)
        
        # Verify graph was built correctly
        self.assertEqual(len(self.knowledge_graph.graph.nodes), 3)  # 3 nodes
        self.assertEqual(len(self.knowledge_graph.graph.edges), 2)  # 2 edges
        
        # Check if nodes have correct attributes
        self.assertEqual(self.knowledge_graph.graph.nodes["e1"]["text"], "TechCorp")
        self.assertEqual(self.knowledge_graph.graph.nodes["e2"]["text"], "John Smith")
        
        # Check if edges have correct attributes
        edge_data = self.knowledge_graph.graph.get_edge_data("e2", "e1", "works_at")
        self.assertIsNotNone(edge_data)
    
    def test_graph_querying(self):
        """Test knowledge graph querying."""
        # Build knowledge graph
        self.knowledge_graph.build(self.reduced_data)
        
        # Query graph
        query_results = self.knowledge_graph.query("MATCH (n) RETURN n")
        
        # Verify query results
        self.assertIn("nodes", query_results)
        self.assertIn("edges", query_results)
        self.assertEqual(len(query_results["nodes"]), 3)
    
    def test_graph_export(self):
        """Test knowledge graph export."""
        # Build knowledge graph
        self.knowledge_graph.build(self.reduced_data)
        
        # Export graph
        os.makedirs("test_output", exist_ok=True)
        export_path = self.knowledge_graph.export("test_output/test_graph.json", "json")
        
        # Verify export
        self.assertTrue(os.path.exists(export_path))
        
        # Clean up
        if os.path.exists(export_path):
            os.remove(export_path)
        
        if os.path.exists("test_output"):
            os.rmdir("test_output")

class TestStackableKnowledge(unittest.TestCase):
    """Test cases for stackable knowledge."""
    
    def setUp(self):
        """Set up test environment."""
        # Initialize StackableKnowledgeManager
        self.stack_manager = StackableKnowledgeManager()
    
    def test_stack_creation(self):
        """Test knowledge stack creation."""
        # Create stacks
        stack1 = self.stack_manager.create_stack("stack1", "Test Stack 1")
        stack2 = self.stack_manager.create_stack("stack2", "Test Stack 2")
        
        # Verify stacks were created correctly
        self.assertEqual(len(self.stack_manager.stacks), 2)
        self.assertEqual(stack1.name, "stack1")
        self.assertEqual(stack2.description, "Test Stack 2")
    
    def test_stack_hierarchy(self):
        """Test knowledge stack hierarchy."""
        # Create stacks
        self.stack_manager.create_stack("parent_stack", "Parent Stack")
        self.stack_manager.create_stack("child_stack", "Child Stack")
        
        # Create hierarchy
        self.stack_manager.create_stack_hierarchy("parent_stack", "child_stack")
        
        # Verify hierarchy was created correctly
        parent_stack = self.stack_manager.get_stack("parent_stack")
        child_stack = self.stack_manager.get_stack("child_stack")
        
        self.assertIn("child_stack", parent_stack.child_stacks)
        self.assertIn("parent_stack", child_stack.parent_stacks)
    
    def test_stack_merging(self):
        """Test knowledge stack merging."""
        # Create stacks
        stack1 = self.stack_manager.create_stack("stack1", "Test Stack 1")
        stack2 = self.stack_manager.create_stack("stack2", "Test Stack 2")
        
        # Add entities and relationships to stacks
        stack1.add_entity("e1")
        stack1.add_entity("e2")
        stack1.add_relationship("r1")
        
        stack2.add_entity("e2")
        stack2.add_entity("e3")
        stack2.add_relationship("r2")
        
        # Merge stacks
        merged_stack = self.stack_manager.merge_stacks(["stack1", "stack2"], "merged_stack", "union")
        
        # Verify merge was performed correctly
        self.assertEqual(len(merged_stack.entities), 3)  # e1, e2, e3
        self.assertEqual(len(merged_stack.relationships), 2)  # r1, r2
        
        # Test intersection merge
        intersection_stack = self.stack_manager.merge_stacks(["stack1", "stack2"], "intersection_stack", "intersection")
        
        # Verify intersection was performed correctly
        self.assertEqual(len(intersection_stack.entities), 1)  # Only e2 is in both stacks
        self.assertEqual(len(intersection_stack.relationships), 0)  # No common relationships
    
    def test_stack_lineage(self):
        """Test knowledge stack lineage."""
        # Create stacks with hierarchy
        self.stack_manager.create_stack("grandparent", "Grandparent Stack")
        self.stack_manager.create_stack("parent", "Parent Stack")
        self.stack_manager.create_stack("child", "Child Stack")
        
        self.stack_manager.create_stack_hierarchy("grandparent", "parent")
        self.stack_manager.create_stack_hierarchy("parent", "child")
        
        # Get lineage
        lineage = self.stack_manager.get_stack_lineage("child")
        
        # Verify lineage
        self.assertIn("grandparent", lineage["ancestors"])
        self.assertIn("parent", lineage["ancestors"])
        self.assertEqual(len(lineage["descendants"]), 0)  # Child has no descendants
        
        # Get lineage for parent
        parent_lineage = self.stack_manager.get_stack_lineage("parent")
        
        # Verify parent lineage
        self.assertIn("grandparent", parent_lineage["ancestors"])
        self.assertIn("child", parent_lineage["descendants"])

class TestIntegration(unittest.TestCase):
    """Integration tests for the KnowledgeReduce framework."""
    
    def setUp(self):
        """Set up test environment."""
        # Create sample data
        os.makedirs("test_data", exist_ok=True)
        
        self.companies = [
            {"id": "comp1", "name": "TechCorp", "industry": "Technology"},
            {"id": "comp2", "name": "FinBank", "industry": "Finance"}
        ]
        
        with open("test_data/companies.json", "w") as f:
            json.dump(self.companies, f, indent=2)
        
        self.people = [
            {"id": "person1", "name": "John Smith", "company": "comp1", "position": "CEO"},
            {"id": "person2", "name": "Jane Doe", "company": "comp1", "position": "CTO"},
            {"id": "person3", "name": "Bob Johnson", "company": "comp2", "position": "CFO"}
        ]
        
        with open("test_data/people.json", "w") as f:
            json.dump(self.people, f, indent=2)
        
        # Initialize KnowledgeReduce
        self.kr = KnowledgeReduce()
    
    def test_full_pipeline(self):
        """Test the full KnowledgeReduce pipeline."""
        # Configure data ingestion
        companies_connector = FileConnector("test_data/companies.json", "json")
        people_connector = FileConnector("test_data/people.json", "json")
        
        self.kr.register_data_source(companies_connector)
        self.kr.register_data_source(people_connector)
        
        # Configure mapping engine
        entity_extractor = SimpleEntityExtractor()
        relationship_extractor = SimpleRelationshipExtractor()
        disambiguation_engine = SimpleDisambiguationEngine()
        
        self.kr.register_entity_extractor(entity_extractor)
        self.kr.register_relationship_extractor(relationship_extractor)
        self.kr.set_disambiguation_engine(disambiguation_engine)
        
        # Configure reducing engine
        aggregator = SimpleAggregator()
        conflict_resolver = ConfidenceBasedResolver()
        
        self.kr.reducing_engine.register_aggregator(aggregator)
        self.kr.reducing_engine.register_conflict_resolver(conflict_resolver)
        
        # Create knowledge stacks
        self.kr.create_stack("companies_stack", "Stack for company data")
        self.kr.create_stack("people_stack", "Stack for people data")
        
        # Process data
        self.kr.set_current_stack("companies_stack")
        companies_data = self.kr.process(["companies_connector"])
        
        self.kr.set_current_stack("people_stack")
        people_data = self.kr.process(["people_connector"])
        
        # Merge stacks
        merged_stack = self.kr.merge_stacks(["companies_stack", "people_stack"], "merged_stack", "union")
        
        # Verify results
        self.assertIsNotNone(companies_data)
        self.assertIsNotNone(people_data)
        self.assertIsNotNone(merged_stack)
        
        # Export knowledge graph
        os.makedirs("test_output", exist_ok=True)
        export_path = self.kr.export_knowledge_graph("test_output/full_pipeline_graph.json", "json")
        
        # Verify export
        self.assertTrue(os.path.exists(export_path))
    
    def tearDown(self):
        """Clean up test environment."""
        # Remove test data
        if os.path.exists("test_data/companies.json"):
            os.remove("test_data/companies.json")
        
        if os.path.exists("test_data/people.json"):
            os.remove("test_data/people.json")
        
        if os.path.exists("test_data"):
            os.rmdir("test_data")
        
        # Remove test output
        if os.path.exists("test_output/full_pipeline_graph.json"):
            os.remove("test_output/full_pipeline_graph.json")
        
        if os.path.exists("test_output"):
            os.rmdir("test_output")

if __name__ == "__main__":
    unittest.main()
