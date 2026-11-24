"""
Unit tests for the serialization module.
"""

import unittest
import os
import tempfile
import networkx as nx
from knowledgereduce.core.core import KnowledgeGraph, StackableKnowledgeGraph, ReliabilityRating
from knowledgereduce.serialization.serialization import KnowledgeGraphSerializer, StackableKnowledgeGraphSerializer

class TestKnowledgeGraphSerializer(unittest.TestCase):
    """Test cases for the KnowledgeGraphSerializer class."""
    
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
        
        # Add a relationship
        self.kg.add_relationship("fact1", "fact2", "related_to", weight=0.8)
    
    def test_to_json(self):
        """Test serializing a knowledge graph to JSON."""
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Serialize to JSON
            json_path = os.path.join(temp_dir, "test_graph.json")
            file_paths = KnowledgeGraphSerializer.to_json(self.kg, json_path)
            
            # Check that file was created
            self.assertTrue(os.path.exists(json_path))
            self.assertEqual(len(file_paths), 1)
            self.assertEqual(file_paths[0], json_path)
    
    def test_from_json(self):
        """Test deserializing a knowledge graph from JSON."""
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Serialize to JSON
            json_path = os.path.join(temp_dir, "test_graph.json")
            KnowledgeGraphSerializer.to_json(self.kg, json_path)
            
            # Deserialize from JSON
            new_kg = KnowledgeGraphSerializer.from_json(json_path)
            
            # Check that facts were deserialized correctly
            self.assertIn("fact1", new_kg.graph)
            self.assertIn("fact2", new_kg.graph)
            self.assertEqual(new_kg.graph.nodes["fact1"]["fact_statement"], "The sky is blue")
            self.assertEqual(new_kg.graph.nodes["fact2"]["fact_statement"], "Water boils at 100°C")
            
            # Check that relationship was deserialized correctly
            self.assertTrue(new_kg.graph.has_edge("fact1", "fact2"))
            edge_data = new_kg.graph.get_edge_data("fact1", "fact2")
            self.assertEqual(edge_data["relationship_type"], "related_to")
            self.assertEqual(edge_data["weight"], 0.8)
    
    def test_to_json_sharded(self):
        """Test serializing a knowledge graph to sharded JSON."""
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
            # Serialize to JSON with sharding (5 nodes per shard)
            json_path = os.path.join(temp_dir, "test_graph_sharded.json")
            file_paths = KnowledgeGraphSerializer.to_json(self.kg, json_path, shard_size=5)
            
            # Check that metadata file was created
            metadata_path = os.path.join(temp_dir, "test_graph_sharded_metadata.json")
            self.assertTrue(os.path.exists(metadata_path))
            
            # Check that shard files were created
            self.assertTrue(len(file_paths) > 1)
            for path in file_paths:
                self.assertTrue(os.path.exists(path))
    
    def test_from_json_sharded(self):
        """Test deserializing a knowledge graph from sharded JSON."""
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
            # Serialize to JSON with sharding (5 nodes per shard)
            json_path = os.path.join(temp_dir, "test_graph_sharded.json")
            file_paths = KnowledgeGraphSerializer.to_json(self.kg, json_path, shard_size=5)
            
            # Get metadata path
            metadata_path = os.path.join(temp_dir, "test_graph_sharded_metadata.json")
            
            # Deserialize from JSON
            new_kg = KnowledgeGraphSerializer.from_json(metadata_path)
            
            # Check that facts were deserialized correctly
            for i in range(1, 11):
                self.assertIn(f"fact{i}", new_kg.graph)
            
            # Check that relationship was deserialized correctly
            self.assertTrue(new_kg.graph.has_edge("fact1", "fact2"))
    
    def test_to_gexf(self):
        """Test serializing a knowledge graph to GEXF."""
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Serialize to GEXF
            gexf_path = os.path.join(temp_dir, "test_graph.gexf")
            result = KnowledgeGraphSerializer.to_gexf(self.kg, gexf_path)
            
            # Check that file was created
            self.assertTrue(os.path.exists(gexf_path))
            self.assertTrue(result)
    
    def test_from_gexf(self):
        """Test deserializing a knowledge graph from GEXF."""
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Serialize to GEXF
            gexf_path = os.path.join(temp_dir, "test_graph.gexf")
            KnowledgeGraphSerializer.to_gexf(self.kg, gexf_path)
            
            # Deserialize from GEXF
            new_kg = KnowledgeGraphSerializer.from_gexf(gexf_path)
            
            # Check that facts were deserialized correctly
            self.assertIn("fact1", new_kg.graph)
            self.assertIn("fact2", new_kg.graph)
    
    def test_to_graphml(self):
        """Test serializing a knowledge graph to GraphML."""
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Serialize to GraphML
            graphml_path = os.path.join(temp_dir, "test_graph.graphml")
            result = KnowledgeGraphSerializer.to_graphml(self.kg, graphml_path)
            
            # Check that file was created
            self.assertTrue(os.path.exists(graphml_path))
            self.assertTrue(result)
    
    def test_from_graphml(self):
        """Test deserializing a knowledge graph from GraphML."""
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Serialize to GraphML
            graphml_path = os.path.join(temp_dir, "test_graph.graphml")
            KnowledgeGraphSerializer.to_graphml(self.kg, graphml_path)
            
            # Deserialize from GraphML
            new_kg = KnowledgeGraphSerializer.from_graphml(graphml_path)
            
            # Check that facts were deserialized correctly
            self.assertIn("fact1", new_kg.graph)
            self.assertIn("fact2", new_kg.graph)

class TestStackableKnowledgeGraphSerializer(unittest.TestCase):
    """Test cases for the StackableKnowledgeGraphSerializer class."""
    
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
        
        # Add a relationship
        self.skg.add_relationship_to_layer("layer1", "fact1", "fact2", "related_to", weight=0.8)
    
    def test_to_json(self):
        """Test serializing a stackable knowledge graph to JSON."""
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Serialize to JSON
            json_dir = os.path.join(temp_dir, "test_stackable_graph")
            layer_files = StackableKnowledgeGraphSerializer.to_json(self.skg, json_dir)
            
            # Check that metadata file was created
            metadata_path = os.path.join(json_dir, "metadata.json")
            self.assertTrue(os.path.exists(metadata_path))
            
            # Check that layer files were created
            self.assertIn("base", layer_files)
            self.assertIn("layer1", layer_files)
            
            # Check that layer directories were created
            base_dir = os.path.join(json_dir, "base")
            layer1_dir = os.path.join(json_dir, "layer1")
            self.assertTrue(os.path.exists(base_dir))
            self.assertTrue(os.path.exists(layer1_dir))
            
            # Check that layer files exist
            base_file = os.path.join(base_dir, "base.json")
            layer1_file = os.path.join(layer1_dir, "layer1.json")
            self.assertTrue(os.path.exists(base_file))
            self.assertTrue(os.path.exists(layer1_file))
    
    def test_from_json(self):
        """Test deserializing a stackable knowledge graph from JSON."""
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Serialize to JSON
            json_dir = os.path.join(temp_dir, "test_stackable_graph")
            StackableKnowledgeGraphSerializer.to_json(self.skg, json_dir)
            
            # Deserialize from JSON
            new_skg = StackableKnowledgeGraphSerializer.from_json(json_dir)
            
            # Check that layers were deserialized correctly
            self.assertIn("base", new_skg.layers)
            self.assertIn("layer1", new_skg.layers)
            
            # Check that facts were deserialized correctly
            self.assertIn("fact1", new_skg.layers["base"].graph)
            self.assertIn("fact2", new_skg.layers["layer1"].graph)
            
            # Check that relationship was deserialized correctly
            self.assertTrue(new_skg.layers["layer1"].graph.has_edge("fact1", "fact2"))
            
            # Check that layer order was preserved
            self.assertEqual(new_skg.layer_order, self.skg.layer_order)
            
            # Check that inheritance rules were preserved
            self.assertEqual(new_skg.inheritance_rules, self.skg.inheritance_rules)
    
    def test_to_json_sharded(self):
        """Test serializing a stackable knowledge graph to sharded JSON."""
        # Add more facts to make sharding meaningful
        for i in range(3, 11):
            self.skg.add_fact_to_layer(
                "base" if i % 2 == 0 else "layer1",
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
            # Serialize to JSON with sharding (3 nodes per shard)
            json_dir = os.path.join(temp_dir, "test_stackable_graph_sharded")
            layer_files = StackableKnowledgeGraphSerializer.to_json(self.skg, json_dir, shard_size=3)
            
            # Check that metadata file was created
            metadata_path = os.path.join(json_dir, "metadata.json")
            self.assertTrue(os.path.exists(metadata_path))
            
            # Ch<response clipped><NOTE>To save on context only part of this file has been shown to you. You should retry this tool after you have searched inside the file with `grep -n` in order to find the line numbers of what you are looking for.</NOTE>