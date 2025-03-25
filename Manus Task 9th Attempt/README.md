# Enhanced Knowledge Graph Reduction

This project provides an improved implementation of knowledge graph reduction techniques, building upon the original KnowledgeReduce repository. The enhanced version incorporates advanced NLP and machine learning approaches to create more effective knowledge reduction.

## Key Improvements

The enhanced knowledge reduction function includes several significant improvements over the original implementation:

1. **Transformer-Based Semantic Similarity**: Using sentence transformers to better capture semantic relationships between facts, replacing the simpler string-based similarity measures.

2. **Hierarchical Clustering**: Implementing hierarchical clustering to group similar facts and select the most representative ones, providing a more nuanced approach to redundancy reduction.

3. **Entity Disambiguation**: Adding entity disambiguation capabilities to identify when different terms refer to the same entity, further reducing redundancy.

4. **Fact Importance Scoring**: Developing a sophisticated scoring mechanism that considers semantic richness, centrality in the knowledge graph, and fact length to prioritize the most valuable information.

5. **Knowledge Graph Embeddings**: Representing entities and relations in a low-dimensional vector space for more effective similarity comparisons.

## Components

- `knowledge_reduce.py`: The core module containing the enhanced knowledge reduction implementation
- `CivicHonorsKGv19.ipynb`: A Jupyter notebook demonstrating the improved knowledge reduction techniques

## Usage

The enhanced knowledge reduction can be used as follows:

```python
from knowledge_reduce import EnhancedKnowledgeReduce

# Create an instance with custom parameters
reducer = EnhancedKnowledgeReduce(
    transformer_model='all-MiniLM-L6-v2',
    similarity_threshold=0.85,
    short_fact_threshold=50
)

# Apply to a knowledge graph
reduced_kg = reducer.reduce_knowledge_graph(knowledge_graph)
```

## Requirements

- Python 3.6+
- sentence-transformers
- spaCy (with en_core_web_md model)
- scikit-learn
- networkx
- numpy

## Comparison with Original Implementation

The original implementation in CivicHonorsKGv18.ipynb used:
- Basic duplicate removal using exact string matching
- Simple similarity comparison using difflib's SequenceMatcher
- Basic spaCy processing for NLP tasks

The enhanced implementation provides:
- More sophisticated semantic understanding through transformer models
- Better clustering of related facts through hierarchical methods
- Improved entity handling through disambiguation
- More nuanced fact prioritization through multi-factor importance scoring

These improvements result in a more effective knowledge reduction process that preserves the most important information while significantly reducing redundancy.
