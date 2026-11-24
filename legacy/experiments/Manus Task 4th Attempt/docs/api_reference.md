# API Reference

## KnowledgeReduce

The main class that orchestrates the knowledge processing pipeline.

### Methods

#### `__init__(self)`
Initialize a new KnowledgeReduce instance.

#### `register_data_source(self, data_source)`
Register a data source connector.

Parameters:
- `data_source`: A data source connector instance.

#### `register_entity_extractor(self, entity_extractor)`
Register an entity extractor.

Parameters:
- `entity_extractor`: An entity extractor instance.

#### `register_relationship_extractor(self, relationship_extractor)`
Register a relationship extractor.

Parameters:
- `relationship_extractor`: A relationship extractor instance.

#### `set_disambiguation_engine(self, disambiguation_engine)`
Set the disambiguation engine.

Parameters:
- `disambiguation_engine`: A disambiguation engine instance.

#### `register_aggregator(self, aggregator)`
Register an aggregator in the reducing engine.

Parameters:
- `aggregator`: An aggregator instance.

#### `register_conflict_resolver(self, conflict_resolver)`
Register a conflict resolver in the reducing engine.

Parameters:
- `conflict_resolver`: A conflict resolver instance.

#### `create_stack(self, name, description="")`
Create a new knowledge stack.

Parameters:
- `name`: The name of the stack.
- `description`: Optional description of the stack.

Returns:
- The created stack instance.

#### `set_current_stack(self, stack_name)`
Set the current active stack.

Parameters:
- `stack_name`: The name of the stack to set as current.

#### `merge_stacks(self, stack_names, target_name, merge_type="union")`
Merge multiple stacks into a new stack.

Parameters:
- `stack_names`: List of stack names to merge.
- `target_name`: Name of the target stack.
- `merge_type`: Type of merge operation ("union" or "intersection").

Returns:
- The merged stack instance.

#### `process(self, data_source_names=None)`
Process data through the entire pipeline.

Parameters:
- `data_source_names`: Optional list of data source names to process. If None, all registered data sources are processed.

Returns:
- A dictionary containing the results of each processing phase.

#### `export_knowledge_graph(self, path, format="json")`
Export the knowledge graph to a file.

Parameters:
- `path`: Path to save the exported graph.
- `format`: Format of the export ("json", "graphml", etc.).

Returns:
- The path to the exported file.

#### `query_knowledge_graph(self, query)`
Query the knowledge graph.

Parameters:
- `query`: Query string.

Returns:
- Query results.

#### `save_state(self, path)`
Save the current state of the KnowledgeReduce instance.

Parameters:
- `path`: Path to save the state.

#### `load_state(self, path)`
Load a saved state into the KnowledgeReduce instance.

Parameters:
- `path`: Path to the saved state.

## Data Ingestion

### BaseConnector

Base class for data source connectors.

#### `__init__(self)`
Initialize a new connector instance.

#### `connect(self)`
Connect to the data source.

#### `fetch_data(self)`
Fetch data from the source.

Returns:
- The fetched data.

### FileConnector

Connector for file data sources.

#### `__init__(self, file_path, format="json")`
Initialize a new file connector.

Parameters:
- `file_path`: Path to the file.
- `format`: Format of the file ("json", "csv", "xml", etc.).

#### `connect(self)`
Connect to the file.

#### `fetch_data(self)`
Fetch data from the file.

Returns:
- The fetched data.

### APIConnector

Connector for API data sources.

#### `__init__(self, url, auth=None, params=None)`
Initialize a new API connector.

Parameters:
- `url`: URL of the API.
- `auth`: Authentication information.
- `params`: Request parameters.

#### `connect(self)`
Connect to the API.

#### `fetch_data(self)`
Fetch data from the API.

Returns:
- The fetched data.

## Mapping Engine

### BaseEntityExtractor

Base class for entity extractors.

#### `__init__(self)`
Initialize a new entity extractor instance.

#### `extract(self, data)`
Extract entities from data.

Parameters:
- `data`: The data to extract entities from.

Returns:
- List of extracted entities.

### SimpleEntityExtractor

A simple implementation of entity extractor.

#### `extract(self, data)`
Extract entities from data.

Parameters:
- `data`: The data to extract entities from.

Returns:
- List of extracted entities.

### BaseRelationshipExtractor

Base class for relationship extractors.

#### `__init__(self)`
Initialize a new relationship extractor instance.

#### `extract(self, data, entities)`
Extract relationships from data.

Parameters:
- `data`: The data to extract relationships from.
- `entities`: The entities to consider for relationships.

Returns:
- List of extracted relationships.

### SimpleRelationshipExtractor

A simple implementation of relationship extractor.

#### `extract(self, data, entities)`
Extract relationships from data.

Parameters:
- `data`: The data to extract relationships from.
- `entities`: The entities to consider for relationships.

Returns:
- List of extracted relationships.

### BaseDisambiguationEngine

Base class for disambiguation engines.

#### `__init__(self)`
Initialize a new disambiguation engine instance.

#### `disambiguate(self, entities)`
Disambiguate entities.

Parameters:
- `entities`: The entities to disambiguate.

Returns:
- List of disambiguated entities.

### SimpleDisambiguationEngine

A simple implementation of disambiguation engine.

#### `disambiguate(self, entities)`
Disambiguate entities.

Parameters:
- `entities`: The entities to disambiguate.

Returns:
- List of disambiguated entities.

### ContextualDisambiguationEngine

A disambiguation engine that uses contextual information.

#### `disambiguate(self, entities)`
Disambiguate entities using contextual information.

Parameters:
- `entities`: The entities to disambiguate.

Returns:
- List of disambiguated entities.

## Reducing Engine

### BaseAggregator

Base class for aggregators.

#### `__init__(self)`
Initialize a new aggregator instance.

#### `aggregate_entities(self, entities)`
Aggregate entities.

Parameters:
- `entities`: The entities to aggregate.

Returns:
- List of aggregated entities.

#### `aggregate_relationships(self, relationships)`
Aggregate relationships.

Parameters:
- `relationships`: The relationships to aggregate.

Returns:
- List of aggregated relationships.

### SimpleAggregator

A simple implementation of aggregator.

#### `aggregate_entities(self, entities)`
Aggregate entities.

Parameters:
- `entities`: The entities to aggregate.

Returns:
- List of aggregated entities.

#### `aggregate_relationships(self, relationships)`
Aggregate relationships.

Parameters:
- `relationships`: The relationships to aggregate.

Returns:
- List of aggregated relationships.

### WeightedAggregator

An aggregator that uses weights for aggregation.

#### `aggregate_entities(self, entities)`
Aggregate entities using weights.

Parameters:
- `entities`: The entities to aggregate.

Returns:
- List of aggregated entities.

#### `aggregate_relationships(self, relationships)`
Aggregate relationships using weights.

Parameters:
- `relationships`: The relationships to aggregate.

Returns:
- List of aggregated relationships.

### BaseConflictResolver

Base class for conflict resolvers.

#### `__init__(self)`
Initialize a new conflict resolver instance.

#### `resolve_entity_conflicts(self, entities, aggregated)`
Resolve conflicts between entities.

Parameters:
- `entities`: The original entities.
- `aggregated`: The aggregated entities.

Returns:
- List of resolved entities.

#### `resolve_relationship_conflicts(self, relationships, aggregated)`
Resolve conflicts between relationships.

Parameters:
- `relationships`: The original relationships.
- `aggregated`: The aggregated relationships.

Returns:
- List of resolved relationships.

### ConfidenceBasedResolver

A conflict resolver that uses confidence scores.

#### `resolve_entity_conflicts(self, entities, aggregated)`
Resolve conflicts between entities based on confidence scores.

Parameters:
- `entities`: The original entities.
- `aggregated`: The aggregated entities.

Returns:
- List of resolved entities.

#### `resolve_relationship_conflicts(self, relationships, aggregated)`
Resolve conflicts between relationships based on confidence scores.

Parameters:
- `relationships`: The original relationships.
- `aggregated`: The aggregated relationships.

Returns:
- List of resolved relationships.

### MajorityVotingResolver

A conflict resolver that uses majority voting.

#### `resolve_entity_conflicts(self, entities, aggregated)`
Resolve conflicts between entities based on majority voting.

Parameters:
- `entities`: The original entities.
- `aggregated`: The aggregated entities.

Returns:
- List of resolved entities.

#### `resolve_relationship_conflicts(self, relationships, aggregated)`
Resolve conflicts between relationships based on majority voting.

Parameters:
- `relationships`: The original relationships.
- `aggregated`: The aggregated relationships.

Returns:
- List of resolved relationships.

### SourcePriorityResolver

A conflict resolver that uses source priorities.

#### `set_source_priority(self, source, priority)`
Set the priority for a source.

Parameters:
- `source`: The source identifier.
- `priority`: The priority value.

#### `resolve_entity_conflicts(self, entities, aggregated)`
Resolve conflicts between entities based on source priorities.

Parameters:
- `entities`: The original entities.
- `aggregated`: The aggregated entities.

Returns:
- List of resolved entities.

#### `resolve_relationship_conflicts(self, relationships, aggregated)`
Resolve conflicts between relationships based on source priorities.

Parameters:
- `relationships`: The original relationships.
- `aggregated`: The aggregated relationships.

Returns:
- List of resolved relationships.

## Knowledge Graph

### KnowledgeGraph

Class for managing the knowledge graph.

#### `__init__(self)`
Initialize a new knowledge graph instance.

#### `build(self, data)`
Build the knowledge graph from data.

Parameters:
- `data`: The data to build the graph from.

#### `query(self, query)`
Query the knowledge graph.

Parameters:
- `query`: Query string.

Returns:
- Query results.

#### `export(self, path, format="json")`
Export the knowledge graph to a file.

Parameters:
- `path`: Path to save the exported graph.
- `format`: Format of the export ("json", "graphml", etc.).

Returns:
- The path to the exported file.

## Stackable Knowledge

### KnowledgeStack

Class representing a knowledge stack.

#### `__init__(self, name, description="")`
Initialize a new knowledge stack.

Parameters:
- `name`: The name of the stack.
- `description`: Optional description of the stack.

#### `add_entity(self, entity)`
Add an entity to the stack.

Parameters:
- `entity`: The entity to add.

#### `add_relationship(self, relationship)`
Add a relationship to the stack.

Parameters:
- `relationship`: The relationship to add.

#### `add_entities(self, entities)`
Add multiple entities to the stack.

Parameters:
- `entities`: The entities to add.

#### `add_relationships(self, relationships)`
Add multiple relationships to the stack.

Parameters:
- `relationships`: The relationships to add.

#### `get_entities(self)`
Get all entities in the stack.

Returns:
- List of entities.

#### `get_relationships(self)`
Get all relationships in the stack.

Returns:
- List of relationships.

#### `filter_entities(self, filter_func)`
Filter entities in the stack.

Parameters:
- `filter_func`: Filter function.

Returns:
- List of filtered entities.

#### `filter_relationships(self, filter_func)`
Filter relationships in the stack.

Parameters:
- `filter_func`: Filter function.

Returns:
- List of filtered relationships.

### StackableKnowledgeManager

Class for managing knowledge stacks.

#### `__init__(self)`
Initialize a new stackable knowledge manager.

#### `create_stack(self, name, description="")`
Create a new knowledge stack.

Parameters:
- `name`: The name of the stack.
- `description`: Optional description of the stack.

Returns:
- The created stack instance.

#### `get_stack(self, name)`
Get a stack by name.

Parameters:
- `name`: The name of the stack.

Returns:
- The stack instance.

#### `set_current_stack(self, name)`
Set the current active stack.

Parameters:
- `name`: The name of the stack to set as current.

#### `add_to_current_stack(self, entities, relationships)`
Add entities and relationships to the current stack.

Parameters:
- `entities`: The entities to add.
- `relationships`: The relationships to add.

#### `create_stack_hierarchy(self, parent_name, child_name)`
Create a parent-child relationship between stacks.

Parameters:
- `parent_name`: The name of the parent stack.
- `child_name`: The name of the child stack.

#### `get_stack_hierarchy(self, stack_name)`
Get the hierarchy information for a stack.

Parameters:
- `stack_name`: The name of the stack.

Returns:
- Dictionary with hierarchy information.

#### `get_stack_lineage(self, stack_name)`
Get the lineage information for a stack.

Parameters:
- `stack_name`: The name of the stack.

Returns:
- Dictionary with lineage information.

#### `merge_stacks(self, stack_names, target_name, merge_type="union")`
Merge multiple stacks into a new stack.

Parameters:
- `stack_names`: List of stack names to merge.
- `target_name`: Name of the target stack.
- `merge_type`: Type of merge operation ("union" or "intersection").

Returns:
- The merged stack instance.

#### `get_combined_stack(self, stack_name, include_ancestors=False, include_descendants=False)`
Get a combined view of a stack with its ancestors and/or descendants.

Parameters:
- `stack_name`: The name of the stack.
- `include_ancestors`: Whether to include ancestors.
- `include_descendants`: Whether to include descendants.

Returns:
- Dictionary with combined stack information.

#### `visualize_stack_hierarchy(self, output_path)`
Visualize the stack hierarchy.

Parameters:
- `output_path`: Path to save the visualization.

Returns:
- The path to the visualization file.

#### `save_state(self, path)`
Save the current state of the manager.

Parameters:
- `path`: Path to save the state.

#### `load_state(self, path)`
Load a saved state into the manager.

Parameters:
- `path`: Path to the saved state.
