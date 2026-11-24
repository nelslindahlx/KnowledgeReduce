"""
Stackable Knowledge Graph Example

This example demonstrates how to create a stackable knowledge graph with multiple layers,
add facts and relationships to different layers, and work with the merged view.
"""

from knowledgereduce import KnowledgeReduceFramework, ReliabilityRating

# Create a stackable knowledge graph
framework = KnowledgeReduceFramework(use_stackable=True)

# Add facts to the base layer (widely accepted facts)
framework.add_fact(
    fact_id="astronomy_earth",
    fact_statement="Earth is the third planet from the Sun",
    category="Astronomy",
    tags=["earth", "planet", "solar system"],
    reliability_rating=ReliabilityRating.VERIFIED,
    layer_name="base"
)

framework.add_fact(
    fact_id="astronomy_moon",
    fact_statement="The Moon is Earth's only natural satellite",
    category="Astronomy",
    tags=["moon", "earth", "satellite"],
    reliability_rating=ReliabilityRating.VERIFIED,
    layer_name="base"
)

# Add a relationship in the base layer
framework.add_relationship(
    "astronomy_earth", "astronomy_moon", "has_satellite", weight=1.0, layer_name="base"
)

# Add a scientific layer with more detailed information
framework.add_layer("scientific", parent_layer="base")

framework.add_fact(
    fact_id="astronomy_earth",  # Same ID as in base layer (override)
    fact_statement="Earth is the third planet from the Sun with a mean radius of 6,371 km",
    category="Astronomy",
    tags=["earth", "planet", "solar system", "radius"],
    reliability_rating=ReliabilityRating.VERIFIED,
    layer_name="scientific"
)

framework.add_fact(
    fact_id="astronomy_moon_distance",
    fact_statement="The Moon orbits Earth at an average distance of 384,400 km",
    category="Astronomy",
    tags=["moon", "earth", "orbit", "distance"],
    reliability_rating=ReliabilityRating.VERIFIED,
    layer_name="scientific"
)

# Add a relationship in the scientific layer
framework.add_relationship(
    "astronomy_earth", "astronomy_moon_distance", "related_to", weight=0.9, layer_name="scientific"
)

# Save the stackable knowledge graph
framework.save_to_file("astronomy_graph")

# Get and print facts from different layers
print("Base layer fact about Earth:")
fact = framework.get_fact("astronomy_earth", layer_name="base")
print(f"- {fact['fact_statement']}")

print("\nScientific layer fact about Earth (override):")
fact = framework.get_fact("astronomy_earth", layer_name="scientific")
print(f"- {fact['fact_statement']}")

# Get the merged graph
merged_graph = framework.get_merged_graph()

print("\nMerged graph fact about Earth (should show scientific layer version):")
fact = merged_graph.get_fact("astronomy_earth")
print(f"- {fact['fact_statement']}")

# Query specific layers
print("\nFacts in the scientific layer:")
results = framework.query(layer_name="scientific").execute()
for fact_id, fact_data in results:
    print(f"- {fact_id}: {fact_data['fact_statement']}")

# Visualize specific layers
framework.visualize(layer_name="base", show_labels=True)
framework.visualize(layer_name="scientific", show_labels=True)

# Visualize the merged graph
framework.visualize(show_labels=True)
