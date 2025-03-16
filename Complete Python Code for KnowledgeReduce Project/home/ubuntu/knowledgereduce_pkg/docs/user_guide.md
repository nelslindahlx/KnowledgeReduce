"""
User Guide for the KnowledgeReduce Framework

This document provides a comprehensive guide to using the KnowledgeReduce framework,
with examples and best practices.
"""

# Introduction

KnowledgeReduce is a Python framework for building stackable knowledge graphs inspired by the MapReduce paradigm. It provides a comprehensive set of tools for creating, managing, analyzing, and visualizing knowledge graphs.

This guide will walk you through the main features of the framework and provide examples of how to use them.

# Installation

You can install KnowledgeReduce using pip:

```bash
pip install knowledgereduce
```

# Basic Usage

## Creating a Knowledge Graph

To create a knowledge graph, you first need to create a `KnowledgeReduceFramework` instance:

```python
from knowledgereduce import KnowledgeReduceFramework, ReliabilityRating

# Create a new framework instance
framework = KnowledgeReduceFramework()
```

Then you can add facts to the knowledge graph:

```python
# Add facts
framework.add_fact(
    fact_id="fact1",
    fact_statement="Paris is the capital of France",
    category="Geography",
    tags=["paris", "france", "capital"],
    reliability_rating=ReliabilityRating.VERIFIED
)

framework.add_fact(
    fact_id="fact2",
    fact_statement="France is a country in Europe",
    category="Geography",
    tags=["france", "europe", "country"],
    reliability_rating=ReliabilityRating.VERIFIED
)

framework.add_fact(
    fact_id="fact3",
    fact_statement="The Eiffel Tower is in Paris",
    category="Landmarks",
    tags=["paris", "eiffel tower", "landmark"],
    reliability_rating=ReliabilityRating.VERIFIED
)
```

You can also add relationships between facts:

```python
# Add relationships
framework.add_relationship("fact1", "fact2", "related_to", weight=0.9)
framework.add_relationship("fact1", "fact3", "related_to", weight=0.8)
```

## Saving and Loading

You can save your knowledge graph to a file and load it later:

```python
# Save to JSON
framework.save_to_file("geography_graph.json")

# Load from JSON
new_framework = KnowledgeReduceFramework()
new_framework.load_from_file("geography_graph.json")
```

KnowledgeReduce supports multiple file formats:

```python
# Save to GEXF
framework.save_to_file("geography_graph.gexf", format="gexf")

# Save to GraphML
framework.save_to_file("geography_graph.graphml", format="graphml")
```

For large knowledge graphs, you can use sharding to split the graph into multiple files:

```python
# Save to sharded JSON (100 nodes per shard)
framework.save_to_file("geography_graph.json", shard_size=100)
```

## Querying

KnowledgeReduce provides a flexible query interface for retrieving facts:

```python
# Create a query
query = framework.query()

# Filter by category
results = query.filter_by_category("Geography").execute()
for fact_id, fact_data in results:
    print(f"{fact_id}: {fact_data['fact_statement']}")

# Filter by tag
results = query.filter_by_tag("paris").execute()
for fact_id, fact_data in results:
    print(f"{fact_id}: {fact_data['fact_statement']}")

# Chain filters
results = query.filter_by_category("Geography").filter_by_tag("france").execute()
for fact_id, fact_data in results:
    print(f"{fact_id}: {fact_data['fact_statement']}")

# Sort and limit results
results = query.sort_by("usage_count", reverse=True).limit(5).execute()
for fact_id, fact_data in results:
    print(f"{fact_id}: {fact_data['fact_statement']}")
```

You can also use specialized query functions:

```python
# Find facts by pattern
results = framework.find_by_pattern(r"capital of \w+")
for fact_id in results:
    fact = framework.get_fact(fact_id)
    print(f"{fact_id}: {fact['fact_statement']}")

# Get facts with a specific relationship
results = framework.get_with_relationship("related_to")
print("Sources:", results["sources"])
print("Targets:", results["targets"])

# Get related facts
related_facts = framework.get_related("fact1")
for fact_id in related_facts:
    fact = framework.get_fact(fact_id)
    print(f"{fact_id}: {fact['fact_statement']}")
```

## Analysis

KnowledgeReduce provides various analysis functions:

```python
# Get central facts
central_facts = framework.get_central_facts(top_n=5)
for fact_id, score in central_facts:
    fact = framework.get_fact(fact_id)
    print(f"{fact_id} (score: {score:.2f}): {fact['fact_statement']}")

# Get fact clusters
clusters = framework.get_fact_clusters()
for i, cluster in enumerate(clusters):
    print(f"Cluster {i+1}:")
    for fact_id in cluster:
        fact = framework.get_fact(fact_id)
        print(f"  {fact_id}: {fact['fact_statement']}")

# Calculate similarity between facts
similarity = framework.calculate_similarity("fact1", "fact2")
print(f"Similarity between fact1 and fact2: {similarity:.2f}")

# Find similar facts
similar_facts = framework.find_similar_facts("fact1", threshold=0.3)
for fact_id, score in similar_facts:
    fact = framework.get_fact(fact_id)
    print(f"{fact_id} (score: {score:.2f}): {fact['fact_statement']}")

# Analyze categories
category_stats = framework.analyze_categories()
print("Categories:", category_stats["category_counts"])
print("Most common categories:", category_stats["most_common_categories"])

# Find path between facts
path = framework.find_path("fact2", "fact3")
print("Path from fact2 to fact3:")
for fact_id in path:
    fact = framework.get_fact(fact_id)
    print(f"  {fact_id}: {fact['fact_statement']}")

# Extract keywords
keywords = framework.extract_keywords("fact1")
print(f"Keywords for fact1: {keywords}")

# Analyze reliability
reliability_stats = framework.analyze_reliability()
print("Reliability counts:", reliability_stats["reliability_counts"])
print("Average reliability:", reliability_stats["avg_reliability"])

# Identify conflicts
conflicts = framework.identify_conflicts()
for source_id, target_id, score in conflicts:
    source = framework.get_fact(source_id)
    target = framework.get_fact(target_id)
    print(f"Conflict (score: {score:.2f}):")
    print(f"  {source_id}: {source['fact_statement']}")
    print(f"  {target_id}: {target['fact_statement']}")
```

## Visualization

KnowledgeReduce provides visualization functions for exploring your knowledge graph:

```python
# Visualize the graph
fig = framework.visualize(show_labels=True)
fig.savefig("graph.png")

# Visualize a specific fact and its neighborhood
fig = framework.visualize_fact("fact1", depth=2)
fig.savefig("fact1_neighborhood.png")

# Get and visualize statistics
stats = framework.get_statistics()
print("Number of nodes:", stats["num_nodes"])
print("Number of edges:", stats["num_edges"])
print("Density:", stats["density"])

fig = framework.visualize_statistics()
fig.savefig("statistics.png")
```

# Advanced Usage

## Stackable Knowledge Graphs

KnowledgeReduce supports stackable knowledge graphs, which allow you to organize knowledge in layers:

```python
# Create a stackable knowledge graph
framework = KnowledgeReduceFramework(use_stackable=True)

# Add a fact to the base layer
framework.add_fact(
    fact_id="fact1",
    fact_statement="The sky is blue",
    category="Science",
    tags=["sky", "color"],
    reliability_rating=ReliabilityRating.VERIFIED,
    layer_name="base"
)

# Add a new layer
framework.add_layer("layer1", parent_layer="base")

# Add a fact to the new layer
framework.add_fact(
    fact_id="fact2",
    fact_statement="Water boils at 100°C",
    category="Science",
    tags=["water", "temperature"],
    reliability_rating=ReliabilityRating.VERIFIED,
    layer_name="layer1"
)

# Add a relationship
framework.add_relationship(
    "fact1", "fact2", "related_to", weight=0.8, layer_name="layer1"
)

# Get a specific layer
layer = framework.get_layer("layer1")

# Get a merged view of all layers
merged_graph = framework.get_merged_graph()

# Override a fact in a higher layer
framework.add_fact(
    fact_id="fact1",
    fact_statement="The sky appears blue due to Rayleigh scattering",
    category="Science",
    tags=["sky", "color", "physics"],
    reliability_rating=ReliabilityRating.VERIFIED,
    layer_name="layer1"
)

# The merged graph will now show the overridden fact
merged_graph = framework.get_merged_graph()
fact1 = merged_graph.get_fact("fact1")
print(fact1["fact_statement"])  # "The sky appears blue due to Rayleigh scattering"
```

## Creating Knowledge Graphs from External Sources

KnowledgeReduce can create knowledge graphs from text or web pages:

```python
# Create from text
text = """
Paris is the capital of France. France is a country in Europe.
The Eiffel Tower is in Paris. Paris is known for its art and culture.
"""
framework = KnowledgeReduceFramework()
framework.create_from_text(text)

# Create from URL
framework = KnowledgeReduceFramework()
framework.create_from_url("https://en.wikipedia.org/wiki/Paris")
```

## Merging Knowledge Graphs

You can merge multiple knowledge graphs:

```python
# Create two frameworks
framework1 = KnowledgeReduceFramework()
framework1.add_fact(
    fact_id="fact1",
    fact_statement="Paris is the capital of France",
    category="Geography",
    tags=["paris", "france", "capital"],
    reliability_rating=ReliabilityRating.VERIFIED
)

framework2 = KnowledgeReduceFramework()
framework2.add_fact(
    fact_id="fact2",
    fact_statement="France is a country in Europe",
    category="Geography",
    tags=["france", "europe", "country"],
    reliability_rating=ReliabilityRating.VERIFIED
)

# Merge frameworks
framework1.merge_with(framework2)

# The merged framework contains facts from both frameworks
fact1 = framework1.get_fact("fact1")
fact2 = framework1.get_fact("fact2")
print(fact1["fact_statement"])  # "Paris is the capital of France"
print(fact2["fact_statement"])  # "France is a country in Europe"
```

# Best Practices

## Fact IDs

Fact IDs should be unique and descriptive. A good practice is to use a prefix that indicates the category or source, followed by a unique identifier:

```python
framework.add_fact(
    fact_id="geo_paris_capital",
    fact_statement="Paris is the capital of France",
    category="Geography",
    tags=["paris", "france", "capital"],
    reliability_rating=ReliabilityRating.VERIFIED
)
```

## Reliability Ratings

Use reliability ratings to indicate the confidence in a fact:

- `ReliabilityRating.VERIFIED`: Fact has been verified by multiple reliable sources
- `ReliabilityRating.LIKELY_TRUE`: Fact is likely true based on reliable sources
- `ReliabilityRating.POSSIBLY_TRUE`: Fact is possibly true but needs more verification
- `ReliabilityRating.UNVERIFIED`: Fact has not been verified
- `ReliabilityRating.DISPUTED`: Fact is disputed by reliable sources

## Relationship Types

Use consistent relationship types to make querying easier. Some common relationship types:

- `related_to`: General relationship between facts
- `part_of`: One fact is part of another
- `causes`: One fact causes another
- `contradicts`: One fact contradicts another
- `supports`: One fact supports another
- `example_of`: One fact is an example of another

## Sharding

For large knowledge graphs, use sharding to split the graph into multiple files:

```python
framework.save_to_file("large_graph.json", shard_size=1000)
```

This will create a metadata file and multiple shard files, making it easier to manage large graphs.

## Layer Organization

When using stackable knowledge graphs, organize layers logically:

- Use the base layer for fundamental, widely accepted facts
- Use higher layers for more specialized or domain-specific knowledge
- Use higher layers to override or refine facts from lower layers
- Name layers descriptively (e.g., "base", "science", "history", "user_specific")

# Conclusion

KnowledgeReduce provides a powerful framework for working with knowledge graphs. By following the examples and best practices in this guide, you can create, manage, analyze, and visualize knowledge graphs effectively.

For more detailed information about the API, see the [API Reference](api_reference.md).
