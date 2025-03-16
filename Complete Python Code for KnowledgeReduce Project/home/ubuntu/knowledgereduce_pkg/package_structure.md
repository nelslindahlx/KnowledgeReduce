# KnowledgeReduce Package Structure

## Package Layout
knowledgereduce_pkg/
├── knowledgereduce/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── core.py
│   ├── serialization/
│   │   ├── __init__.py
│   │   └── serialization.py
│   ├── visualization/
│   │   ├── __init__.py
│   │   └── visualization.py
│   ├── analysis/
│   │   ├── __init__.py
│   │   └── analysis.py
│   ├── query/
│   │   ├── __init__.py
│   │   └── query.py
│   └── integration.py
├── tests/
│   ├── core/
│   │   └── test_core.py
│   ├── serialization/
│   │   └── test_serialization.py
│   ├── visualization/
│   │   └── test_visualization.py
│   ├── analysis/
│   │   └── test_analysis.py
│   ├── query/
│   │   └── test_query.py
│   └── integration/
│       └── test_integration.py
├── docs/
│   ├── api_reference.md
│   ├── user_guide.md
│   └── tutorials.md
├── examples/
│   ├── simple_knowledge_graph.py
│   ├── stackable_knowledge_graph.py
│   ├── analysis_example.py
│   └── query_example.py
├── setup.py
├── README.md
├── LICENSE
└── MANIFEST.in
