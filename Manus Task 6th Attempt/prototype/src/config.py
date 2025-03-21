"""
Configuration settings for the KnowledgeReduce prototype.
"""

# Neo4j connection settings
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"

# Data paths
ENTITIES_FILE = "data/entities.csv"
RELATIONSHIPS_FILE = "data/relationships.csv"

# Entity resolution settings
SIMILARITY_THRESHOLD = 0.8  # Threshold for fuzzy matching
MAX_EDIT_DISTANCE = 3  # Maximum edit distance for name matching

# Knowledge mapping settings
DEFAULT_ENTITY_TYPES = ["Person", "Organization", "Location", "Concept"]
DEFAULT_RELATIONSHIP_TYPES = ["WORKS_FOR", "LOCATED_IN", "RELATED_TO", "KNOWS"]

# Knowledge stacking settings
KNOWLEDGE_LAYERS = ["Raw", "Processed", "Abstract"]
