"""
Tests for the core functionality of the KnowledgeReduce framework.
"""
import sys
import os
import unittest
from datetime import datetime

# Add parent directory to path so we can import the implementation
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core import KnowledgeGraph, ReliabilityRating

class TestKnowledgeGraph(unittest.TestCase):
    def setUp(self):
        # Setup a KnowledgeGraph instance for each test
        self.kg = KnowledgeGraph()
        
        # Add some test facts
        self.kg.add_fact(
            fact_id="fact1",
            fact_statement="The sky is blue",
            category="Science",
            tags=["sky", "color"],
            date_recorded=datetime.now(),
            last_updated=datetime.now(),
            reliability_rating=ReliabilityRating.VERIFIED,
            source_id="source1",
            source_title="Nature Journal",
            author_creator="Dr. Sky Watcher",
            publication_date=datetime.now(),
            url_reference="https://example.com/fact1",
            related_facts=[],
            contextual_notes="Some notes",
            access_level="public",
            usage_count=5
        )
        
        self.kg.add_fact(
            fact_id="fact2",
            fact_statement="Water boils at 100°C",
            category="Science",
            tags=["water", "boiling point"],
            date_recorded=datetime.now(),
            last_updated=datetime.now(),
            reliability_rating=ReliabilityRating.VERIFIED,
            source_id="source2",
            source_title="Science Daily",
            author_creator="Dr. H2O",
            publication_date=datetime.now(),
            url_reference="https://example.com/fact2",
            related_facts=[],
            contextual_notes="Boiling point at sea level",
            access_level="public",
            usage_count=10
        )

    def test_graph_initialization(self):
        # Test if the graph is initialized correctly
        kg = KnowledgeGraph()
        self.assertIsNotNone(kg.graph)
        self.assertEqual(len(kg.graph.nodes), 0)

    def test_adding_and_getting_fact(self):
        # Test adding a fact and then retrieving it
        fact = self.kg.get_fact("fact1")
        self.assertIsNotNone(fact)
        self.assertEqual(fact['fact_statement'], "The sky is blue")

    def test_fact_quality_score(self):
        # Test the quality score calculation
        fact = self.kg.get_fact("fact2")
        self.assertIsNotNone(fact.get('quality_score'))
        self.assertTrue(fact['quality_score'] > 0)
    
    def test_update_fact(self):
        # Test updating a fact
        self.kg.update_fact("fact1", fact_statement="The sky appears blue")
        fact = self.kg.get_fact("fact1")
        self.assertEqual(fact['fact_statement'], "The sky appears blue")
    
    def test_add_relationship(self):
        # Test adding a relationship between facts
        self.kg.add_relationship("fact1", "fact2", "related_to", weight=0.8)
        
        # Check if relationship exists
        relationships = self.kg.get_relationships("fact1")
        self.assertEqual(len(relationships['outgoing']), 1)
        self.assertEqual(relationships['outgoing'][0]['target_id'], "fact2")
        self.assertEqual(relationships['outgoing'][0]['relationship_type'], "related_to")
        self.assertEqual(relationships['outgoing'][0]['weight'], 0.8)

if __name__ == '__main__':
    unittest.main()