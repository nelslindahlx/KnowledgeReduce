"""
Unit tests for the visualization module.
"""

import unittest
import os
import tempfile
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for testing
import matplotlib.pyplot as plt
from knowledgereduce.core.core import KnowledgeGraph, ReliabilityRating
from knowledgereduce.visualization.visualization import (
    visualize_graph, visualize_fact_neighborhood, 
    create_graph_statistics, visualize_graph_statistics
)

class TestVisualization(unittest.TestCase):
    """Test cases for the visualization module."""
    
    def setUp(self):
        """Set up a test knowledge graph."""
        self.kg = KnowledgeGraph()
        
        # Add some test facts
        self.kg.add_fact(
            fact_id="fact1",
            fact_statement="The sky is blue",
            category="Science",
            tags=["sky", "color"],
            date_recorded="2023-01-01",
            last_updated="2023-01-01",
            reliability_rating=ReliabilityRating.VERIFIED,
            source_id="source1",
            source_title="Test Source",
            author_creator="Test Author",
            publication_date="2023-01-01",
            url_reference="http://example.com",
            related_facts=[],
            contextual_notes="Test notes",
            access_level="public",
            usage_count=5,
            source_quality=8
        )
        
        self.kg.add_fact(
            fact_id="fact2",
            fact_statement="Water boils at 100°C",
            category="Science",
            tags=["water", "temperature"],
            date_recorded="2023-01-01",
            last_updated="2023-01-01",
            reliability_rating=ReliabilityRating.VERIFIED,
            source_id="source1",
            source_title="Test Source",
            author_creator="Test Author",
            publication_date="2023-01-01",
            url_reference="http://example.com",
            related_facts=[],
            contextual_notes="Test notes",
            access_level="public",
            usage_count=3,
            source_quality=7
        )
        
        self.kg.add_fact(
            fact_id="fact3",
            fact_statement="Gold is a metal",
            category="Chemistry",
            tags=["gold", "metal"],
            date_recorded="2023-01-01",
            last_updated="2023-01-01",
            reliability_rating=ReliabilityRating.LIKELY_TRUE,
            source_id="source2",
            source_title="Another Source",
            author_creator="Another Author",
            publication_date="2023-01-01",
            url_reference="http://example.com/another",
            related_facts=[],
            contextual_notes="Another notes",
            access_level="public",
            usage_count=2,
            source_quality=6
        )
        
        # Add relationships
        self.kg.add_relationship("fact1", "fact2", "related_to", weight=0.8)
        self.kg.add_relationship("fact2", "fact3", "related_to", weight=0.6)
    
    def test_visualize_graph(self):
        """Test visualizing a knowledge graph."""
        # Visualize graph
        fig = visualize_graph(self.kg)
        
        # Check that figure was created
        self.assertIsInstance(fig, plt.Figure)
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save figure to file
            fig_path = os.path.join(temp_dir, "test_graph.png")
            fig.savefig(fig_path)
            
            # Check that file was created
            self.assertTrue(os.path.exists(fig_path))
        
        # Close figure
        plt.close(fig)
    
    def test_visualize_graph_with_options(self):
        """Test visualizing a knowledge graph with various options."""
        # Visualize graph with options
        fig = visualize_graph(
            self.kg,
            max_nodes=2,
            layout='circular',
            node_size_by='usage_count',
            edge_width_by='weight',
            node_color_by='category',
            title="Test Graph",
            figsize=(8, 6),
            show_labels=True,
            label_font_size=10
        )
        
        # Check that figure was created
        self.assertIsInstance(fig, plt.Figure)
        
        # Close figure
        plt.close(fig)
    
    def test_visualize_graph_html(self):
        """Test visualizing a knowledge graph as HTML."""
        # Visualize graph as HTML
        html = visualize_graph(self.kg, return_html=True)
        
        # Check that HTML was created
        self.assertIsInstance(html, str)
        self.assertIn("<html>", html)
        self.assertIn("</html>", html)
        self.assertIn("data:image/png;base64,", html)
    
    def test_visualize_fact_neighborhood(self):
        """Test visualizing a fact neighborhood."""
        # Visualize fact neighborhood
        fig = visualize_fact_neighborhood(self.kg, "fact2")
        
        # Check that figure was created
        self.assertIsInstance(fig, plt.Figure)
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save figure to file
            fig_path = os.path.join(temp_dir, "test_neighborhood.png")
            fig.savefig(fig_path)
            
            # Check that file was created
            self.assertTrue(os.path.exists(fig_path))
        
        # Close figure
        plt.close(fig)
    
    def test_visualize_fact_neighborhood_with_options(self):
        """Test visualizing a fact neighborhood with various options."""
        # Visualize fact neighborhood with options
        fig = visualize_fact_neighborhood(
            self.kg,
            "fact2",
            depth=2,
            layout='circular',
            include_incoming=True,
            include_outgoing=True,
            title="Test Neighborhood",
            figsize=(8, 6),
            show_labels=True,
            label_font_size=10
        )
        
        # Check that figure was created
        self.assertIsInstance(fig, plt.Figure)
        
        # Close figure
        plt.close(fig)
    
    def test_visualize_fact_neighborhood_html(self):
        """Test visualizing a fact neighborhood as HTML."""
        # Visualize fact neighborhood as HTML
        html = visualize_fact_neighborhood(self.kg, "fact2", return_html=True)
        
        # Check that HTML was created
        self.assertIsInstance(html, str)
        self.assertIn("<html>", html)
        self.assertIn("</html>", html)
        self.assertIn("data:image/png;base64,", html)
    
    def test_create_graph_statistics(self):
        """Test creating graph statistics."""
        # Create graph statistics
        stats = create_graph_statistics(self.kg)
        
        # Check that statistics were created
        self.assertIsInstance(stats, dict)
        self.assertEqual(stats["num_nodes"], 3)
        self.assertEqual(stats["num_edges"], 2)
        self.assertIn("density", stats)
        self.assertIn("is_directed", stats)
        self.assertIn("is_connected", stats)
        
        # Check degree statistics
        self.assertIn("degree_stats", stats)
        self.assertIn("min_degree", stats["degree_stats"])
        self.assertIn("max_degree", stats["degree_stats"])
        self.assertIn("avg_degree", stats["degree_stats"])
        
        # Check category statistics
        self.assertIn("category_stats", stats)
        self.assertEqual(stats["category_stats"]["num_categories"], 2)
        self.assertEqual(stats["category_stats"]["category_counts"]["Science"], 2)
        self.assertEqual(stats["category_stats"]["category_counts"]["Chemistry"], 1)
    
    def test_visualize_graph_statistics(self):
        """Test visualizing graph statistics."""
        # Visualize graph statistics
        fig = visualize_graph_statistics(self.kg)
        
        # Check that figure was created
        self.assertIsInstance(fig, plt.Figure)
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save figure to file
            fig_path = os.path.join(temp_dir, "test_statistics.png")
            fig.savefig(fig_path)
            
            # Check that file was created
            self.assertTrue(os.path.exists(fig_path))
        
        # Close figure
        plt.close(fig)
    
    def test_visualize_graph_statistics_html(self):
        """Test visualizing graph statistics as HTML."""
        # Visualize graph statistics as HTML
        html = visualize_graph_statistics(self.kg, return_html=True)
        
        # Check that HTML was created
        self.assertIsInstance(html, str)
        self.assertIn("<html>", html)
        self.assertIn("</html>", html)
        self.assertIn("data:image/png;base64,", html)
        self.assertIn("<table", html)

if __name__ == "__main__":
    unittest.main()
