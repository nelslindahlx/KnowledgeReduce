"""
Test script for the KnowledgeReduce framework.
This script tests the functionality of the integrated framework.
"""
import os
import sys
import unittest
import tempfile
import matplotlib.pyplot as plt
from datetime import datetime

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core import KnowledgeGraph, ReliabilityRating
from framework import KnowledgeReduceFramework

class TestKnowledgeReduceFramework(unittest.TestCase):
    def setUp(self):
        # Create a new KnowledgeReduce framework instance
        self.kr = KnowledgeReduceFramework()
        
        # Add some test facts
        self.kr.add_fact(
            fact_id="fact1",
            fact_statement="The Earth orbits the Sun",
            category="Astronomy",
            tags=["Earth", "Sun", "orbit"],
            reliability_rating=ReliabilityRating.VERIFIED,
            source_title="Astronomy Textbook",
            author_creator="Dr. Astronomer"
        )
        
        self.kr.add_fact(
            fact_id="fact2",
            fact_statement="The Moon orbits the Earth",
            category="Astronomy",
            tags=["Moon", "Earth", "orbit"],
            reliability_rating=ReliabilityRating.VERIFIED,
            source_title="Astronomy Textbook",
            author_creator="Dr. Astronomer"
        )
        
        self.kr.add_fact(
            fact_id="fact3",
            fact_statement="The Earth has one natural satellite",
            category="Astronomy",
            tags=["Earth", "Moon", "satellite"],
            reliability_rating=ReliabilityRating.VERIFIED,
            source_title="Astronomy Facts",
            author_creator="Space Agency"
        )
        
        # Add relationships between facts
        self.kr.knowledge_graph.add_relationship("fact1", "fact2", "related_to", weight=0.9)
        self.kr.knowledge_graph.add_relationship("fact2", "fact3", "supports", weight=0.8)
    
    def test_add_fact(self):
        # Test adding a fact
        self.kr.add_fact(
            fact_id="fact4",
            fact_statement="Jupiter is the largest planet in our solar system",
            category="Astronomy",
            tags=["Jupiter", "planet", "solar system"],
            reliability_rating=ReliabilityRating.VERIFIED
        )
        
        # Check if fact was added
        fact = self.kr.knowledge_graph.get_fact("fact4")
        self.assertIsNotNone(fact)
        self.assertEqual(fact['fact_statement'], "Jupiter is the largest planet in our solar system")
    
    def test_get_statistics(self):
        # Test getting statistics
        stats = self.kr.get_statistics()
        self.assertIn('num_facts', stats)
        self.assertIn('num_relationships', stats)
        self.assertEqual(stats['num_facts'], 3)
        self.assertEqual(stats['num_relationships'], 2)
    
    def test_central_facts(self):
        # Test finding central facts
        central_facts = self.kr.get_central_facts(method="betweenness")
        self.assertEqual(len(central_facts), 3)  # Should return all facts
        
        # fact2 should be most central as it connects fact1 and fact3
        self.assertEqual(central_facts[0][0], "fact2")
    
    def test_query(self):
        # Test query functionality
        query_results = self.kr.query().filter_by_category("Astronomy").filter_by_text("Earth").execute()
        self.assertEqual(len(query_results), 3)  # All facts mention Earth
        
        query_results = self.kr.query().filter_by_text("Moon").execute()
        self.assertEqual(len(query_results), 2)  # Two facts mention Moon
    
    def test_find_by_pattern(self):
        # Test finding facts by pattern
        orbit_facts = self.kr.find_by_pattern("orbit")
        self.assertEqual(len(orbit_facts), 2)  # Two facts mention orbit
        self.assertIn("fact1", orbit_facts)
        self.assertIn("fact2", orbit_facts)
    
    def test_get_related(self):
        # Test getting related facts
        related = self.kr.get_related("fact1")
        self.assertEqual(len(related), 1)  # fact1 is related to fact2
        self.assertEqual(related[0], "fact2")
        
        related = self.kr.get_related("fact2", max_depth=2)
        self.assertEqual(len(related), 2)  # fact2 is related to fact1 and fact3
        self.assertIn("fact1", related)
        self.assertIn("fact3", related)
    
    def test_save_load(self):
        # Test saving and loading
        with tempfile.NamedTemporaryFile(suffix='.gexf', delete=False) as tmp:
            filepath = tmp.name
        
        try:
            # Save
            self.kr.save_to_file(filepath)
            self.assertTrue(os.path.exists(filepath))
            
            # Load into a new instance
            kr2 = KnowledgeReduceFramework()
            kr2.load_from_file(filepath)
            
            # Check if facts were loaded correctly
            self.assertEqual(len(kr2.knowledge_graph.graph.nodes), 3)
            self.assertEqual(len(kr2.knowledge_graph.graph.edges), 2)
            
            fact = kr2.knowledge_graph.get_fact("fact1")
            self.assertEqual(fact['fact_statement'], "The Earth orbits the Sun")
        finally:
            # Clean up
            if os.path.exists(filepath):
                os.remove(filepath)
    
    def test_visualization(self):
        # Test visualization (just check if it runs without errors)
        try:
            fig = self.kr.visualize()
            self.assertIsNotNone(fig)
            plt.close(fig)
            
            fig = self.kr.visualize_fact("fact2")
            self.assertIsNotNone(fig)
            plt.close(fig)
        except Exception as e:
            self.fail(f"Visualization raised exception: {e}")
    
    def test_analyze_categories(self):
        # Test category analysis
        categories = self.kr.analyze_categories()
        self.assertEqual(len(categories), 1)  # Only one category: Astronomy
        self.assertEqual(categories['Astronomy'], 3)  # Three facts in Astronomy category

if __name__ == '__main__':
    unittest.main()
