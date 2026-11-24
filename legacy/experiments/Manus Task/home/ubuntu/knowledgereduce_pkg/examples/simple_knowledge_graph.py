"""
Simple Knowledge Graph Example

This example demonstrates how to create a basic knowledge graph,
add facts and relationships, and perform simple operations.
"""

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

framework.add_fact(
    fact_id="fact3",
    fact_statement="The Eiffel Tower is in Paris",
    category="Landmarks",
    tags=["paris", "eiffel tower", "landmark"],
    reliability_rating=ReliabilityRating.VERIFIED
)

# Add relationships
framework.add_relationship("fact1", "fact2", "related_to", weight=0.9)
framework.add_relationship("fact1", "fact3", "related_to", weight=0.8)

# Save the knowledge graph
framework.save_to_file("geography_graph.json")

# Get a fact
fact1 = framework.get_fact("fact1")
print(f"Fact 1: {fact1['fact_statement']}")

# Query the graph
print("\nFacts about Paris:")
results = framework.query().filter_by_tag("paris").execute()
for fact_id, fact_data in results:
    print(f"- {fact_id}: {fact_data['fact_statement']}")

# Get related facts
print("\nFacts related to fact1:")
related_facts = framework.get_related("fact1")
for fact_id in related_facts:
    fact = framework.get_fact(fact_id)
    print(f"- {fact_id}: {fact['fact_statement']}")

# Visualize the graph
framework.visualize(show_labels=True)
