"""
Analysis Example

This example demonstrates how to analyze a knowledge graph to extract insights.
"""

from knowledgereduce import KnowledgeReduceFramework, ReliabilityRating

# Create a knowledge graph about a topic (e.g., renewable energy)
framework = KnowledgeReduceFramework()

# Add facts about renewable energy
framework.add_fact(
    fact_id="energy_solar",
    fact_statement="Solar energy is a renewable energy source that harnesses power from the sun",
    category="Energy",
    tags=["solar", "renewable", "sun"],
    reliability_rating=ReliabilityRating.VERIFIED
)

framework.add_fact(
    fact_id="energy_wind",
    fact_statement="Wind energy is a renewable energy source that harnesses power from wind",
    category="Energy",
    tags=["wind", "renewable", "turbine"],
    reliability_rating=ReliabilityRating.VERIFIED
)

framework.add_fact(
    fact_id="energy_hydro",
    fact_statement="Hydroelectric power is a renewable energy source that harnesses energy from flowing water",
    category="Energy",
    tags=["hydro", "renewable", "water", "dam"],
    reliability_rating=ReliabilityRating.VERIFIED
)

framework.add_fact(
    fact_id="energy_geothermal",
    fact_statement="Geothermal energy is a renewable energy source that harnesses heat from the Earth",
    category="Energy",
    tags=["geothermal", "renewable", "heat", "earth"],
    reliability_rating=ReliabilityRating.VERIFIED
)

framework.add_fact(
    fact_id="energy_biomass",
    fact_statement="Biomass energy is a renewable energy source derived from organic materials",
    category="Energy",
    tags=["biomass", "renewable", "organic"],
    reliability_rating=ReliabilityRating.VERIFIED
)

# Add relationships
framework.add_relationship("energy_solar", "energy_wind", "related_to", weight=0.5)
framework.add_relationship("energy_wind", "energy_hydro", "related_to", weight=0.5)
framework.add_relationship("energy_hydro", "energy_geothermal", "related_to", weight=0.3)
framework.add_relationship("energy_biomass", "energy_solar", "related_to", weight=0.2)

# Save the knowledge graph
framework.save_to_file("renewable_energy_graph.json")

# Analyze the graph

# 1. Find central facts
print("Central facts (by betweenness centrality):")
central_facts = framework.get_central_facts(method="betweenness")
for fact_id, score in central_facts[:3]:
    fact = framework.get_fact(fact_id)
    print(f"- {fact_id} (score: {score:.2f}): {fact['fact_statement']}")

print("\nCentral facts (by degree centrality):")
central_facts = framework.get_central_facts(method="degree")
for fact_id, score in central_facts[:3]:
    fact = framework.get_fact(fact_id)
    print(f"- {fact_id} (score: {score:.2f}): {fact['fact_statement']}")

# 2. Find fact clusters
print("\nFact clusters:")
clusters = framework.get_fact_clusters(min_cluster_size=2)
for i, cluster in enumerate(clusters):
    print(f"Cluster {i+1}:")
    for fact_id in cluster:
        fact = framework.get_fact(fact_id)
        print(f"  - {fact_id}: {fact['fact_statement']}")

# 3. Find similar facts
print("\nFacts similar to 'energy_solar':")
similar_facts = framework.find_similar_facts("energy_solar", threshold=0.2)
for fact_id, score in similar_facts:
    if fact_id != "energy_solar":  # Skip the fact itself
        fact = framework.get_fact(fact_id)
        print(f"- {fact_id} (score: {score:.2f}): {fact['fact_statement']}")

# 4. Analyze categories
print("\nCategory analysis:")
category_stats = framework.analyze_categories()
print(f"Number of categories: {category_stats['num_categories']}")
print("Category counts:")
for category, count in category_stats["category_counts"].items():
    print(f"- {category}: {count}")

# 5. Find paths between facts
print("\nPath from 'energy_biomass' to 'energy_hydro':")
path = framework.find_path("energy_biomass", "energy_hydro")
for fact_id in path:
    fact = framework.get_fact(fact_id)
    print(f"- {fact_id}: {fact['fact_statement']}")

# 6. Visualize the graph
framework.visualize(show_labels=True)

# 7. Visualize statistics
framework.visualize_statistics()
