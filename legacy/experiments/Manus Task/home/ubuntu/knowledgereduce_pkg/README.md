# KnowledgeReduce

A Python framework for building stackable knowledge graphs inspired by the MapReduce paradigm.

## Overview

KnowledgeReduce is a conceptual framework inspired by MapReduce but specifically designed for knowledge graph construction. It adapts the Map-Reduce paradigm with specialized phases for knowledge graph creation:

- The mapping phase extracts entities and relationships from raw data
- The reducing phase aggregates information and resolves conflicts
- The framework includes data ingestion, preprocessing, entity recognition, and graph synthesis

This package provides a comprehensive implementation of the KnowledgeReduce framework with support for stackable knowledge sets, advanced analysis capabilities, and flexible querying.

## Installation

```bash
pip install knowledgereduce
```

## Quick Start

```python
from knowledgereduce import KnowledgeReduceFramework, ReliabilityRating

# Create a new framework instance
framework = KnowledgeReduceFramework()

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

# Add a relationship
framework.add_relationship("fact1", "fact2", "related_to", weight=0.9)

# Save the knowledge graph
framework.save_to_file("geography_graph.json")

# Analyze the graph
central_facts = framework.get_central_facts()
print(f"Most central fact: {central_facts[0][0]}")

# Query the graph
results = framework.query().filter_by_tag("france").execute()
for fact_id, fact_data in results:
    print(f"{fact_id}: {fact_data['fact_statement']}")

# Visualize the graph
framework.visualize(show_labels=True)
```

## Features

- **Core Knowledge Graph**: Create, manage, and manipulate knowledge graphs with facts and relationships
- **Stackable Knowledge Sets**: Layer knowledge graphs with inheritance and overrides
- **Advanced Serialization**: Import/export to JSON, GEXF, and GraphML with sharding support for large graphs
- **Visualization**: Visualize graphs, fact neighborhoods, and statistics
- **Analysis**: Identify central facts, clusters, similarities, and conflicts
- **Flexible Querying**: Query facts by various criteria with a fluent interface
- **Integration**: High-level API that ties everything together

## Documentation

For detailed documentation, see the [API Reference](https://example.com/knowledgereduce/api) and [User Guide](https://example.com/knowledgereduce/guide).

## Examples

See the [examples directory](https://github.com/nelslindahlx/KnowledgeReduce/tree/main/examples) for more examples of how to use KnowledgeReduce.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Citation

If you use KnowledgeReduce in your research, please cite:

```
@article{lindahl2023knowledgereduce,
  title={KnowledgeReduce: Building Stackable Knowledge},
  author={Lindahl, Nels},
  journal={arXiv preprint},
  year={2023}
}
```
