# KnowledgeReduce

A Python package for creating, managing, and querying knowledge graphs with BERT-based question answering capabilities.

## Project Overview

KnowledgeReduce is a comprehensive knowledge graph framework that enables users to:

- Create and manage knowledge graphs using NetworkX
- Extract information from web content and text documents
- Assign reliability ratings to knowledge facts
- Query knowledge graphs using natural language with BERT-based question answering
- Visualize knowledge relationships and connections

The project consists of a core Python package (`knowledge_graph_pkg`) and a collection of Jupyter notebooks demonstrating various use cases and implementations.

## Installation

### Requirements

- Python 3.8+
- NetworkX
- NLTK
- spaCy
- Transformers (for BERT-based question answering)
- BeautifulSoup4 (for web scraping)

### Installing from Source

```bash
git clone https://github.com/nelslindahlx/KnowledgeReduce.git
cd KnowledgeReduce/knowledge_graph_pkg
pip install -e .
```

### Installing from PyPI

```bash
pip install knowledge_graph_pkg
```

## Quick Start

```python
from knowledge_graph_pkg import KnowledgeGraph
from knowledge_graph_pkg.core import ReliabilityRating
from datetime import datetime

# Create a new knowledge graph
kg = KnowledgeGraph()

# Add a fact to the knowledge graph
kg.add_fact(
    fact_id="fact1",
    fact_statement="The Earth orbits the Sun",
    category="Astronomy",
    tags=["Earth", "Sun", "orbit"],
    date_recorded=datetime.now(),
    last_updated=datetime.now(),
    reliability_rating=ReliabilityRating.VERIFIED,
    source_id="source1",
    source_title="Astronomy Textbook",
    author_creator="Dr. Astronomer",
    publication_date=datetime.now(),
    url_reference="https://example.com/astronomy",
    related_facts=[],
    contextual_notes="Basic astronomical fact",
    access_level="public",
    usage_count=10
)

# Retrieve a fact from the knowledge graph
fact = kg.get_fact("fact1")
print(fact)

# Update a fact in the knowledge graph
kg.update_fact("fact1", usage_count=11)
```

## Core Features

### Knowledge Graph Creation and Management

- Create knowledge graphs with structured fact representation
- Add, retrieve, and update facts with comprehensive metadata
- Assign reliability ratings to facts for quality assessment
- Track usage statistics and update history

### Web Scraping and Text Processing

- Extract information from web pages and documents
- Process text using NLTK and spaCy for entity recognition
- Convert unstructured text into structured knowledge facts

### BERT-based Question Answering

- Query knowledge graphs using natural language
- Leverage BERT models for accurate question answering
- Rank answers based on reliability and relevance

### Visualization and Export

- Visualize knowledge graphs using NetworkX
- Export graphs to various formats (GEXF, GraphML)
- Generate interactive visualizations for exploration

## Documentation

For detailed documentation and examples, please refer to the Jupyter notebooks in the repository:

- **Basic Knowledge Graph Creation**: `notebooks/01_basic_knowledge_graph.ipynb`
- **Advanced Knowledge Graph Features**: `notebooks/02_advanced_knowledge_graph.ipynb`
- **BERT Question Answering**: `notebooks/03_bert_question_answering.ipynb`
- **Web Scraping and Text Processing**: `notebooks/04_web_scraping.ipynb`
- **Visualization and Export**: `notebooks/05_visualization.ipynb`

## API Reference

### KnowledgeGraph Class

The main class for creating and managing knowledge graphs.

```python
class KnowledgeGraph:
    def __init__(self)
    def add_fact(self, fact_id, fact_statement, category, tags, date_recorded, last_updated,
                 reliability_rating, source_id, source_title, author_creator,
                 publication_date, url_reference, related_facts, contextual_notes,
                 access_level, usage_count)
    def get_fact(self, fact_id)
    def update_fact(self, fact_id, **kwargs)
```

### ReliabilityRating Enum

Enum for representing the reliability of facts in the knowledge graph.

```python
class ReliabilityRating(Enum):
    UNVERIFIED = 1
    POSSIBLY_TRUE = 2
    LIKELY_TRUE = 3
    VERIFIED = 4
```

## Contributing

Contributions to KnowledgeReduce are welcome! Please follow these steps to contribute:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please ensure your code follows the project's coding standards and includes appropriate tests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Roadmap

Future development plans for KnowledgeReduce include:

- Advanced NLP integration for improved fact extraction
- Scalability improvements for handling larger knowledge graphs
- Semantic reasoning capabilities
- Integration with external knowledge bases
- Enhanced visualization tools
- Performance optimizations
