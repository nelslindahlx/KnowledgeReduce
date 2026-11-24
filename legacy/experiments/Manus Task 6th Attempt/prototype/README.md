# KnowledgeReduce Prototype

This prototype demonstrates the core concepts of the KnowledgeReduce framework for building stackable knowledge repositories. It implements simplified versions of the mapping and reducing phases to show how raw data can be transformed into a structured knowledge graph.

## Overview

The prototype focuses on the following key components:

1. **Data Ingestion**: Simple CSV/JSON data loading
2. **Knowledge Mapping**: Entity and relationship extraction
3. **Knowledge Reduction**: Entity resolution and graph synthesis
4. **Basic Query Interface**: Simple queries against the knowledge graph

## Project Structure

```
prototype/
├── README.md                 # This file
├── data/                     # Sample data files
│   ├── entities.csv          # Sample entity data
│   └── relationships.csv     # Sample relationship data
├── src/                      # Source code
│   ├── __init__.py           # Package initialization
│   ├── config.py             # Configuration settings
│   ├── data_ingestion.py     # Data loading and preprocessing
│   ├── knowledge_mapping.py  # Entity and relationship extraction
│   ├── knowledge_reduction.py # Entity resolution and graph synthesis
│   ├── graph_store.py        # Graph database interface
│   └── query_interface.py    # Simple query functionality
├── tests/                    # Test files
│   ├── __init__.py           # Test package initialization
│   ├── test_data_ingestion.py # Tests for data ingestion
│   ├── test_knowledge_mapping.py # Tests for knowledge mapping
│   └── test_knowledge_reduction.py # Tests for knowledge reduction
└── main.py                   # Main entry point
```

## Installation

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up Neo4j (optional, for full functionality):
   - Install Neo4j Desktop or use a Docker container
   - Create a new database
   - Update the connection settings in `config.py`

## Usage

Run the prototype with sample data:
```bash
python main.py
```

This will:
1. Load sample data
2. Extract entities and relationships
3. Resolve and merge duplicate entities
4. Create a knowledge graph
5. Run example queries

## Implementation Details

This prototype implements the core concepts from the KnowledgeReduce paper:

1. **Mapping Phase**: Extracts entities and relationships from raw data, similar to the "map" phase in MapReduce.
2. **Reducing Phase**: Consolidates entities and relationships, resolving conflicts and creating a coherent knowledge graph.
3. **Stackable Knowledge**: Demonstrates basic knowledge layering through entity categorization.

## Limitations

This is a simplified implementation intended to demonstrate concepts rather than provide a production-ready system. Limitations include:

- Limited data source support (CSV/JSON only)
- Basic entity extraction (rule-based rather than ML-based)
- Simple entity resolution (exact and fuzzy matching only)
- In-memory graph representation (with optional Neo4j persistence)
- No distributed processing capabilities
