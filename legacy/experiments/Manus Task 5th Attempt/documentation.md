# KnowledgeReduce System Documentation

## Overview

The KnowledgeReduce system is an implementation of the conceptual framework described in the paper "KnowledgeReduce: Building Stackable Sets of Knowledge." It adapts the MapReduce paradigm for knowledge graph construction, providing a scalable and flexible solution for extracting facts from diverse data sources and organizing them into a comprehensive knowledge graph.

## System Architecture

The system follows a modular architecture with three main components:

1. **Fact Extraction Module**: Extracts entities and relationships from text data
2. **Knowledge Stacking Algorithm**: Aggregates facts from multiple sources and resolves conflicts
3. **Database Integration Components**: Stores and queries the knowledge graph

### Component Diagram

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  Fact           │     │  Knowledge      │     │  Database       │
│  Extraction     │────▶│  Stacking      │────▶│  Integration    │
│  Module         │     │  Algorithm      │     │  Components     │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        ▲                       ▲                       ▲
        │                       │                       │
        │                       │                       │
┌───────┴───────────────────────┴───────────────────────┴───────┐
│                                                               │
│                      KnowledgeReduce System                   │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

## Components

### 1. Fact Extraction Module

The fact extraction module is responsible for identifying entities and relationships in text data. It consists of three main components:

- **EntityRecognizer**: Identifies entities in text using NLP techniques
- **RelationshipExtractor**: Extracts relationships between entities
- **IntermediateRepresentationGenerator**: Creates a structured representation of entities and relationships

#### Key Features:
- Named Entity Recognition (NER) for identifying people, organizations, locations, etc.
- Relationship extraction using dependency parsing
- Intermediate representation in a format suitable for knowledge stacking

### 2. Knowledge Stacking Algorithm

The knowledge stacking algorithm aggregates facts from multiple sources and resolves conflicts to create a comprehensive knowledge graph. It consists of three main components:

- **EntityAggregator**: Combines information about the same entities from different sources
- **ConflictResolver**: Resolves contradictory information using trust scores and majority voting
- **GraphSynthesizer**: Constructs the knowledge graph from aggregated data

#### Key Features:
- Entity aggregation with mention counting
- Conflict resolution using trust scores
- Graph synthesis using NetworkX

### 3. Database Integration Components

The database integration components provide storage and querying capabilities for the knowledge graph. They consist of four main components:

- **Neo4jConnector**: Connects to a Neo4j graph database
- **GraphDatabaseManager**: Manages the storage of knowledge graphs
- **QueryInterface**: Provides methods for querying the knowledge graph
- **DataPersistenceLayer**: Handles import/export between the application and database

#### Key Features:
- Neo4j integration for graph storage
- Cypher query support
- JSON import/export functionality
- Mock database implementation for testing

## Workflow

The KnowledgeReduce system follows this workflow:

1. **Data Ingestion**: Text data is loaded from files
2. **Fact Extraction**: Entities and relationships are extracted from the text
3. **Knowledge Stacking**: Facts are aggregated and conflicts are resolved
4. **Graph Storage**: The knowledge graph is stored in a database
5. **Querying**: The knowledge graph can be queried for information

## Usage

### Basic Usage

```python
from knowledge_reduce.main import KnowledgeReduceSystem

# Create system with mock database
system = KnowledgeReduceSystem(use_mock_db=True)

# Process text files
file_paths = ['/path/to/data.txt']
system.run_complete_workflow(file_paths)
```

### With Neo4j Database

```python
from knowledge_reduce.main import KnowledgeReduceSystem

# Create system with Neo4j database
system = KnowledgeReduceSystem(
    use_mock_db=False,
    db_uri="bolt://localhost:7687",
    username="neo4j",
    password="password"
)

# Process text files
file_paths = ['/path/to/data.txt']
system.run_complete_workflow(file_paths)
```

### Command Line Interface

```bash
python -m knowledge_reduce.main --files /path/to/data1.txt /path/to/data2.txt
```

## Performance

The system has been tested with sample data and demonstrates the following capabilities:

- Entity extraction from text data
- Relationship identification between entities
- Knowledge stacking from multiple sources
- Conflict resolution for contradictory information
- Graph storage and querying

## Future Enhancements

1. **Improved Entity Recognition**: Integrate more advanced NLP models for better entity recognition
2. **Enhanced Relationship Extraction**: Implement more sophisticated relationship extraction techniques
3. **Distributed Processing**: Add support for distributed processing of large datasets
4. **User Interface**: Develop a web-based interface for visualizing and interacting with the knowledge graph
5. **Real-time Updates**: Implement real-time updates to the knowledge graph from streaming data sources

## Conclusion

The KnowledgeReduce system provides a robust implementation of the KnowledgeReduce framework described in the paper. It enables efficient extraction of facts from diverse data sources and their organization into a comprehensive knowledge graph. The modular architecture allows for easy extension and customization to meet specific requirements.
