# User Guide

## Introduction

Welcome to the KnowledgeReduce framework! This guide will help you get started with using the framework to build stackable knowledge graphs from various data sources.

KnowledgeReduce adapts the MapReduce paradigm for knowledge processing, enabling incremental knowledge building, integration, and conflict resolution. The framework provides a comprehensive solution for constructing knowledge graphs with support for hierarchical knowledge stacks.

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Installation Steps

1. Clone the repository:
```bash
git clone https://github.com/yourusername/knowledge_reduce.git
```

2. Navigate to the project directory:
```bash
cd knowledge_reduce
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install the package in development mode:
```bash
pip install -e .
```

## Quick Start

Here's a simple example to get you started with KnowledgeReduce:

```python
from knowledge_reduce import KnowledgeReduce
from knowledge_reduce.data_ingestion import FileConnector
from knowledge_reduce.mapping_engine.entity_extractors import SimpleEntityExtractor
from knowledge_reduce.mapping_engine.relationship_extractors import SimpleRelationshipExtractor
from knowledge_reduce.mapping_engine.disambiguation import SimpleDisambiguationEngine

# Initialize KnowledgeReduce
kr = KnowledgeReduce()

# Configure data ingestion
file_connector = FileConnector("data/sample.json", "json")
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
kr.export_knowledge_graph("output/knowledge_graph.json", "json")
```

## Working with Data Sources

KnowledgeReduce supports various data sources through connectors. Here's how to use them:

### File Connector

```python
from knowledge_reduce.data_ingestion import FileConnector

# JSON file
json_connector = FileConnector("data/sample.json", "json")

# CSV file
csv_connector = FileConnector("data/sample.csv", "csv")

# XML file
xml_connector = FileConnector("data/sample.xml", "xml")

# Register with KnowledgeReduce
kr.register_data_source(json_connector)
kr.register_data_source(csv_connector)
kr.register_data_source(xml_connector)
```

### API Connector

```python
from knowledge_reduce.data_ingestion import APIConnector

# Basic API
api_connector = APIConnector("https://api.example.com/data")

# API with authentication
auth_api_connector = APIConnector(
    "https://api.example.com/data",
    headers={"Authorization": "Bearer token"}
)

# API with parameters
params_api_connector = APIConnector(
    "https://api.example.com/data",
    params={"limit": 100, "offset": 0}
)

# Register with KnowledgeReduce
kr.register_data_source(api_connector)
kr.register_data_source(auth_api_connector)
kr.register_data_source(params_api_connector)
```

## Entity and Relationship Extraction

KnowledgeReduce extracts entities and relationships from raw data using extractors:

### Entity Extraction

```python
from knowledge_reduce.mapping_engine.entity_extractors import SimpleEntityExtractor

# Initialize entity extractor
entity_extractor = SimpleEntityExtractor()

# Register with KnowledgeReduce
kr.register_entity_extractor(entity_extractor)
```

### Relationship Extraction

```python
from knowledge_reduce.mapping_engine.relationship_extractors import SimpleRelationshipExtractor

# Initialize relationship extractor
relationship_extractor = SimpleRelationshipExtractor()

# Register with KnowledgeReduce
kr.register_relationship_extractor(relationship_extractor)
```

### Entity Disambiguation

```python
from knowledge_reduce.mapping_engine.disambiguation import SimpleDisambiguationEngine

# Initialize disambiguation engine
disambiguation_engine = SimpleDisambiguationEngine()

# Register with KnowledgeReduce
kr.set_disambiguation_engine(disambiguation_engine)
```

## Conflict Resolution

KnowledgeReduce resolves conflicts between different data sources using conflict resolvers:

### Confidence-Based Resolution

```python
from knowledge_reduce.reducing_engine.conflict_resolvers import ConfidenceBasedResolver

# Initialize conflict resolver
resolver = ConfidenceBasedResolver()

# Register with KnowledgeReduce
kr.register_conflict_resolver(resolver)
```

### Majority Voting Resolution

```python
from knowledge_reduce.reducing_engine.conflict_resolvers import MajorityVotingResolver

# Initialize conflict resolver
resolver = MajorityVotingResolver()

# Register with KnowledgeReduce
kr.register_conflict_resolver(resolver)
```

### Source Priority Resolution

```python
from knowledge_reduce.reducing_engine.conflict_resolvers import SourcePriorityResolver

# Initialize conflict resolver
resolver = SourcePriorityResolver()

# Set source priorities
resolver.set_source_priority("source1", 3)  # Higher priority
resolver.set_source_priority("source2", 2)
resolver.set_source_priority("source3", 1)  # Lower priority

# Register with KnowledgeReduce
kr.register_conflict_resolver(resolver)
```

## Working with Knowledge Stacks

KnowledgeReduce supports stackable knowledge through knowledge stacks:

### Creating Stacks

```python
# Create stacks
kr.create_stack("stack1", "First knowledge stack")
kr.create_stack("stack2", "Second knowledge stack")
```

### Processing Data into Stacks

```python
# Process data into stack1
kr.set_current_stack("stack1")
kr.process(["data_source1"])

# Process data into stack2
kr.set_current_stack("stack2")
kr.process(["data_source2"])
```

### Creating Stack Hierarchies

```python
# Create hierarchy (stack1 is parent of stack2)
kr.stack_manager.create_stack_hierarchy("stack1", "stack2")
```

### Merging Stacks

```python
# Union merge
union_stack = kr.merge_stacks(["stack1", "stack2"], "union_stack", "union")

# Intersection merge
intersection_stack = kr.merge_stacks(["stack1", "stack2"], "intersection_stack", "intersection")
```

### Getting Combined Knowledge

```python
# Get combined knowledge from stack2 and its ancestors
combined_knowledge = kr.stack_manager.get_combined_stack("stack2", include_ancestors=True)
```

### Visualizing Stack Hierarchy

```python
# Visualize stack hierarchy
kr.stack_manager.visualize_stack_hierarchy("output/stack_hierarchy.png")
```

## Querying the Knowledge Graph

KnowledgeReduce allows querying the knowledge graph:

```python
# Query the knowledge graph
results = kr.query_knowledge_graph("MATCH (n) RETURN n")
```

## Exporting the Knowledge Graph

KnowledgeReduce supports exporting the knowledge graph to various formats:

```python
# Export to JSON
kr.export_knowledge_graph("output/graph.json", "json")

# Export to GraphML
kr.export_knowledge_graph("output/graph.graphml", "graphml")
```

## Saving and Loading State

KnowledgeReduce allows saving and loading the state of the framework:

```python
# Save state
kr.save_state("output/kr_state")

# Load state
kr.load_state("output/kr_state")
```

## Advanced Usage

### Creating Custom Entity Extractors

```python
from knowledge_reduce.mapping_engine.entity_extractors import BaseEntityExtractor

class CustomEntityExtractor(BaseEntityExtractor):
    def extract(self, data):
        entities = []
        # Custom extraction logic
        return entities

# Register with KnowledgeReduce
kr.register_entity_extractor(CustomEntityExtractor())
```

### Creating Custom Relationship Extractors

```python
from knowledge_reduce.mapping_engine.relationship_extractors import BaseRelationshipExtractor

class CustomRelationshipExtractor(BaseRelationshipExtractor):
    def extract(self, data, entities):
        relationships = []
        # Custom extraction logic
        return relationships

# Register with KnowledgeReduce
kr.register_relationship_extractor(CustomRelationshipExtractor())
```

### Creating Custom Conflict Resolvers

```python
from knowledge_reduce.reducing_engine.conflict_resolvers import BaseConflictResolver

class CustomConflictResolver(BaseConflictResolver):
    def resolve_entity_conflicts(self, entities, aggregated):
        # Custom conflict resolution logic
        return resolved_entity
    
    def resolve_relationship_conflicts(self, relationships, aggregated):
        # Custom conflict resolution logic
        return resolved_relationship

# Register with KnowledgeReduce
kr.register_conflict_resolver(CustomConflictResolver())
```

## Troubleshooting

### Common Issues

1. **Data source connection issues**
   - Check that the data source is accessible
   - Verify connection parameters
   - Check network connectivity

2. **Entity extraction issues**
   - Check that the data format is supported
   - Verify that the entity extractor is configured correctly
   - Check for data quality issues

3. **Relationship extraction issues**
   - Verify that entities are extracted correctly
   - Check that the relationship extractor is configured correctly
   - Check for data quality issues

4. **Knowledge graph issues**
   - Verify that entities and relationships are extracted correctly
   - Check that the knowledge graph is built correctly
   - Verify export format compatibility

### Getting Help

If you encounter issues not covered in this guide, please:
- Check the API reference documentation
- Look at the example code in the `examples` directory
- Submit an issue on the GitHub repository

## Next Steps

Now that you're familiar with the basics of KnowledgeReduce, you can:
- Explore the example code in the `examples` directory
- Read the API reference documentation
- Customize the framework for your specific needs
- Contribute to the project on GitHub
