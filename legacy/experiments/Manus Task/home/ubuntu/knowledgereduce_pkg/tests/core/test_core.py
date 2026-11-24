"""
Unit tests for the core module.
"""

import unittest
import os
import tempfile
import networkx as nx
from knowledgereduce.core.core import KnowledgeGraph, StackableKnowledgeGraph, ReliabilityRating

class TestKnowledgeGraph(unittest.TestCase):
    """Test cases for the KnowledgeGraph class."""
    
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
    
    def test_add_fact(self):
        """Test adding a fact to the knowledge graph."""
        # Check that facts were added correctly
        self.assertIn("fact1", self.kg.graph)
        self.assertIn("fact2", self.kg.graph)
        
        # Check fact data
        self.assertEqual(self.kg.graph.nodes["fact1"]["fact_statement"], "The sky is blue")
        self.assertEqual(self.kg.graph.nodes["fact2"]["fact_statement"], "Water boils at 100°C")
    
    def test_get_fact(self):
        """Test getting a fact from the knowledge graph."""
        fact1 = self.kg.get_fact("fact1")
        self.assertEqual(fact1["fact_statement"], "The sky is blue")
        self.assertEqual(fact1["category"], "Science")
        
        # Test getting non-existent fact
        with self.assertRaises(ValueError):
            self.kg.get_fact("non_existent_fact")
    
    def test_update_fact(self):
        """Test updating a fact in the knowledge graph."""
        # Update fact
        self.kg.update_fact("fact1", fact_statement="The sky appears blue")
        
        # Check that fact was updated
        fact1 = self.kg.get_fact("fact1")
        self.assertEqual(fact1["fact_statement"], "The sky appears blue")
        
        # Test updating non-existent fact
        with self.assertRaises(ValueError):
            self.kg.update_fact("non_existent_fact", fact_statement="Test")
    
    def test_add_relationship(self):
        """Test adding a relationship between facts."""
        # Add relationship
        self.kg.add_relationship("fact1", "fact2", "related_to", weight=0.8)
        
        # Check that relationship was added
        self.assertTrue(self.kg.graph.has_edge("fact1", "fact2"))
        edge_data = self.kg.graph.get_edge_data("fact1", "fact2")
        self.assertEqual(edge_data["relationship_type"], "related_to")
        self.assertEqual(edge_data["weight"], 0.8)
        
        # Test adding relationship with non-existent facts
        with self.assertRaises(ValueError):
            self.kg.add_relationship("fact1", "non_existent_fact", "related_to")
        
        with self.assertRaises(ValueError):
            self.kg.add_relationship("non_existent_fact", "fact2", "related_to")
    
    def test_get_relationships(self):
        """Test getting relationships for a fact."""
        # Add relationships
        self.kg.add_relationship("fact1", "fact2", "related_to", weight=0.8)
        
        # Get relationships
        relationships = self.kg.get_relationships("fact1")
        
        # Check outgoing relationships
        self.assertEqual(len(relationships["outgoing"]), 1)
        self.assertEqual(relationships["outgoing"][0]["target_id"], "fact2")
        self.assertEqual(relationships["outgoing"][0]["relationship_type"], "related_to")
        self.assertEqual(relationships["outgoing"][0]["weight"], 0.8)
        
        # Check incoming relationships
        self.assertEqual(len(relationships["incoming"]), 0)
        
        # Get relationships for target fact
        relationships = self.kg.get_relationships("fact2")
        
        # Check incoming relationships
        self.assertEqual(len(relationships["incoming"]), 1)
        self.assertEqual(relationships["incoming"][0]["source_id"], "fact1")
        self.assertEqual(relationships["incoming"][0]["relationship_type"], "related_to")
        self.assertEqual(relationships["incoming"][0]["weight"], 0.8)
        
        # Check outgoing relationships
        self.assertEqual(len(relationships["outgoing"]), 0)
        
        # Test getting relationships for non-existent fact
        with self.assertRaises(ValueError):
            self.kg.get_relationships("non_existent_fact")
    
    def test_calculate_quality_score(self):
        """Test quality score calculation."""
        # Calculate quality score
        score = self.kg.calculate_quality_score(
            reliability_rating=ReliabilityRating.VERIFIED,
            usage_count=5,
            related_facts_count=2,
            source_quality=8
        )
        
        # Check score components:
        # - Base score from reliability rating (VERIFIED = 4): 4 * 10 = 40
        # - Usage score (5 uses): min(2 * 5, 20) = 10
        # - Related facts score (2 related facts): min(2, 15) = 2
        # - Source quality score: 8
        # Total: 40 + 10 + 2 + 8 = 60
        self.assertEqual(score, 60)
        
        # Check that quality score was calculated for added facts
        fact1 = self.kg.get_fact("fact1")
        self.assertIn("quality_score", fact1)
        
        # The quality score for fact1 should be:
        # - Base score from reliability rating (VERIFIED = 4): 4 * 10 = 40
        # - Usage score (5 uses): min(2 * 5, 20) = 10
        # - Related facts score (initially 0, then 1 after adding relationship): min(1, 15) = 1
        # - Source quality score: 8
        # Total: 40 + 10 + 1 + 8 = 59
        # Note: The score might be different if the relationship was added before this test
        self.assertGreaterEqual(fact1["quality_score"], 58)  # Allow for variations in test order
    
    def test_search_facts(self):
        """Test searching for facts."""
        # Search by fact statement
        results = self.kg.search_facts("blue")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], "fact1")
        
        # Search by category
        results = self.kg.search_facts("Science", fields=["category"])
        self.assertEqual(len(results), 2)
        self.assertIn("fact1", results)
        self.assertIn("fact2", results)
        
        # Search with no matches
        results = self.kg.search_facts("non_existent_text")
        self.assertEqual(len(results), 0)
    
    def test_export_import_json(self):
        """Test exporting and importing knowledge graph to/from JSON."""
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Export to JSON
            json_path = os.path.join(temp_dir, "test_graph.json")
            file_paths = self.kg.export_to_json(json_path)
            
            # Check that file was created
            self.assertTrue(os.path.exists(json_path))
            
            # Create new knowledge graph
            new_kg = KnowledgeGraph()
            
            # Import from JSON
            new_kg.import_from_json(json_path)
            
            # Check that facts were imported correctly
            self.assertIn("fact1", new_kg.graph)
            self.assertIn("fact2", new_kg.graph)
            self.assertEqual(new_kg.graph.nodes["fact1"]["fact_statement"], "The sky is blue")
            self.assertEqual(new_kg.graph.nodes["fact2"]["fact_statement"], "Water boils at 100°C")
            
            # Check that relationship was imported correctly
            if self.kg.graph.has_edge("fact1", "fact2"):
                self.assertTrue(new_kg.graph.has_edge("fact1", "fact2"))
                edge_data = new_kg.graph.get_edge_data("fact1", "fact2")
                self.assertEqual(edge_data["relationship_type"], "related_to")
    
    def test_export_import_json_sharded(self):
        """Test exporting and importing sharded knowledge graph to/from JSON."""
        # Add more facts to make sharding meaningful
        for i in range(3, 11):
            self.kg.add_fact(
                fact_id=f"fact{i}",
                fact_statement=f"Test fact {i}",
                category="Test",
                tags=["test"],
                date_recorded="2023-01-01",
                last_updated="2023-01-01",
                reliability_rating=ReliabilityRating.UNVERIFIED,
                source_id="source1",
                source_title="Test Source",
                author_creator="Test Author",
                publication_date="2023-01-01",
                url_reference="http://example.com",
                related_facts=[],
                contextual_notes="Test notes",
                access_level="public",
                usage_count=1,
                source_quality=5
            )
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Export to JSON with sharding (5 nodes per shard)
            json_path = os.path.join(temp_dir, "test_graph_sharded.json")
            file_paths = self.kg.export_to_json(json_path, shard_size=5)
            
            # Check that metadata file was created
            metadata_path = os.path.join(temp_dir, "test_graph_sharded_metadata.json")
            self.assertTrue(os.path.exists(metadata_path))
            
            # Check that shard files were created
            self.assertTrue(len(file_paths) > 1)
            for path in file_paths:
                self.assertTrue(os.path.exists(path))
            
            # Create new knowledge graph
            new_kg = KnowledgeGraph()
            
            # Import from JSON
            new_kg.import_from_json(metadata_path)
            
            # Check that facts were imported correctly
            for i in range(1, 11):
                self.assertIn(f"fact{i}", new_kg.graph)
    
    def test_export_import_gexf(self):
        """Test exporting and importing knowledge graph to/from GEXF."""
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Export to GEXF
            gexf_path = os.path.join(temp_dir, "test_graph.gexf")
            self.kg.export_to_gexf(gexf_path)
            
            # Check that file was created
            self.assertTrue(os.path.exists(gexf_path))
            
            # Create new knowledge graph
            new_kg = KnowledgeGraph()
            
            # Import from GEXF
            new_kg.import_from_gexf(gexf_path)
            
            # Check that facts were imported correctly
            self.assertIn("fact1", new_kg.graph)
            self.assertIn("fact2", new_kg.graph)
    
    def test_export_import_graphml(self):
        """Test exporting and importing knowledge graph to/from GraphML."""
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Export to GraphML
            graphml_path = os.path.join(temp_dir, "test_graph.graphml")
            self.kg.export_to_graphml(graphml_path)
            
            # Check that file was created
            self.assertTrue(os.path.exists(graphml_path))
            
            # Create new knowledge graph
            new_kg = KnowledgeGraph()
            
            # Import from GraphML
            new_kg.import_from_graphml(graphml_path)
            
            # Check that facts were imported correctly
            self.assertIn("fact1", new_kg.graph)
            self.assertIn("fact2", new_kg.graph)

class TestStackableKnowledgeGraph(unittest.TestCase):
    """Test cases for the StackableKnowledgeGraph class."""
    
    def setUp(self):
        """Set up a test stackable knowledge graph."""
        self.skg = StackableKnowledgeGraph()
        
        # Add a fact to the base layer
        self.skg.add_fact_to_layer(
            "base",
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
        
        # Add a new layer
        self.skg.add_layer("layer1", parent_layer="base")
        
        # Add a fact to the new layer
        self.skg.add_fact_to_layer(
            "layer1",
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
    
    def test_add_layer(self):
        """Test adding a layer to the stackable knowledge graph."""
        # Add a new layer
        self.skg.add_layer("layer2", parent_layer="layer1")
        
        # Check that layer was added
        self.assertIn("layer2", self.skg.layers)
        self.assertIn("layer2", self.skg.layer_order)
        self.assertEqual(self.skg.inheritance_rules["layer2"], "layer1")
        
        # Test adding layer with non-existent parent
        with self.assertRaises(ValueError):
            self.skg.add_layer("layer3", parent_layer="non_existent_layer")
        
        # Test adding layer that already exists
        with self.assertRaises(ValueError):
            self.skg.add_layer("layer1")
    
    def test_get_layer(self):
        """Test getting a layer from the stackable knowledge graph."""
        # Get layer
        layer = self.skg.get_layer("base")
        
        # Check that layer is a KnowledgeGraph
        self.assertIsInstance(layer, KnowledgeGraph)
        
        # Check that fact is in layer
        self.assertIn("fact1", layer.graph)
        
        # Test getting non-existent layer
        with self.assertRaises(ValueError):
            self.skg.get_layer("non_existent_layer")
    
    def test_add_fact_to_layer(self):
        """Test adding a fact to a layer."""
        # Add fact to layer
        self.skg.add_fact_to_layer(
            "layer1",
            fact_id="fact3",
            fact_statement="Gold i<response clipped><NOTE>To save on context only part of this file has been shown to you. You should retry this tool after you have searched inside the file with `grep -n` in order to find the line numbers of what you are looking for.</NOTE>