"""
Tests for the knowledge graph core functionality.
"""

import unittest
from knowledge_graph_pkg.core import KnowledgeGraph, ReliabilityRating
from datetime import datetime

class TestKnowledgeGraph(unittest.TestCase):

    def setUp(self):
        # Setup a KnowledgeGraph instance for each test
        self.kg = KnowledgeGraph()

    def test_graph_initialization(self):
        # Test if the graph is initialized correctly
        self.assertIsNotNone(self.kg.graph)
        self.assertEqual(len(self.kg.graph.nodes), 0)

    def test_adding_and_getting_fact(self):
        # Test adding a fact and then retrieving it
        fact_id = "fact1"
        self.kg.add_fact(fact_id, "The sky is blue", "Science", ["sky", "color"],
                         datetime.now(), datetime.now(),
                         ReliabilityRating.VERIFIED, "source1", "Nature Journal",
                         "Dr. Sky Watcher", datetime.now(), "https://example.com/fact1",
                         [], "Some notes", "public", 5)

        fact = self.kg.get_fact(fact_id)
        self.assertIsNotNone(fact)
        self.assertEqual(fact['fact_statement'], "The sky is blue")

    def test_fact_quality_score(self):
        # Test the quality score calculation
        fact_id = "fact2"
        self.kg.add_fact(fact_id, "Water boils at 100°C", "Science", ["water", "boiling point"],
                         datetime.now(), datetime.now(),
                         ReliabilityRating.VERIFIED, "source2", "Science Daily",
                         "Dr. H2O", datetime.now(), "https://example.com/fact2",
                         [], "Boiling point at sea level", "public", 10)

        fact = self.kg.get_fact(fact_id)
        expected_score = 10 * ReliabilityRating.VERIFIED.value + 2 * 10  # Based on your scoring logic
        self.assertEqual(fact['quality_score'], expected_score)

    # Additional tests can be added here for other functionalities like updating facts, error handling, etc.

if __name__ == '__main__':
    unittest.main()
