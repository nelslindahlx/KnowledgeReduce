# KnowledgeReduce

A Python framework for building stackable knowledge graphs, inspired by the MapReduce model.

## Overview

KnowledgeReduce is a conceptual framework designed for constructing knowledge graphs from extensive, diverse datasets. It adapts the MapReduce model's core principles to meet the unique challenges of knowledge graph creation, such as entity recognition, relationship extraction, and data integration.

This implementation provides a comprehensive solution for:
- Extracting facts from web sources
- Constructing structured knowledge graphs
- Cleaning and deduplicating data
- Serializing graphs for portability

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/knowledgereduce.git
cd knowledgereduce

# Install dependencies
pip install -r requirements.txt

# Install spaCy model for advanced cleaning
python -m spacy download en_core_web_md
```

## Quick Start

```python
from knowledge_reduce.graph import ReliabilityRating
from knowledge_reduce.main import build_knowledge_graph_from_urls, save_knowledge_graph

# Define URLs to scrape
urls = {
    "Example1": "https://example.com",
    "Example2": "https://example.org"
}

# Build knowledge graph from URLs with automatic cleaning
kg, stats = build_knowledge_graph_from_urls(
    urls,
    category="General",
    tags=["Example", "WebScraped"],
    reliability_rating=ReliabilityRating.LIKELY_TRUE,
    clean=True
)

# Print statistics
print(f"Initial facts extracted: {stats['initial_count']}")
print(f"Duplicates removed: {stats['duplicates_removed']}")
print(f"Final fact count: {stats['final_count']}")

# Save knowledge graph
save_knowledge_graph(kg, "knowledge_graph.json")
```

## Core Components

### KnowledgeGraph

The central data structure for storing and managing knowledge:

```python
from knowledge_reduce.graph import KnowledgeGraph, ReliabilityRating

# Create a knowledge graph
kg = KnowledgeGraph()

# Add a fact
kg.add_fact(
    fact_id="fact_1",
    fact_statement="The Earth orbits the Sun.",
    category="Astronomy",
    tags=["planet", "solar system"],
    reliability_rating=ReliabilityRating.VERIFIED,
    source_id="textbook",
    source_title="Astronomy 101",
    author_creator="Dr. Smith",
    contextual_notes="Basic astronomical fact"
)

# Retrieve a fact
fact = kg.get_fact("fact_1")

# Update a fact
kg.update_fact("fact_1", usage_count=5)

# Save to file
kg.save_to_file("astronomy_facts.json")
```

### Web Extraction

Extract facts from web sources:

```python
from knowledge_reduce.extraction import populate_knowledge_graph_from_urls
from knowledge_reduce.graph import KnowledgeGraph, ReliabilityRating

# Create a knowledge graph
kg = KnowledgeGraph()

# Define URLs to scrape
urls = {
    "NASA": "https://www.nasa.gov/solar-system/",
    "ESA": "https://www.esa.int/Science_Exploration/Space_Science/Solar_System"
}

# Populate knowledge graph from URLs
fact_count = populate_knowledge_graph_from_urls(
    kg,
    urls,
    category="Astronomy",
    tags=["Space", "Research"],
    reliability_rating=ReliabilityRating.LIKELY_TRUE
)

print(f"Extracted {fact_count} facts")
```

### Data Cleaning

Clean and deduplicate facts:

```python
from knowledge_reduce.processing import clean_knowledge_graph

# Clean the knowledge graph
stats = clean_knowledge_graph(
    kg,
    basic=True,      # Remove exact duplicates
    advanced=True,   # Remove short facts and similar text
    semantic=True,   # Remove semantically similar facts
    similarity_threshold=0.8,
    short_fact_threshold=50
)

print(f"Removed {stats['total_removed']} facts")
```

### Serialization

Serialize and deserialize knowledge graphs:

```python
from knowledge_reduce.utils import serialize_knowledge_graph, deserialize_knowledge_graph
from knowledge_reduce.graph import KnowledgeGraph

# Serialize
serialize_knowledge_graph(kg, "knowledge_graph.json")

# Deserialize
loaded_kg = deserialize_knowledge_graph("knowledge_graph.json", KnowledgeGraph)

# Sharded serialization for large graphs
from knowledge_reduce.main import save_knowledge_graph, load_knowledge_graph

# Save with sharding (100 nodes per shard)
save_knowledge_graph(kg, "large_graph.json", sharded=True, shard_size=100)

# Load sharded graph
loaded_kg = load_knowledge_graph("large_graph_shard_metadata.json", sharded=True)
```

## Advanced Usage

### Custom Data Sources

You can extend the framework to work with custom data sources:

```python
from knowledge_reduce.graph import KnowledgeGraph, ReliabilityRating
from datetime import datetime

def extract_facts_from_custom_source(source_data, kg):
    """Extract facts from a custom data source and add to knowledge graph."""
    for i, item in enumerate(source_data):
        kg.add_fact(
            fact_id=f"custom_{i}",
            fact_statement=item["text"],
            category=item["category"],
            tags=item["tags"],
            reliability_rating=ReliabilityRating.UNVERIFIED,
            source_id="custom_source",
            date_recorded=datetime.now()
        )
    return len(source_data)
```

### Custom Cleaning Methods

Implement custom cleaning methods:

```python
def custom_cleaning(knowledge_graph, threshold=0.5):
    """Custom cleaning method."""
    # Your custom cleaning logic here
    removed_count = 0
    # ...
    return removed_count
```

## Project Structure

```
knowledge_reduce/
├── __init__.py        # Package initialization
├── main.py            # High-level functions
├── graph/             # Core data structures
│   ├── __init__.py
│   └── core.py        # KnowledgeGraph and ReliabilityRating
├── extraction/        # Data extraction utilities
│   ├── __init__.py
│   └── web.py         # Web scraping functions
├── processing/        # Data processing utilities
│   ├── __init__.py
│   └── cleaning.py    # Cleaning and deduplication
└── utils/             # Utility functions
    ├── __init__.py
    └── serialization.py # Serialization utilities
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

This framework is based on the paper "KnowledgeReduce: Building Stackable Sets of Knowledge" by Nels Lindahl.
