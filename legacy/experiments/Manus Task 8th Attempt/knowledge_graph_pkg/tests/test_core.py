"""
Unit tests for the knowledge graph core functionality.

This module contains pytest-based tests for the KnowledgeGraph class and ReliabilityRating enum.
"""

import pytest
from datetime import datetime
from knowledge_graph_pkg.core import KnowledgeGraph, ReliabilityRating


@pytest.fixture
def empty_kg():
    """Fixture providing an empty KnowledgeGraph instance."""
    return KnowledgeGraph()


@pytest.fixture
def populated_kg():
    """Fixture providing a KnowledgeGraph instance with sample facts."""
    kg = KnowledgeGraph()
    
    # Add a sample fact
    kg.add_fact(
        fact_id="test_fact_1",
        fact_statement="The Earth is round",
        category="Science",
        tags=["Earth", "astronomy", "shape"],
        date_recorded=datetime.now(),
        last_updated=datetime.now(),
        reliability_rating=ReliabilityRating.VERIFIED,
        source_id="source_1",
        source_title="Science Journal",
        author_creator="Dr. Scientist",
        publication_date=datetime.now(),
        url_reference="https://example.com/earth",
        related_facts=[],
        contextual_notes="Basic scientific fact",
        access_level="public",
        usage_count=10
    )
    
    # Add another sample fact
    kg.add_fact(
        fact_id="test_fact_2",
        fact_statement="Water is composed of hydrogen and oxygen",
        category="Chemistry",
        tags=["water", "chemistry", "composition"],
        date_recorded=datetime.now(),
        last_updated=datetime.now(),
        reliability_rating=ReliabilityRating.VERIFIED,
        source_id="source_2",
        source_title="Chemistry Textbook",
        author_creator="Dr. Chemist",
        publication_date=datetime.now(),
        url_reference="https://example.com/water",
        related_facts=["test_fact_1"],
        contextual_notes="Basic chemistry fact",
        access_level="public",
        usage_count=8
    )
    
    return kg


class TestKnowledgeGraphInitialization:
    """Tests for KnowledgeGraph initialization."""
    
    def test_initialization(self, empty_kg):
        """Test that a new KnowledgeGraph is initialized correctly."""
        assert empty_kg is not None
        assert empty_kg.graph is not None
        assert len(empty_kg.graph.nodes) == 0
        assert len(empty_kg.graph.edges) == 0


class TestReliabilityRating:
    """Tests for ReliabilityRating enum."""
    
    def test_enum_values(self):
        """Test that ReliabilityRating enum has the expected values."""
        assert ReliabilityRating.UNVERIFIED.value == 1
        assert ReliabilityRating.POSSIBLY_TRUE.value == 2
        assert ReliabilityRating.LIKELY_TRUE.value == 3
        assert ReliabilityRating.VERIFIED.value == 4
    
    def test_enum_comparison(self):
        """Test that ReliabilityRating enum values can be compared."""
        assert int(ReliabilityRating.UNVERIFIED) < int(ReliabilityRating.POSSIBLY_TRUE)
        assert int(ReliabilityRating.POSSIBLY_TRUE) < int(ReliabilityRating.LIKELY_TRUE)
        assert int(ReliabilityRating.LIKELY_TRUE) < int(ReliabilityRating.VERIFIED)


class TestFactValidation:
    """Tests for fact validation methods."""
    
    def test_validate_fact_id_valid(self, empty_kg):
        """Test that valid fact IDs pass validation."""
        # These should not raise exceptions
        empty_kg.validate_fact_id("fact1")
        empty_kg.validate_fact_id("a_valid_id_123")
        empty_kg.validate_fact_id("UPPERCASE_ID")
    
    def test_validate_fact_id_invalid(self, empty_kg):
        """Test that invalid fact IDs fail validation."""
        with pytest.raises(ValueError):
            empty_kg.validate_fact_id("")
        
        with pytest.raises(ValueError):
            empty_kg.validate_fact_id(None)
        
        with pytest.raises(ValueError):
            empty_kg.validate_fact_id(123)  # Not a string
    
    def test_validate_reliability_rating_valid(self, empty_kg):
        """Test that valid reliability ratings pass validation."""
        # These should not raise exceptions
        empty_kg.validate_reliability_rating(ReliabilityRating.UNVERIFIED)
        empty_kg.validate_reliability_rating(ReliabilityRating.POSSIBLY_TRUE)
        empty_kg.validate_reliability_rating(ReliabilityRating.LIKELY_TRUE)
        empty_kg.validate_reliability_rating(ReliabilityRating.VERIFIED)
    
    def test_validate_reliability_rating_invalid(self, empty_kg):
        """Test that invalid reliability ratings fail validation."""
        with pytest.raises(ValueError):
            empty_kg.validate_reliability_rating("VERIFIED")  # String instead of enum
        
        with pytest.raises(ValueError):
            empty_kg.validate_reliability_rating(4)  # Integer instead of enum
        
        with pytest.raises(ValueError):
            empty_kg.validate_reliability_rating(None)


class TestFactOperations:
    """Tests for fact operations (add, get, update)."""
    
    def test_add_fact(self, empty_kg):
        """Test adding a fact to the knowledge graph."""
        fact_id = "new_fact"
        empty_kg.add_fact(
            fact_id=fact_id,
            fact_statement="Test statement",
            category="Test",
            tags=["test", "example"],
            date_recorded=datetime.now(),
            last_updated=datetime.now(),
            reliability_rating=ReliabilityRating.VERIFIED,
            source_id="source_test",
            source_title="Test Source",
            author_creator="Test Author",
            publication_date=datetime.now(),
            url_reference="https://example.com/test",
            related_facts=[],
            contextual_notes="Test notes",
            access_level="public",
            usage_count=5
        )
        
        # Verify the fact was added
        assert fact_id in empty_kg.graph.nodes
        assert len(empty_kg.graph.nodes) == 1
    
    def test_get_fact_existing(self, populated_kg):
        """Test retrieving an existing fact from the knowledge graph."""
        fact = populated_kg.get_fact("test_fact_1")
        assert fact is not None
        assert fact["fact_statement"] == "The Earth is round"
        assert fact["category"] == "Science"
        assert "Earth" in fact["tags"]
    
    def test_get_fact_nonexistent(self, populated_kg):
        """Test that retrieving a nonexistent fact raises an error."""
        with pytest.raises(ValueError):
            populated_kg.get_fact("nonexistent_fact")
    
    def test_update_fact(self, populated_kg):
        """Test updating a fact in the knowledge graph."""
        # Update the usage count
        populated_kg.update_fact("test_fact_1", usage_count=15)
        
        # Verify the update
        fact = populated_kg.get_fact("test_fact_1")
        assert fact["usage_count"] == 15
        
        # Update multiple attributes
        populated_kg.update_fact(
            "test_fact_1",
            fact_statement="The Earth is approximately spherical",
            reliability_rating=ReliabilityRating.LIKELY_TRUE
        )
        
        # Verify the updates
        fact = populated_kg.get_fact("test_fact_1")
        assert fact["fact_statement"] == "The Earth is approximately spherical"
        assert fact["reliability_rating"] == ReliabilityRating.LIKELY_TRUE
    
    def test_update_nonexistent_fact(self, populated_kg):
        """Test that updating a nonexistent fact raises an error."""
        with pytest.raises(ValueError):
            populated_kg.update_fact("nonexistent_fact", usage_count=10)
    
    def test_update_invalid_attribute(self, populated_kg):
        """Test that updating with an invalid attribute raises an error."""
        with pytest.raises(ValueError):
            populated_kg.update_fact("test_fact_1", nonexistent_attribute="value")


class TestQualityScore:
    """Tests for quality score calculation."""
    
    def test_quality_score_calculation(self, empty_kg):
        """Test that quality score is calculated correctly when adding a fact."""
        fact_id = "quality_test"
        reliability_rating = ReliabilityRating.VERIFIED
        usage_count = 10
        
        empty_kg.add_fact(
            fact_id=fact_id,
            fact_statement="Test statement",
            category="Test",
            tags=["test"],
            date_recorded=datetime.now(),
            last_updated=datetime.now(),
            reliability_rating=reliability_rating,
            source_id="source_test",
            source_title="Test Source",
            author_creator="Test Author",
            publication_date=datetime.now(),
            url_reference="https://example.com/test",
            related_facts=[],
            contextual_notes="Test notes",
            access_level="public",
            usage_count=usage_count
        )
        
        fact = empty_kg.get_fact(fact_id)
        expected_score = usage_count * reliability_rating.value + 2 * usage_count
        assert fact["quality_score"] == expected_score
    
    def test_quality_score_update(self, populated_kg):
        """Test that quality score is updated when reliability rating or usage count changes."""
        # Get the initial quality score
        fact = populated_kg.get_fact("test_fact_1")
        initial_score = fact["quality_score"]
        
        # Update the usage count
        populated_kg.update_fact("test_fact_1", usage_count=20)
        
        # Verify the quality score was updated
        fact = populated_kg.get_fact("test_fact_1")
        assert fact["quality_score"] != initial_score
        assert fact["quality_score"] == 20 * ReliabilityRating.VERIFIED.value + 2 * 20
        
        # Update the reliability rating
        populated_kg.update_fact("test_fact_1", reliability_rating=ReliabilityRating.LIKELY_TRUE)
        
        # Verify the quality score was updated again
        fact = populated_kg.get_fact("test_fact_1")
        assert fact["quality_score"] == 20 * ReliabilityRating.LIKELY_TRUE.value + 2 * 20


class TestPropertyBasedTests:
    """Property-based tests for the knowledge graph."""
    
    @pytest.mark.parametrize("reliability_rating", [
        ReliabilityRating.UNVERIFIED,
        ReliabilityRating.POSSIBLY_TRUE,
        ReliabilityRating.LIKELY_TRUE,
        ReliabilityRating.VERIFIED
    ])
    def test_quality_score_increases_with_reliability(self, empty_kg, reliability_rating):
        """Test that quality score increases with higher reliability ratings."""
        fact_id = f"reliability_test_{reliability_rating.name}"
        usage_count = 10
        
        empty_kg.add_fact(
            fact_id=fact_id,
            fact_statement="Test statement",
            category="Test",
            tags=["test"],
            date_recorded=datetime.now(),
            last_updated=datetime.now(),
            reliability_rating=reliability_rating,
            source_id="source_test",
            source_title="Test Source",
            author_creator="Test Author",
            publication_date=datetime.now(),
            url_reference="https://example.com/test",
            related_facts=[],
            contextual_notes="Test notes",
            access_level="public",
            usage_count=usage_count
        )
        
        fact = empty_kg.get_fact(fact_id)
        assert fact["quality_score"] == usage_count * reliability_rating.value + 2 * usage_count
    
    @pytest.mark.parametrize("usage_count", [1, 5, 10, 20])
    def test_quality_score_increases_with_usage(self, empty_kg, usage_count):
        """Test that quality score increases with higher usage counts."""
        fact_id = f"usage_test_{usage_count}"
        reliability_rating = ReliabilityRating.VERIFIED
        
        empty_kg.add_fact(
            fact_id=fact_id,
            fact_statement="Test statement",
            category="Test",
            tags=["test"],
            date_recorded=datetime.now(),
            last_updated=datetime.now(),
            reliability_rating=reliability_rating,
            source_id="source_test",
            source_title="Test Source",
            author_creator="Test Author",
            publication_date=datetime.now(),
            url_reference="https://example.com/test",
            related_facts=[],
            contextual_notes="Test notes",
            access_level="public",
            usage_count=usage_count
        )
        
        fact = empty_kg.get_fact(fact_id)
        assert fact["quality_score"] == usage_count * reliability_rating.value + 2 * usage_count
