# KnowledgeReduce Framework Documentation

## Overview

KnowledgeReduce is a framework for building and managing stackable knowledge graphs. It adapts the MapReduce paradigm for knowledge processing, enabling the creation, integration, and management of knowledge from various sources. The framework supports incremental knowledge building, conflict resolution, and hierarchical organization of knowledge stacks.

## Key Concepts

### Knowledge Reduce

Knowledge Reduce adapts the MapReduce paradigm for knowledge processing:

1. **Map Phase**: Extracts entities and relationships from raw data sources
2. **Reduce Phase**: Aggregates entities and relationships, resolves conflicts, and builds a knowledge graph

### Stackable Knowledge

Stackable Knowledge is a key innovation that allows knowledge to be organized in layers or stacks:

1. **Knowledge Stacks**: Coherent units of knowledge that can be layered and combined
2. **Stack Hierarchy**: Parent-child relationships between knowledge stacks
3. **Stack Operations**: Union, intersection, and difference operations on knowledge stacks

## System Architecture

The KnowledgeReduce framework consists of the following components:

1. **Data Ingestion**: Connectors for various data sources
2. **Mapping Engine**: Entity extractors, relationship extractors, and disambiguation engines
3. **Reducing Engine**: Aggregators and conflict resolvers
4. **Knowledge Graph**: Graph storage, querying, and export capabilities
5. **Stackable Knowledge Manager**: Creation, management, and operations on knowledge stacks

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/knowledge_reduce.git

# Navigate to the project directory
cd knowledge_reduce

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Basic Usage

```python
from knowledge_reduce import KnowledgeReduce
from knowledge_reduce.data_ingestion import FileConnector
from knowledge_reduce.mapping_engine.entity_extractors import SimpleEntityExtractor
from knowledge_reduce.mapping_engine.relationship_extractors import SimpleRelationshipExtractor
from knowledge_reduce.mapping_engine.disambiguation import SimpleDisambiguationEngine

# Initialize KnowledgeReduce
kr = KnowledgeReduce()

# Configure data ingestion
file_connector = FileConnector("data.json", "json")
kr.register_data_source(file_connector)

# Configure mapping engine
entity_extractor = SimpleEntityExtractor()
relationship_extractor = SimpleRelationshipExtractor()
disambiguation_engine = SimpleDisambiguationEngine()

kr.register_entity_extractor(entity_extractor)
kr.register_relationship_extractor(relationship_extractor)
kr.set_disambiguation_engine(disambiguation_engine)

# Process data
result = kr.process()

# Export knowledge graph
kr.export_knowledge_graph("knowledge_graph.json", "json")
```

### Stackable Knowledge

```python
# Create knowledge stacks
kr.create_stack("stack1", "First knowledge stack")
kr.create_stack("stack2", "Second knowledge stack")

# Process data into different stacks
kr.set_current_stack("stack1")
kr.process(["data_source1"])

kr.set_current_stack("stack2")
kr.process(["data_source2"])

# Create stack hierarchy
kr.stack_manager.create_stack_hierarchy("stack1", "stack2")

# Merge stacks
merged_stack = kr.merge_stacks(["stack1", "stack2"], "merged_stack", "union")

# Get combined knowledge
combined_knowledge = kr.stack_manager.get_combined_stack("stack2", include_ancestors=True)
```

## API Reference

### KnowledgeReduce

The main class that orchestrates the entire knowledge reduction process.

#### Methods

- `__init__(config=None)`: Initialize the KnowledgeReduce framework
- `register_data_source(data_source)`: Register a data source
- `register_entity_extractor(extractor)`: Register an entity extractor
- `register_relationship_extractor(extractor)`: Register a relationship extractor
- `set_disambiguation_engine(engine)`: Set the disambiguation engine
- `create_stack(name, description=None, metadata=None)`: Create a new knowledge stack
- `set_current_stack(name)`: Set the current knowledge stack
- `process(data_source_names=None, stack_name=None)`: Process data from registered data sources
- `query_knowledge_graph(query_string, params=None)`: Query the knowledge graph
- `export_knowledge_graph(output_path, format='graphml')`: Export the knowledge graph to a file
- `merge_stacks(stack_names, new_stack_name, merge_type='union')`: Merge multiple knowledge stacks
- `get_stack_hierarchy(stack_name)`: Get the hierarchy of a stack
- `save_state(path)`: Save the current state of the framework
- `load_state(path)`: Load a previously saved state

### Data Ingestion

#### FileConnector

Connector for ingesting data from files.

```python
from knowledge_reduce.data_ingestion import FileConnector

# Initialize a file connector
connector = FileConnector("data.json", "json")
```

#### APIConnector

Connector for ingesting data from APIs.

```python
from knowledge_reduce.data_ingestion import APIConnector

# Initialize an API connector
connector = APIConnector("https://api.example.com/data", headers={"Authorization": "Bearer token"})
```

### Mapping Engine

#### Entity Extractors

```python
from knowledge_reduce.mapping_engine.entity_extractors import SimpleEntityExtractor

# Initialize an entity extractor
extractor = SimpleEntityExtractor()

# Extract entities from data
entities = extractor.extract(data)
```

#### Relationship Extractors

```python
from knowledge_reduce.mapping_engine.relationship_extractors import SimpleRelationshipExtractor

# Initialize a relationship extractor
extractor = SimpleRelationshipExtractor()

# Extract relationships from data
relationships = extractor.extract(data, entities)
```

#### Disambiguation Engines

```python
from knowledge_reduce.mapping_engine.disambiguation import SimpleDisambiguationEngine

# Initialize a disambiguation engine
engine = SimpleDisambiguationEngine()

# Disambiguate entities
disambiguated_entities = engine.disambiguate(entities)
```

### Reducing Engine

#### Aggregators

```python
from knowledge_reduce.reducing_engine.aggregators import SimpleAggregator

# Initialize an aggregator
aggregator = SimpleAggregator()

# Register with KnowledgeReduce
kr.reducing_engine.register_aggregator(aggregator)
```

#### Conflict Resolvers

```python
from knowledge_reduce.reducing_engine.conflict_resolvers import ConfidenceBasedResolver

# Initialize a conflict resolver
resolver = ConfidenceBasedResolver()

# Register with KnowledgeReduce
kr.reducing_engine.register_conflict_resolver(resolver)
```

### Knowledge Graph

```python
# Build knowledge graph
kr.knowledge_graph.build(reduced_data)

# Query knowledge graph
results = kr.knowledge_graph.query("MATCH (n) RETURN n")

# Export knowledge graph
kr.knowledge_graph.export("graph.json", "json")
```

### Stackable Knowledge Manager

```python
from knowledge_reduce.knowledge_graph.stackable import StackableKnowledgeManager

# Initialize a stackable knowledge manager
manager = StackableKnowledgeManager()

# Create stacks
stack1 = manager.create_stack("stack1", "First stack")
stack2 = manager.create_stack("stack2", "Second stack")

# Create hierarchy
manager.create_stack_hierarchy("stack1", "stack2")

# Merge stacks
merged_stack = manager.merge_stacks(["stack1", "stack2"], "merged_stack", "union")

# Get stack lineage
lineage = manager.get_stack_lineage("stack2")

# Visualize stack hierarchy
manager.visualize_stack_hierarchy("hierarchy.png")
```

## Examples

See the `examples` directory for demonstration examples:

- `basic_example.py`: Basic usage of KnowledgeReduce
- `stackable_knowledge_example.py`: Working with stackable knowledge
- `incremental_knowledge_example.py`: Incremental knowledge building
- `knowledge_integration_example.py`: Integrating knowledge from multiple sources

## Testing

Run the test suite to validate the implementation:

```bash
cd tests
python run_tests.py
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
