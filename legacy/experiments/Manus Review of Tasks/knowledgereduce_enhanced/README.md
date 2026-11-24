# KnowledgeReduce Enhanced

A powerful Python package for creating and managing portable knowledge graphs with advanced features.

## Features

### Core Functionality
- Create and manage knowledge graphs with reliability ratings
- Add, update, and query facts with rich metadata
- Visualize knowledge graphs with customizable layouts
- Import and export knowledge graphs in various formats

### Enhanced Performance
- LRU caching for improved query performance
- Batch operations for efficient data manipulation
- Change tracking and auto-saving capabilities
- Optimized data structures for large knowledge graphs

### Semantic Capabilities
- Entity extraction from unstructured text
- Relationship identification between entities
- Automatic fact creation from text
- Semantic similarity calculation between facts

### Scalability
- Sharding for distributed knowledge graphs
- Efficient handling of very large datasets
- Optimized shard management and balancing
- Cross-shard search and query capabilities

## Installation

```bash
pip install knowledge-graph-pkg
```

## Quick Start

```python
from knowledge_graph_pkg import KnowledgeGraph, ReliabilityRating
from knowledge_graph_pkg.enhanced import EnhancedKnowledgeGraph
from knowledge_graph_pkg.semantic import SemanticKnowledgeGraph
from knowledge_graph_pkg.sharding import ShardedKnowledgeGraph

# Create an enhanced knowledge graph with caching
kg = EnhancedKnowledgeGraph(cache_enabled=True)

# Add facts with reliability ratings
kg.add_fact(
    fact_id="earth_sun",
    fact_statement="The Earth orbits the Sun",
    category="Astronomy",
    tags=["earth", "sun", "orbit"],
    date_recorded=datetime.now(),
    last_updated=datetime.now(),
    reliability_rating=ReliabilityRating.VERIFIED,
    source_id="astronomy_textbook",
    source_title="Principles of Astronomy",
    author_creator="Dr. Neil Stargazer",
    publication_date=datetime.now(),
    url_reference="https://example.com/astronomy",
    related_facts=[],
    contextual_notes="Fundamental astronomical fact",
    access_level="public",
    usage_count=100
)

# Use semantic capabilities
semantic_kg = SemanticKnowledgeGraph(kg)
entities = semantic_kg.extract_entities_from_text("NASA launched the James Webb Space Telescope in December 2021.")
relations = semantic_kg.extract_relations_from_text("NASA launched the James Webb Space Telescope in December 2021.")

# For large datasets, use sharding
sharded_kg = ShardedKnowledgeGraph("shards_directory", shard_size=1000)
```

## Examples

See the `examples` directory for detailed usage examples:
- `basic_usage.py`: Simple knowledge graph operations
- `enhanced_features.py`: Advanced features demonstration

## Documentation

For detailed documentation, see the docstrings in the source code or run:

```python
help(knowledge_graph_pkg)
```

## License

MIT
