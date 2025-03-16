"""
Unit tests for the analysis module.
"""

import unittest
import networkx as nx
from knowledgereduce.core.core import KnowledgeGraph, ReliabilityRating
from knowledgereduce.analysis.analysis import (
    identify_central_facts, identify_fact_clusters, 
    calculate_fact_similarity, find_similar_facts, 
    analyze_fact_categories, find_path_between_facts,
    extract_keywords_from_fact, analyze_fact_reliability,
    identify_conflicting_facts, analyze_fact_usage
)

class TestAnalysis(unittest.TestCase):
    """Test cases for the analysis module."""
    
    def setUp(self):
        """Set up a test knowledge graph."""
        self.kg = KnowledgeGraph()
        
        # Add some test facts
        self.kg.add_fact(
            fact_id="fact1",
            fact_statement="The sky is blue due to Rayleigh scattering of sunlight",
            category="Science",
            tags=["sky", "color", "physics"],
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
            fact_statement="Water boils at 100°C at standard atmospheric pressure",
            category="Science",
            tags=["water", "temperature", "physics"],
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
            fact_statement="Gold is a precious metal with atomic number 79",
            category="Chemistry",
            tags=["gold", "metal", "element"],
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
        
        self.kg.add_fact(
            fact_id="fact4",
            fact_statement="Silver is a precious metal with atomic number 47",
            category="Chemistry",
            tags=["silver", "metal", "element"],
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
            usage_count=1,
            source_quality=6
        )
        
        self.kg.add_fact(
            fact_id="fact5",
            fact_statement="The sky appears blue because of how air scatters sunlight",
            category="Science",
            tags=["sky", "color", "light"],
            date_recorded="2023-01-01",
            last_updated="2023-01-01",
            reliability_rating=ReliabilityRating.POSSIBLY_TRUE,
            source_id="source3",
            source_title="Less Reliable Source",
            author_creator="Less Reliable Author",
            publication_date="2023-01-01",
            url_reference="http://example.com/less_reliable",
            related_facts=[],
            contextual_notes="Less reliable notes",
            access_level="public",
            usage_count=1,
            source_quality=4
        )
        
        # Add relationships
        self.kg.add_relationship("fact1", "fact2", "related_to", weight=0.5)
        self.kg.add_relationship("fact2", "fact3", "related_to", weight=0.3)
        self.kg.add_relationship("fact3", "fact4", "similar_to", weight=0.8)
        self.kg.add_relationship("fact1", "fact5", "contradicts", weight=0.2)
    
    def test_identify_central_facts(self):
        """Test identifying central facts."""
        # Identify central facts using degree centrality
        central_facts = identify_central_facts(self.kg, top_n=2, method='degree')
        
        # Check that central facts were identified
        self.assertEqual(len(central_facts), 2)
        self.assertIsInstance(central_facts[0], tuple)
        self.assertEqual(len(central_facts[0]), 2)
        
        # Identify central facts using betweenness centrality
        central_facts = identify_central_facts(self.kg, top_n=2, method='betweenness')
        
        # Check that central facts were identified
        self.assertEqual(len(central_facts), 2)
        
        # Identify central facts using eigenvector centrality
        central_facts = identify_central_facts(self.kg, top_n=2, method='eigenvector')
        
        # Check that central facts were identified
        self.assertEqual(len(central_facts), 2)
        
        # Identify central facts using pagerank
        central_facts = identify_central_facts(self.kg, top_n=2, method='pagerank')
        
        # Check that central facts were identified
        self.assertEqual(len(central_facts), 2)
        
        # Test with invalid method
        with self.assertRaises(ValueError):
            identify_central_facts(self.kg, top_n=2, method='invalid_method')
    
    def test_identify_fact_clusters(self):
        """Test identifying fact clusters."""
        # Identify fact clusters
        clusters = identify_fact_clusters(self.kg, min_cluster_size=2)
        
        # Check that clusters were identified
        self.assertIsInstance(clusters, list)
        
        # There should be at least one cluster with at least 2 facts
        if clusters:
            self.assertGreaterEqual(len(clusters[0]), 2)
    
    def test_calculate_fact_similarity(self):
        """Test calculating fact similarity."""
        # Calculate content similarity
        similarity = calculate_fact_similarity(self.kg, "fact1", "fact5", method='content')
        
        # Check that similarity was calculated
        self.assertIsInstance(similarity, float)
        self.assertGreaterEqual(similarity, 0.0)
        self.assertLessEqual(similarity, 1.0)
        
        # These facts should have high content similarity
        self.assertGreater(similarity, 0.5)
        
        # Calculate structural similarity
        similarity = calculate_fact_similarity(self.kg, "fact3", "fact4", method='structural')
        
        # Check that similarity was calculated
        self.assertIsInstance(similarity, float)
        self.assertGreaterEqual(similarity, 0.0)
        self.assertLessEqual(similarity, 1.0)
        
        # Calculate combined similarity
        similarity = calculate_fact_similarity(self.kg, "fact1", "fact5", method='combined')
        
        # Check that similarity was calculated
        self.assertIsInstance(similarity, float)
        self.assertGreaterEqual(similarity, 0.0)
        self.assertLessEqual(similarity, 1.0)
        
        # Test with invalid method
        with self.assertRaises(ValueError):
            calculate_fact_similarity(self.kg, "fact1", "fact5", method='invalid_method')
        
        # Test with non-existent fact
        with self.assertRaises(ValueError):
            calculate_fact_similarity(self.kg, "fact1", "non_existent_fact")
    
    def test_find_similar_facts(self):
        """Test finding similar facts."""
        # Find similar facts
        similar_facts = find_similar_facts(self.kg, "fact1", threshold=0.1, max_results=3, method='content')
        
        # Check that similar facts were found
        self.assertIsInstance(similar_facts, list)
        
        # fact5 should be similar to fact1
        similar_fact_ids = [fact_id for fact_id, _ in similar_facts]
        self.assertIn("fact5", similar_fact_ids)
        
        # Find similar facts with structural method
        similar_facts = find_similar_facts(self.kg, "fact3", threshold=0.1, max_results=3, method='structural')
        
        # Check that similar facts were found
        self.assertIsInstance(similar_facts, list)
        
        # Find similar facts with combined method
        similar_facts = find_similar_facts(self.kg, "fact1", threshold=0.1, max_results=3, method='combined')
        
        # Check that similar facts were found
        self.assertIsInstance(similar_facts, list)
        
        # Test with non-existent fact
        with self.assertRaises(ValueError):
            find_similar_facts(self.kg, "non_existent_fact")
    
    def test_analyze_fact_categories(self):
        """Test analyzing fact categories."""
        # Analyze fact categories
        category_stats = analyze_fact_categories(self.kg)
        
        # Check that category statistics were created
        self.assertIsInstance(category_stats, dict)
        self.assertEqual(category_stats["total_facts"], 5)
        self.assertEqual(category_stats["num_categories"], 2)
        self.assertEqual(category_stats["category_counts"]["Science"], 3)
        self.assertEqual(category_stats["category_counts"]["Chemistry"], 2)
        
        # Check category percentages
        self.assertIn("category_percentages", category_stats)
        self.assertAlmostEqual(category_stats["category_percentages"]["Science"], 60.0)
        self.assertAlmostEqual(category_stats["category_percentages"]["Chemistry"], 40.0)
        
        # Check most common categories
        self.assertIn("most_common_categories", category_stats)
        self.assertEqual(category_stats["most_common_categories"][0][0], "Science")
        self.assertEqual(category_stats["most_common_categories"][0][1], 3)
        
        # Check average quality score per category
        self.assertIn("category_avg_quality", category_stats)
        self.assertIn("Science", category_stats["category_avg_quality"])
        self.assertIn("Chemistry", category_stats["category_avg_quality"])
    
    def test_find_path_between_facts(self):
        """Test finding path between facts."""
        # Find path between facts
        path = find_path_between_facts(self.kg, "fact1", "fact3")
        
        # Check that path was found
        self.assertIsInstance(path, list)
        self.assertEqual(len(path), 3)
        self.assertEqual(path[0], "fact1")
        self.assertEqual(path[1], "fact2")
        self.assertEqual(path[2], "fact3")
        
        # Find path with max length
        path = find_path_between_facts(self.kg, "fact1", "fact3", max_length=2)
        
        # Check that path was found
        self.assertIsInstance(path, list)
        self.assertEqual(len(path), 3)
        
        # Find path with max length too short
        with self.assertRaises(ValueError):
            find_path_between_facts(self.kg, "fact1", "fact4", max_length=1)
        
        # Test with non-existent fact
        with self.assertRaises(ValueError):
            find_path_between_facts(self.kg, "fact1", "non_existent_fact")
    
    def test_extract_keywords_from_fact(self):
        """Test extracting keywords from a fact."""
        # Extract keywords
        keywords = extract_keywords_from_fact(self.kg, "fact1", num_keywords=3)
        
        # Check that keywords were extracted
        self.assertIsInstance(keywords, list)
        self.assertLessEqual(len(keywords), 3)
        
        # Keywords should include important terms from the fact statement
        for keyword in keywords:
            self.assertIn(keyword.lower(), self.kg.graph.nodes["fact1"]["fact_statement"].lower())
        
        # Test with non-existent fact
        with self.assertRaises(ValueError):
            extract_keywords_from_fact(self.kg, "non_existent_fact")
    
    def test_analyze_fact_reliability(self):
        """Test analyzing fact reliability."""
        # Analyze fact reliability
        reliability_stats = analyze_fact_reliability(self.kg)
        
        # Check that reliability statistics were created
        self.assertIsInstance(reliability_stats, dict)
        self.assertEqual(reliability_stats["total_facts"], 5)
        
        # Check reliability counts
        self.assertIn("reliability_counts", reliability_stats)
        self.assertEqual(reliability_stats["reliability_counts"][ReliabilityRating.VERIFIED.value], 2)
        self.assertEqual(reliability_stats["reliability_counts"][ReliabilityRating.LIKELY_TRUE.value], 2)
        self.assertEqual(reliability_stats["reliability_counts"][ReliabilityRating.POSSIBLY_TRUE.value], 1)
        
        # Check reliability percentages
        self.assertIn("reliability_percentages", reliability_stats)
        self.assertAlmostEqual(reliability_stats["reliability_percentages"][ReliabilityRating.VERIFIED.value], 40.0)
        self.assertAlmostEqual(reliability_stats["reliability_percentages"][ReliabilityRating.LIKELY_TRUE.value], 40.0)
        self.assertAlmostEqual(reliability_stats["reliability_percentages"][ReliabilityRating.POSSIBLY_TRUE.value], 20.0)
        
        # Check average reliability
        self.assertIn("avg_reliability", reliability_stats)
        # (2*4 + 2*3 + 1*2) / 5 = 3.2
        self.assertAlmostEqual(reliability_stats["avg_reliability"], 3.2)
    
    def test_identify_conflicting_facts(self):
        """Test identifying conflicting facts."""
        # Identify conflicting facts
        conflicts = identify_conflicting_facts(self.kg, threshold=0.5)
        
        # Check that conflicts were identified
        self.assertIsInstance(conflicts, list)
        
        # fact1 and fact5 should be identified as conflicting
        # (they have similar content but different reliability ratings)
        conflict_pairs = [(a, b) for a, b, _ in conflicts]
        self.assertTrue(("fact1", "fact5") in conflict_pairs or ("fact5", "fact1") in conflict_pairs)
    
    def test_analyze_fact_usage(self):
        """Test analyzing fact usage."""
        # Analyze fact usage
        usage_stats = analyze_fact_usage(self.kg)
        
        # Check that usage statistics were created
        self.assertIsInstance(usage_stats, dict)
        self.assertEqual(usage_stats["total_facts"], 5)
        self.assertEqual(usage_stats["total_usage"], 12)  # 5 + 3 + 2 + 1 + 1 = 12
        self.assertAlmostEqual(usage_stats["avg_usage"], 2.4)  # 12 / 5 = 2.4
        self.assertEqual(usage_stats["max_usage"], 5)
        self.assertEqual(usage_stats["min_usage"], 1)
        
        # Check most used facts
        self.assertIn("most_used_facts", usage_stats)
        self.assertEqual(usage_stats["most_used_facts"][0][0], "fact1")
        self.assertEqual(usage_stats["most_used_facts"][0][1], 5)
        
        # Check usage ranges
        self.assertIn("usage_ranges", usage_stats)
        self.assertEqual(usage_stats["usage_ranges"]["0-1"], 2)  # fact4, fact5
        self.assertEqual(usage_stats["usage_ranges"]["2-5"], 3)  # fact1, fact2, fact3
        
        # Check usage percentages
        self.assertIn("usage_percentages", usage_stats)
        self.assertAlmostEqual(usage_stat<response clipped><NOTE>To save on context only part of this file has been shown to you. You should retry this tool after you have searched inside the file with `grep -n` in order to find the line numbers of what you are looking for.</NOTE>