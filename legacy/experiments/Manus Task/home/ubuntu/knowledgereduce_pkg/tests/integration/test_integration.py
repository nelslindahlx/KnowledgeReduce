"""
Integration tests for the KnowledgeReduce framework.
"""

import unittest
import os
import tempfile
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for testing
import matplotlib.pyplot as plt
from knowledgereduce.core.core import ReliabilityRating
from knowledgereduce.integration import KnowledgeReduceFramework

class TestIntegration(unittest.TestCase):
    """Integration tests for the KnowledgeReduce framework."""
    
    def setUp(self):
        """Set up a test framework instance."""
        self.framework = KnowledgeReduceFramework()
        
        # Add some test facts
        self.framework.add_fact(
            fact_id="fact1",
            fact_statement="The sky is blue due to Rayleigh scattering of sunlight",
            category="Science",
            tags=["sky", "color", "physics"],
            reliability_rating=ReliabilityRating.VERIFIED,
            source_id="source1",
            source_title="Test Source",
            author_creator="Test Author",
            publication_date="2023-01-01",
            url_reference="http://example.com"
        )
        
        self.framework.add_fact(
            fact_id="fact2",
            fact_statement="Water boils at 100°C at standard atmospheric pressure",
            category="Science",
            tags=["water", "temperature", "physics"],
            reliability_rating=ReliabilityRating.VERIFIED,
            source_id="source1",
            source_title="Test Source",
            author_creator="Test Author",
            publication_date="2023-01-01",
            url_reference="http://example.com"
        )
        
        self.framework.add_fact(
            fact_id="fact3",
            fact_statement="Gold is a precious metal with atomic number 79",
            category="Chemistry",
            tags=["gold", "metal", "element"],
            reliability_rating=ReliabilityRating.LIKELY_TRUE,
            source_id="source2",
            source_title="Another Source",
            author_creator="Another Author",
            publication_date="2023-01-01",
            url_reference="http://example.com/another"
        )
        
        # Add relationships
        self.framework.add_relationship("fact1", "fact2", "related_to", weight=0.8)
        self.framework.add_relationship("fact2", "fact3", "related_to", weight=0.6)
        
        # Set up a stackable framework
        self.stackable_framework = KnowledgeReduceFramework(use_stackable=True)
        
        # Add a fact to the base layer
        self.stackable_framework.add_fact(
            fact_id="fact1",
            fact_statement="The sky is blue",
            category="Science",
            tags=["sky", "color"],
            reliability_rating=ReliabilityRating.VERIFIED,
            layer_name="base"
        )
        
        # Add a new layer
        self.stackable_framework.add_layer("layer1", parent_layer="base")
        
        # Add a fact to the new layer
        self.stackable_framework.add_fact(
            fact_id="fact2",
            fact_statement="Water boils at 100°C",
            category="Science",
            tags=["water", "temperature"],
            reliability_rating=ReliabilityRating.VERIFIED,
            layer_name="layer1"
        )
        
        # Add a relationship
        self.stackable_framework.add_relationship(
            "fact1", "fact2", "related_to", weight=0.8, layer_name="layer1"
        )
    
    def test_save_load(self):
        """Test saving and loading a knowledge graph."""
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save to JSON
            json_path = os.path.join(temp_dir, "test_graph.json")
            self.framework.save_to_file(json_path)
            
            # Check that file was created
            self.assertTrue(os.path.exists(json_path))
            
            # Create new framework
            new_framework = KnowledgeReduceFramework()
            
            # Load from JSON
            new_framework.load_from_file(json_path)
            
            # Check that facts were loaded correctly
            fact1 = new_framework.get_fact("fact1")
            self.assertEqual(fact1["fact_statement"], "The sky is blue due to Rayleigh scattering of sunlight")
            
            # Check that relationships were loaded correctly
            self.assertTrue(new_framework.knowledge_graph.graph.has_edge("fact1", "fact2"))
    
    def test_save_load_stackable(self):
        """Test saving and loading a stackable knowledge graph."""
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save to JSON
            json_dir = os.path.join(temp_dir, "test_stackable_graph")
            self.stackable_framework.save_to_file(json_dir)
            
            # Check that directory was created
            self.assertTrue(os.path.exists(json_dir))
            
            # Create new framework
            new_framework = KnowledgeReduceFramework(use_stackable=True)
            
            # Load from JSON
            new_framework.load_from_file(json_dir)
            
            # Check that facts were loaded correctly
            fact1 = new_framework.get_fact("fact1", layer_name="base")
            self.assertEqual(fact1["fact_statement"], "The sky is blue")
            
            fact2 = new_framework.get_fact("fact2", layer_name="layer1")
            self.assertEqual(fact2["fact_statement"], "Water boils at 100°C")
            
            # Check that relationships were loaded correctly
            layer1 = new_framework.get_layer("layer1")
            self.assertTrue(layer1.graph.has_edge("fact1", "fact2"))
    
    def test_visualization(self):
        """Test visualization functionality."""
        # Visualize graph
        fig = self.framework.visualize()
        
        # Check that figure was created
        self.assertIsInstance(fig, plt.Figure)
        
        # Close figure
        plt.close(fig)
        
        # Visualize fact neighborhood
        fig = self.framework.visualize_fact("fact2")
        
        # Check that figure was created
        self.assertIsInstance(fig, plt.Figure)
        
        # Close figure
        plt.close(fig)
        
        # Get statistics
        stats = self.framework.get_statistics()
        
        # Check that statistics were created
        self.assertIsInstance(stats, dict)
        self.assertEqual(stats["num_nodes"], 3)
        self.assertEqual(stats["num_edges"], 2)
        
        # Visualize statistics
        fig = self.framework.visualize_statistics()
        
        # Check that figure was created
        self.assertIsInstance(fig, plt.Figure)
        
        # Close figure
        plt.close(fig)
    
    def test_analysis(self):
        """Test analysis functionality."""
        # Get central facts
        central_facts = self.framework.get_central_facts()
        
        # Check that central facts were identified
        self.assertIsInstance(central_facts, list)
        self.assertGreaterEqual(len(central_facts), 1)
        
        # Get fact clusters
        clusters = self.framework.get_fact_clusters()
        
        # Check that clusters were identified
        self.assertIsInstance(clusters, list)
        
        # Calculate similarity
        similarity = self.framework.calculate_similarity("fact1", "fact2")
        
        # Check that similarity was calculated
        self.assertIsInstance(similarity, float)
        self.assertGreaterEqual(similarity, 0.0)
        self.assertLessEqual(similarity, 1.0)
        
        # Find similar facts
        similar_facts = self.framework.find_similar_facts("fact1", threshold=0.1)
        
        # Check that similar facts were found
        self.assertIsInstance(similar_facts, list)
        
        # Analyze categories
        category_stats = self.framework.analyze_categories()
        
        # Check that category statistics were created
        self.assertIsInstance(category_stats, dict)
        self.assertEqual(category_stats["num_categories"], 2)
        
        # Find path
        path = self.framework.find_path("fact1", "fact3")
        
        # Check that path was found
        self.assertIsInstance(path, list)
        self.assertEqual(len(path), 3)
        self.assertEqual(path[0], "fact1")
        self.assertEqual(path[1], "fact2")
        self.assertEqual(path[2], "fact3")
        
        # Extract keywords
        keywords = self.framework.extract_keywords("fact1")
        
        # Check that keywords were extracted
        self.assertIsInstance(keywords, list)
        self.assertGreaterEqual(len(keywords), 1)
        
        # Analyze reliability
        reliability_stats = self.framework.analyze_reliability()
        
        # Check that reliability statistics were created
        self.assertIsInstance(reliability_stats, dict)
        
        # Analyze usage
        usage_stats = self.framework.analyze_usage()
        
        # Check that usage statistics were created
        self.assertIsInstance(usage_stats, dict)
    
    def test_query(self):
        """Test query functionality."""
        # Create query
        query = self.framework.query()
        
        # Filter by category
        results = query.filter_by_category("Science").execute()
        
        # Check that only Science facts were returned
        self.assertEqual(len(results), 2)
        for fact_id, _ in results:
            self.assertIn(fact_id, ["fact1", "fact2"])
        
        # Find facts by pattern
        results = self.framework.find_by_pattern(r"atomic number \d+")
        
        # Check that facts matching the pattern were found
        self.assertEqual(len(results), 1)
        self.assertIn("fact3", results)
        
        # Get facts with relationship
        results = self.framework.get_with_relationship("related_to")
        
        # Check that facts with the relationship were found
        self.assertEqual(len(results["sources"]), 2)
        self.assertIn("fact1", results["sources"])
        self.assertIn("fact2", results["sources"])
        
        # Get related facts
        results = self.framework.get_related("fact1")
        
        # Check that related facts were found
        self.assertEqual(len(results), 1)
        self.assertIn("fact2", results)
        
        # Find facts by quality
        results = self.framework.find_by_quality(50)
        
        # Check that facts with quality score >= 50 were found
        self.assertGreaterEqual(len(results), 1)
        
        # Get fact relationships
        results = self.framework.get_relationships("fact2")
        
        # Check that relationships were found
        self.assertEqual(len(results["outgoing_relationships"]), 1)
        self.assertEqual(results["outgoing_relationships"][0]["target_id"], "fact3")
        
        self.assertEqual(len(results["incoming_relationships"]), 1)
        self.assertEqual(results["incoming_relationships"][0]["source_id"], "fact1")
    
    def test_stackable_operations(self):
        """Test operations specific to stackable knowledge graphs."""
        # Get layer
        layer = self.stackable_framework.get_layer("base")
        
        # Check that layer is a KnowledgeGraph
        self.assertIsNotNone(layer)
        
        # Get merged graph
        merged_graph = self.stackable_framework.get_merged_graph()
        
        # Check that merged graph contains facts from all layers
        self.assertIn("fact1", merged_graph.graph)
        self.assertIn("fact2", merged_graph.graph)
        
        # Add a fact to layer1 that overrides a fact in base
        self.stackable_framework.add_fact(
            fact_id="fact1",
            fact_statement="The sky appears blue due to Rayleigh scattering",
            category="Science",
            tags=["sky", "color", "physics"],
            reliability_rating=ReliabilityRating.VERIFIED,
            layer_name="layer1"
        )
        
        # Get merged graph again
        merged_graph = self.stackable_framework.get_merged_graph()
        
        # Check that fact1 has the data from layer1 (override)
        self.assertEqual(
            merged_graph.graph.nodes["fact1"]["fact_statement"],
            "The sky appears blue due to Rayleigh scattering"
        )
        
        # Visualize specific layer
        fig = self.stackable_framework.visualize(layer_name="layer1")
        
        # Check that figure was created
        self.assertIsInstance(fig, plt.Figure)
        
        # Close figure
        plt.close(fig)
        
        # Get statistics for specific layer
        stats = self.stackable_framework.get_statistics(layer_name="layer1")
        
        # Check that statistics were created
        self.assertIsInstance(stats, dict)
        
        # Query specific layer
        query = self.stackable_framework.query(layer_name="layer1")
        
        # Filter by category
        results = query.filter_by_category("Science").execute()
        
        # Check that Science facts from layer1 were returned
        self.assertEqual(len(results), 2)
        for fact_id, _ in results:
            self.assertIn(fact_id, ["fact1", "fact2"])
    
    def test_end_to_end(self):
        """Test end-to-end workflow."""
        # Create a new framework
        framework = KnowledgeReduceFramework()
        
        # Add facts
        framework.add_fact(
            fact_id="fact1",
            fact_statement="Paris is the capital of France",
            category="Geography",
            tags=["paris", "france", "capital"],
            reliability_rating=ReliabilityRating.VERIFIED
        )
        
        framework.add_fact(
            fact_id="fact2",
            fact_statement="France is a country in Europe",
            category="Geography",
            tags=["france", "europe", "country"],
            reliability_rating=ReliabilityRating.VERIFIED
        )
        
        framework.add_fact(
            fact_id="fact3",
            fact_statement="The Eiffel Tower is in Paris",
            category="Landmarks",
            tags=["paris", "eiffel tower", "landmark"],
            reliability_rating=ReliabilityRating.VERIFIED
        )
        
        # Add relationships
        framework.add_relationship("fact1", "fact2", "related_to", weight=0.9)
        framework.add_relationship("fact1", "fact3", "related_to", weight=0.8)
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save to JSON
            json_path = os.path.join(temp_dir, "geography_graph.json")
            framework.save_to_file(json_path)
            
            # Create new framework
            new_framework = KnowledgeReduceFramework()
            
            # Load from JSON
            new_framework.load_from_file(json_path)
            
            # Analyze the graph
            central_facts = new_framework.get_central_facts()
            self.assertEqual(central_facts[0][0], "fact1")  # fact1 should be most central
            
            # Query the graph
            results = new_framework.query().filter_by_tag("paris").execute()
            self.assertEqual(len(results), 2)
            
            # Find path
            path = new_framework.find_path("fact2", "fact3")
            self.assertEqual(len(path), 3)
            self.assertEqual(path[0], "fact2")
            self.assertEqual(path[1], "fact1")
            self.assertEqual(path[2], "fact3")
            
            # Visualize
            fig = new_framework.visualize()
            self.assertIsInstance(fig, plt.Figure)
            plt.close(fig)

if __name__ == "__main__":
    unittest.main()
