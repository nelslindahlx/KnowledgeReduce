# KnowledgeReduce

A Python library for creating, managing, and querying portable knowledge graphs with reliability ratings.

## Overview

KnowledgeReduce provides tools for building knowledge graphs from text content, managing facts with reliability ratings, and integrating with BERT-based question answering systems. The project aims to create lightweight, portable knowledge representations that can be easily shared and integrated into various applications.

## Features

- Create and manage directed knowledge graphs using NetworkX
- Assign reliability ratings to facts (Unverified, Possibly True, Likely True, Verified)
- Store detailed metadata with each fact (source, author, dates, etc.)
- Update and query facts within the knowledge graph
- Integration examples with BERT-based question answering

## Installation

```bash
pip install knowledge_graph_pkg
```

### Requirements

- Python 3.6+
- NetworkX
- spaCy
- requests
- beautifulsoup4

## Quick Start

```python
from knowledge_graph_pkg import KnowledgeGraph
from knowledge_graph_pkg.core import ReliabilityRating
from datetime import datetime

# Create a new knowledge graph
kg = KnowledgeGraph()

# Add a fact with metadata
kg.add_fact(
    fact_id="fact1",
    fact_statement="The sky is blue due to Rayleigh scattering of sunlight.",
    category="Science",
    tags=["sky", "color", "physics"],
    date_recorded=datetime.now(),
    last_updated=datetime.now(),
    reliability_rating=ReliabilityRating.VERIFIED,
    source_id="source1",
    source_title="Atmospheric Physics Journal",
    author_creator="Dr. Sky Researcher",
    publication_date=datetime.now(),
    url_reference="https://example.com/sky-color",
    related_facts=[],
    contextual_notes="Observed during clear weather conditions",
    access_level="public",
    usage_count=5
)

# Retrieve a fact
fact = kg.get_fact("fact1")
print(fact['fact_statement'])

# Update a fact
kg.update_fact("fact1", reliability_rating=ReliabilityRating.LIKELY_TRUE)
```

## Documentation

For more detailed documentation and examples, see the [notebooks](./CivicHonorsAdvancedKGv2.ipynb) in this repository.

## Project Structure

- `knowledge_graph_pkg/`: Core package implementation
  - `core.py`: Main implementation of KnowledgeGraph class
  - `tests/`: Unit tests for the package
- Jupyter notebooks: Various implementations and examples of knowledge graph usage

## Development

### Testing

Run the tests with pytest:

```bash
pytest knowledge_graph_pkg/tests/
```

### Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the terms of the license included in the repository.

## Author

Nels Lindahl (nels@nelslindahl.com)
