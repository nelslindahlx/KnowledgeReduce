# KnowledgeReduce Apex

A revolutionary knowledge graph framework with advanced AI integration, multi-modal data support, and federated collaboration capabilities.

## Overview

KnowledgeReduce Apex is a comprehensive Python framework for creating, managing, and analyzing knowledge graphs with reliability ratings. It represents the pinnacle of knowledge graph technology, combining traditional graph-based knowledge representation with cutting-edge AI capabilities, multi-modal data support, and collaborative features.

## Key Features

### Core Capabilities
- **Reliability-rated Facts**: Associate confidence levels with each piece of knowledge
- **Flexible Knowledge Structure**: Store and connect facts with rich metadata
- **Visualization Tools**: Visualize knowledge graphs with customizable layouts
- **Import/Export**: Support for various data formats including JSON, CSV, and GraphML

### Performance Optimizations
- **LRU Caching**: 10-100x faster repeated queries
- **Batch Operations**: Efficient data manipulation
- **Change Tracking**: Automatic saving and versioning
- **Memory Optimization**: Efficient handling of large knowledge graphs

### Scalability
- **Distributed Sharding**: Partition knowledge across multiple shards
- **Cross-shard Queries**: Seamless querying across partitions
- **Shard Balancing**: Automatic load balancing between shards
- **Millions of Facts**: Efficiently handle massive knowledge bases

### Advanced Analytics
- **Centrality Analysis**: Identify key facts in the knowledge graph
- **Community Detection**: Discover clusters of related facts
- **Contradiction Finding**: Identify conflicting information
- **Missing Link Prediction**: Suggest potential connections

### Vector Capabilities
- **Semantic Search**: Find facts based on meaning, not just keywords
- **Vector Embeddings**: Convert facts to vector representations
- **Similarity Matching**: Find semantically similar facts
- **Clustering**: Group facts by semantic similarity

### Real-time Features
- **Event-driven Updates**: React to changes in real-time
- **Streaming Integration**: Connect to data streams
- **Change Propagation**: Automatically update dependent facts
- **Event History**: Track all changes with complete history

### Blockchain Verification
- **Immutable History**: Cryptographically secure fact history
- **Distributed Consensus**: Verify facts across multiple nodes
- **Tamper-proof Audit**: Complete audit trail for all facts
- **Verification Proofs**: Cryptographic proof of fact provenance

### AI Integration (NEW)
- **LLM Knowledge Extraction**: Extract structured knowledge from text
- **Question Answering**: Answer natural language questions using the knowledge graph
- **Hypothesis Generation**: Generate and test hypotheses based on existing knowledge
- **Natural Language Interface**: Query and update the knowledge graph using natural language

### Multi-modal Support (NEW)
- **Image Integration**: Associate images with facts in the knowledge graph
- **Audio Support**: Include audio recordings as knowledge elements
- **Video Content**: Incorporate video data into the knowledge structure
- **Media Search**: Search across all modalities of knowledge

### Federated Collaboration (NEW)
- **Multi-user Editing**: Collaborative knowledge graph editing
- **Permission Management**: Fine-grained access control
- **Change Synchronization**: Sync changes across distributed nodes
- **Conflict Resolution**: Automatically resolve editing conflicts

## Installation

```bash
pip install knowledgereduce
```

## Quick Start

```python
from knowledge_graph_pkg import KnowledgeGraph, ReliabilityRating

# Create a basic knowledge graph
kg = KnowledgeGraph()

# Add a fact with reliability rating
kg.add_fact(
    fact_id="fact_001",
    fact_statement="The Earth orbits the Sun",
    category="Astronomy",
    tags=["earth", "sun", "orbit"],
    reliability_rating=ReliabilityRating.VERIFIED
)
```

## Advanced Usage

### AI Integration

```python
from knowledge_graph_pkg import KnowledgeGraph, AIKnowledgeGraph

# Create a knowledge graph
kg = KnowledgeGraph()

# Enhance with AI capabilities
ai_kg = AIKnowledgeGraph(kg)

# Extract knowledge from text
fact_ids = ai_kg.extract_knowledge_from_text(
    text="Mars has two moons, Phobos and Deimos.",
    source_id="astronomy_text"
)

# Answer questions using the knowledge graph
answer = ai_kg.answer_question("How many moons does Mars have?")
print(answer['answer'])
```

### Multi-modal Knowledge

```python
from knowledge_graph_pkg import KnowledgeGraph, MultiModalKnowledgeGraph

# Create a knowledge graph
kg = KnowledgeGraph()

# Enhance with multi-modal capabilities
mm_kg = MultiModalKnowledgeGraph(kg)

# Add an image fact
image_fact = mm_kg.add_image_fact(
    fact_id="image_001",
    image_data=open("solar_system.jpg", "rb"),
    caption="Diagram of the solar system",
    category="Astronomy",
    tags=["solar system", "diagram"]
)

# Get the path to the media file
media_path = mm_kg.get_media_path("image_001")
```

### Federated Collaboration

```python
from knowledge_graph_pkg import KnowledgeGraph, FederatedKnowledgeGraph

# Create a knowledge graph
kg = KnowledgeGraph()

# Enhance with federation capabilities
fed_kg = FederatedKnowledgeGraph(kg, node_id="node_001")

# Register users
admin = fed_kg.register_user(
    user_id="user_001",
    username="Admin User",
    role="admin"
)

# Add a fact collaboratively
fact = fed_kg.add_fact_collaborative(
    user_id="user_001",
    fact_id="collab_001",
    fact_statement="Neptune has 14 known moons",
    category="Astronomy",
    tags=["neptune", "moons"]
)

# Export federation state
fed_kg.export_federation_state("federation_state.json")
```

## Examples

See the `examples` directory for comprehensive examples:

- `basic_usage.py`: Simple knowledge graph operations
- `advanced_usage.py`: Advanced features demonstration
- `enhanced_features.py`: Performance and scalability features
- `ultimate_features.py`: Vector, streaming, and blockchain capabilities
- `apex_features.py`: AI, multi-modal, and federated collaboration

## Documentation

For complete documentation, visit [https://knowledgereduce.readthedocs.io/](https://knowledgereduce.readthedocs.io/)

## License

MIT License

## Citation

If you use KnowledgeReduce in your research, please cite:

```
@software{knowledgereduce,
  author = {Lindahl, Nels},
  title = {KnowledgeReduce: A Comprehensive Knowledge Graph Framework},
  url = {https://github.com/nelslindahlx/KnowledgeReduce},
  version = {3.0.0},
  year = {2025},
}
```
