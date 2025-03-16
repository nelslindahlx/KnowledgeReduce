"""
Unit tests for the query module.
"""

import unittest
import networkx as nx
from knowledgereduce.core.core import KnowledgeGraph, ReliabilityRating
from knowledgereduce.query.query import (
    KnowledgeQuery, find_facts_by_pattern, 
    get_facts_with_relationship, get_related_facts,
    find_facts_by_quality_range, get_fact_relationships,
    find_facts_by_relationship_count
)

class TestQuery(unittest.TestCase):
    """Test cases for the query module."""
    
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
            access_level="restricted",
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
    
    def test_knowledge_query_basic(self):
        """Test basic KnowledgeQuery functionality."""
        # Create query
        query = KnowledgeQuery(self.kg)
        
        # Execute query without filters
        results = query.execute()
        
        # Check that all facts were returned
        self.assertEqual(len(results), 5)
    
    def test_filter_by_category(self):
        """Test filtering by category."""
        # Create query
        query = KnowledgeQuery(self.kg)
        
        # Filter by category
        results = query.filter_by_category("Science").execute()
        
        # Check that only Science facts were returned
        self.assertEqual(len(results), 3)
        for fact_id, _ in results:
            self.assertIn(fact_id, ["fact1", "fact2", "fact5"])
    
    def test_filter_by_categories(self):
        """Test filtering by multiple categories."""
        # Create query
        query = KnowledgeQuery(self.kg)
        
        # Filter by categories
        results = query.filter_by_categories(["Science", "Chemistry"]).execute()
        
        # Check that all facts were returned
        self.assertEqual(len(results), 5)
        
        # Filter by non-existent category
        results = query.filter_by_categories(["Non-existent"]).execute()
        
        # Check that no facts were returned
        self.assertEqual(len(results), 0)
    
    def test_filter_by_tag(self):
        """Test filtering by tag."""
        # Create query
        query = KnowledgeQuery(self.kg)
        
        # Filter by tag
        results = query.filter_by_tag("metal").execute()
        
        # Check that only facts with the metal tag were returned
        self.assertEqual(len(results), 2)
        for fact_id, _ in results:
            self.assertIn(fact_id, ["fact3", "fact4"])
    
    def test_filter_by_tags(self):
        """Test filtering by multiple tags."""
        # Create query
        query = KnowledgeQuery(self.kg)
        
        # Filter by tags (any match)
        results = query.filter_by_tags(["sky", "water"]).execute()
        
        # Check that facts with either tag were returned
        self.assertEqual(len(results), 3)
        for fact_id, _ in results:
            self.assertIn(fact_id, ["fact1", "fact2", "fact5"])
        
        # Filter by tags (all match)
        results = query.filter_by_tags(["metal", "element"], match_all=True).execute()
        
        # Check that only facts with both tags were returned
        self.assertEqual(len(results), 2)
        for fact_id, _ in results:
            self.assertIn(fact_id, ["fact3", "fact4"])
    
    def test_filter_by_reliability(self):
        """Test filtering by reliability rating."""
        # Create query
        query = KnowledgeQuery(self.kg)
        
        # Filter by minimum reliability
        results = query.filter_by_reliability(ReliabilityRating.VERIFIED).execute()
        
        # Check that only VERIFIED facts were returned
        self.assertEqual(len(results), 2)
        for fact_id, _ in results:
            self.assertIn(fact_id, ["fact1", "fact2"])
        
        # Filter by minimum reliability (integer value)
        results = query.filter_by_reliability(3).execute()
        
        # Check that facts with reliability >= 3 were returned
        self.assertEqual(len(results), 4)
        for fact_id, _ in results:
            self.assertIn(fact_id, ["fact1", "fact2", "fact3", "fact4"])
    
    def test_filter_by_quality_score(self):
        """Test filtering by quality score."""
        # Create query
        query = KnowledgeQuery(self.kg)
        
        # Filter by minimum quality score
        results = query.filter_by_quality_score(50).execute()
        
        # Check that facts with quality score >= 50 were returned
        self.assertGreaterEqual(len(results), 1)
    
    def test_filter_by_usage_count(self):
        """Test filtering by usage count."""
        # Create query
        query = KnowledgeQuery(self.kg)
        
        # Filter by minimum usage count
        results = query.filter_by_usage_count(3).execute()
        
        # Check that facts with usage count >= 3 were returned
        self.assertEqual(len(results), 2)
        for fact_id, _ in results:
            self.assertIn(fact_id, ["fact1", "fact2"])
    
    def test_filter_by_source(self):
        """Test filtering by source ID."""
        # Create query
        query = KnowledgeQuery(self.kg)
        
        # Filter by source ID
        results = query.filter_by_source("source2").execute()
        
        # Check that only facts from source2 were returned
        self.assertEqual(len(results), 2)
        for fact_id, _ in results:
            self.assertIn(fact_id, ["fact3", "fact4"])
    
    def test_filter_by_author(self):
        """Test filtering by author/creator."""
        # Create query
        query = KnowledgeQuery(self.kg)
        
        # Filter by author/creator
        results = query.filter_by_author("Another Author").execute()
        
        # Check that only facts by Another Author were returned
        self.assertEqual(len(results), 2)
        for fact_id, _ in results:
            self.assertIn(fact_id, ["fact3", "fact4"])
    
    def test_filter_by_access_level(self):
        """Test filtering by access level."""
        # Create query
        query = KnowledgeQuery(self.kg)
        
        # Filter by access level
        results = query.filter_by_access_level("restricted").execute()
        
        # Check that only restricted facts were returned
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], "fact4")
    
    def test_filter_by_text(self):
        """Test filtering by text content."""
        # Create query
        query = KnowledgeQuery(self.kg)
        
        # Filter by text
        results = query.filter_by_text("precious metal").execute()
        
        # Check that facts containing "precious metal" were returned
        self.assertEqual(len(results), 2)
        for fact_id, _ in results:
            self.assertIn(fact_id, ["fact3", "fact4"])
    
    def test_filter_by_regex(self):
        """Test filtering by regular expression."""
        # Create query
        query = KnowledgeQuery(self.kg)
        
        # Filter by regex
        results = query.filter_by_regex(r"\d+°C").execute()
        
        # Check that facts matching the regex were returned
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], "fact2")
    
    def test_filter_by_related_fact(self):
        """Test filtering by related fact."""
        # Create query
        query = KnowledgeQuery(self.kg)
        
        # Filter by related fact
        results = query.filter_by_related_fact("fact1").execute()
        
        # Check that facts related to fact1 were returned
        self.assertEqual(len(results), 2)
        for fact_id, _ in results:
            self.assertIn(fact_id, ["fact2", "fact5"])
    
    def test_filter_custom(self):
        """Test custom filter."""
        # Create query
        query = KnowledgeQuery(self.kg)
        
        # Custom filter: facts with statement length > 50
        results = query.filter_custom("fact_statement", lambda x: len(x) > 50).execute()
        
        # Check that facts with long statements were returned
        self.assertGreaterEqual(len(results), 1)
    
    def test_sort_by(self):
        """Test sorting results."""
        # Create query
        query = KnowledgeQuery(self.kg)
        
        # Sort by usage count (descending)
        results = query.sort_by("usage_count", reverse=True).execute()
        
        # Check that results are sorted
        self.assertEqual(results[0][0], "fact1")  # usage_count = 5
        self.assertEqual(results[1][0], "fact2")  # usage_count = 3
        
        # Sort by category (ascending)
        results = query.sort_by("category").execute()
        
        # Check that results are sorted
        self.assertIn(results[0][0], ["fact3", "fact4"])  # category = Chemistry
    
    def test_limit(self):
        """Test limiting results."""
        # Create query
        query = KnowledgeQuery(self.kg)
        
        # Limit results
        results = query.limit(2).execute()
        
        # Check that only 2 results were returned
        self.assertEqual(len(results), 2)
    
    def test_chained_filters(self):
        """Test chaining multiple filters."""
        # Create query
        query = KnowledgeQuery(self.kg)
        
        # Chain filters
        results = query.filter_by_category("Science") \
                      .filter_by_tag("physics") \
                      .filter_by_reliability(ReliabilityRating.VERIFIED) \
                      .execute()
        
        # Check that only facts matching all filters were returned
        self.assertEqual(len(results), 2)
        for fact_id, _ in results:
            self.assertIn(fact_id, ["fact1", "fact2"])
    
    def test_find_facts_by_pattern(self):
        """Test finding facts by pattern."""
        # Find facts matching pattern
        results = find_facts_by_pattern(self.kg, r"atomic number \d+")
        
        # Check that facts matching the pattern were found
        self.assertEqual(len(results), 2)
        self.assertIn("fact3", results)
        self.assertIn("fact4", results)
    
    def test_get_facts_with_relationship(self):
        """Test getting facts with a specific relationship type."""
        # Get facts with relationship
        results = get_facts_with_relationship(self.kg, "related_to")
        
        # Check that facts with the relationship were found
        self.assertEqual(len(results["sources"]), 2)
        self.assertIn("fact1", results["sources"])
        self.assertIn("fact2", results["sources"])
        
        self.assertEqual(len(results["targets"]), 2)
        self.assertIn("fact2", results["targets"])
        self.assertIn("fact3", results["targets"])
        
        # Get only source facts
        results = get_facts_with_relationship(self.kg, "related_to", as_target=False)
        
        # Check that only source facts were found
        self.assertEqual(len(results["sources"]), 2)
        self.assertEqual(len(results["targets"]), 0)
    
    def test_get_related_facts(self):
        """Test getting facts related to a given fact."""
        # Get related facts
        results = get_related_facts(self.kg, "fact2")
        
        # Check that related facts were found
        self.assertEqual(len(results), 2)
        self.assertIn("fact1", results)
        self.assertIn("fact3", results)
        
        # Get related facts with specific relationship type
        results = get_related_facts(self.kg, "fact1", relationship_types=["contradicts"])
        
        # Check that only facts with the specified relationship were found
        self.assertEqual(len(results), 1)
        self.assertIn("fact5", results)
        
        # Get related facts with max depth
        results = get_related_facts(self.kg, "fact1", max_depth=2)
        
        # Check that facts up to 2 steps away were found
        self.assertEqual(len(results), 3)
        <response clipped><NOTE>To save on context only part of this file has been shown to you. You should retry this tool after you have searched inside the file with `grep -n` in order to find the line numbers of what you are looking for.</NOTE>