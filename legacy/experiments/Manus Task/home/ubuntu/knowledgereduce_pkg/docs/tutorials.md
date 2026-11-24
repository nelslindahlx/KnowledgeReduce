"""
Tutorials for the KnowledgeReduce Framework

This document provides step-by-step tutorials for common tasks with the KnowledgeReduce framework.
"""

# Tutorial 1: Building a Simple Knowledge Graph

In this tutorial, we'll build a simple knowledge graph about countries and capitals.

```python
from knowledgereduce import KnowledgeReduceFramework, ReliabilityRating

# Create a new framework instance
framework = KnowledgeReduceFramework()

# Add facts about countries and capitals
framework.add_fact(
    fact_id="geo_france_capital",
    fact_statement="Paris is the capital of France",
    category="Geography",
    tags=["paris", "france", "capital"],
    reliability_rating=ReliabilityRating.VERIFIED
)

framework.add_fact(
    fact_id="geo_germany_capital",
    fact_statement="Berlin is the capital of Germany",
    category="Geography",
    tags=["berlin", "germany", "capital"],
    reliability_rating=ReliabilityRating.VERIFIED
)

framework.add_fact(
    fact_id="geo_italy_capital",
    fact_statement="Rome is the capital of Italy",
    category="Geography",
    tags=["rome", "italy", "capital"],
    reliability_rating=ReliabilityRating.VERIFIED
)

# Add facts about countries
framework.add_fact(
    fact_id="geo_france_location",
    fact_statement="France is located in Western Europe",
    category="Geography",
    tags=["france", "europe", "location"],
    reliability_rating=ReliabilityRating.VERIFIED
)

framework.add_fact(
    fact_id="geo_germany_location",
    fact_statement="Germany is located in Central Europe",
    category="Geography",
    tags=["germany", "europe", "location"],
    reliability_rating=ReliabilityRating.VERIFIED
)

framework.add_fact(
    fact_id="geo_italy_location",
    fact_statement="Italy is located in Southern Europe",
    category="Geography",
    tags=["italy", "europe", "location"],
    reliability_rating=ReliabilityRating.VERIFIED
)

# Add relationships between capitals and countries
framework.add_relationship(
    "geo_france_capital", "geo_france_location", "related_to", weight=1.0
)

framework.add_relationship(
    "geo_germany_capital", "geo_germany_location", "related_to", weight=1.0
)

framework.add_relationship(
    "geo_italy_capital", "geo_italy_location", "related_to", weight=1.0
)

# Add relationships between neighboring countries
framework.add_relationship(
    "geo_france_location", "geo_germany_location", "neighbors", weight=0.8
)

framework.add_relationship(
    "geo_france_location", "geo_italy_location", "neighbors", weight=0.8
)

# Save the knowledge graph
framework.save_to_file("countries_graph.json")

# Visualize the graph
fig = framework.visualize(show_labels=True)
fig.savefig("countries_graph.png")

# Query the graph
print("Facts about capitals:")
results = framework.query().filter_by_tag("capital").execute()
for fact_id, fact_data in results:
    print(f"- {fact_data['fact_statement']}")

print("\nFacts about France:")
results = framework.query().filter_by_tag("france").execute()
for fact_id, fact_data in results:
    print(f"- {fact_data['fact_statement']}")

print("\nNeighboring countries:")
results = framework.get_with_relationship("neighbors")
for source_id in results["sources"]:
    source = framework.get_fact(source_id)
    print(f"- {source['fact_statement']}")
```

# Tutorial 2: Building a Stackable Knowledge Graph

In this tutorial, we'll build a stackable knowledge graph with multiple layers of knowledge.

```python
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

# Add a historical layer with historical information
framework.add_layer("historical", parent_layer="base")

framework.add_fact(
    fact_id="astronomy_moon_landing",
    fact_statement="Apollo 11 was the first manned mission to land on the Moon in 1969",
    category="History",
    tags=["moon", "apollo", "nasa", "1969"],
    reliability_rating=ReliabilityRating.VERIFIED,
    layer_name="historical"
)

# Add a relationship in the historical layer
framework.add_relationship(
    "astronomy_moon", "astronomy_moon_landing", "related_to", weight=0.8, layer_name="historical"
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

print("\nMerged graph fact about Earth (should show scientific layer version):")
merged_graph = framework.get_merged_graph()
fact = merged_graph.get_fact("astronomy_earth")
print(f"- {fact['fact_statement']}")

# Query specific layers
print("\nFacts in the historical layer:")
results = framework.query(layer_name="historical").execute()
for fact_id, fact_data in results:
    print(f"- {fact_data['fact_statement']}")

# Visualize specific layers
fig = framework.visualize(layer_name="scientific", show_labels=True)
fig.savefig("scientific_layer.png")

fig = framework.visualize(layer_name="historical", show_labels=True)
fig.savefig("historical_layer.png")

# Visualize the merged graph
fig = framework.visualize(show_labels=True)
fig.savefig("merged_graph.png")
```

# Tutorial 3: Analyzing a Knowledge Graph

In this tutorial, we'll analyze a knowledge graph to extract insights.

```python
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

# Add facts about solar energy
framework.add_fact(
    fact_id="solar_photovoltaic",
    fact_statement="Photovoltaic cells convert sunlight directly into electricity",
    category="Solar",
    tags=["solar", "photovoltaic", "electricity"],
    reliability_rating=ReliabilityRating.VERIFIED
)

framework.add_fact(
    fact_id="solar_thermal",
    fact_statement="Solar thermal systems use sunlight to heat water or air",
    category="Solar",
    tags=["solar", "thermal", "heat"],
    reliability_rating=ReliabilityRating.VERIFIED
)

framework.add_fact(
    fact_id="solar_csp",
    fact_statement="Concentrated solar power systems use mirrors to focus sunlight onto receivers",
    category="Solar",
    tags=["solar", "concentrated", "mirrors"],
    reliability_rating=ReliabilityRating.VERIFIED
)

# Add facts about wind energy
framework.add_fact(
    fact_id="wind_onshore",
    fact_statement="Onshore wind farms are built on land",
    category="Wind",
    tags=["wind", "onshore", "land"],
    reliability_rating=ReliabilityRating.VERIFIED
)

framework.add_fact(
    fact_id="wind_offshore",
    fact_statement="Offshore wind farms are built in bodies of water",
    category="Wind",
    tags=["wind", "offshore", "water"],
    reliability_rating=ReliabilityRating.VERIFIED
)

# Add relationships
framework.add_relationship("energy_solar", "solar_photovoltaic", "includes", weight=1.0)
framework.add_relationship("energy_solar", "solar_thermal", "includes", weight=1.0)
framework.add_relationship("energy_solar", "solar_csp", "includes", weight=1.0)
framework.add_relationship("energy_wind", "wind_onshore", "includes", weight=1.0)
framework.add_relationship("energy_wind", "wind_offshore", "includes", weight=1.0)
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
print("\nPath from 'energy_biomass' to 'solar_photovoltaic':")
path = framework.find_path("energy_biomass", "solar_photovoltaic")
for fact_id in path:
    fact = framework.get_fact(fact_id)
    print(f"- {fact_id}: {fact['fact_statement']}")

# 6. Extract keywords
print("\nKeywords from 'energy_solar':")
keywords = framework.extract_keywords("energy_solar")
print(keywords)

# 7. Visualize the graph
fig = framework.visualize(show_labels=True)
fig.savefig("renewable_energy_graph.png")

# 8. Visualize a fact neighborhood
fig = framework.visualize_fact("energy_solar", depth=2, show_labels=True)
fig.savefig("solar_energy_neighborhood.png")

# 9. Visualize statistics
fig = framework.visualize_statistics()
fig.savefig("renewable_energy_statistics.png")
```

# Tutorial 4: Creating a Knowledge Graph from Text

In this tutorial, we'll create a knowledge graph from text.

```python
from knowledgereduce import KnowledgeReduceFramework

# Create a new framework instance
framework = KnowledgeReduceFramework()

# Sample text about artificial intelligence
text = """
Artificial intelligence (AI) is intelligence demonstrated by machines, as opposed to natural intelligence displayed by animals including humans. 
AI research has been defined as the field of study of intelligent agents, which refers to any system that perceives its environment and takes actions that maximize its chance of achieving its goals.

The term "artificial intelligence" was first used in 1956 during the Dartmouth Conference. The field has gone through several cycles of optimism followed by disappointment and loss of funding, followed by new approaches, success, and renewed funding.

Machine learning is a subset of AI that focuses on the development of algorithms that can access data and use it to learn for themselves. Deep learning is a subset of machine learning that uses neural networks with many layers.

Natural language processing (NLP) is a field of AI that focuses on the interaction between computers and humans through natural language. The ultimate goal of NLP is to enable computers to understand, interpret, and generate human language in a valuable way.

Computer vision is a field of AI that focuses on enabling computers to see, identify, and process images in the same way that human vision does. It involves the development of algorithms to accomplish automatic visual understanding.
"""

# Create a knowledge graph from the text
framework.create_from_text(text)

# Save the knowledge graph
framework.save_to_file("ai_graph.json")

# Explore the graph

# 1. View all facts
print("All facts:")
results = framework.query().execute()
for fact_id, fact_data in results:
    print(f"- {fact_id}: {fact_data['fact_statement']}")

# 2. Find facts about machine learning
print("\nFacts about machine learning:")
results = framework.find_by_pattern(r"machine learning", field="fact_statement")
for fact_id in results:
    fact = framework.get_fact(fact_id)
    print(f"- {fact_id}: {fact['fact_statement']}")

# 3. Find central facts
print("\nCentral facts:")
central_facts = framework.get_central_facts(top_n=3)
for fact_id, score in central_facts:
    fact = framework.get_fact(fact_id)
    print(f"- {fact_id} (score: {score:.2f}): {fact['fact_statement']}")

# 4. Visualize the graph
fig = framework.visualize(show_labels=True)
fig.savefig("ai_graph.png")

# 5. Extract keywords from each fact
print("\nKeywords from facts:")
for fact_id, _ in results:
    keywords = framework.extract_keywords(fact_id, num_keywords<response clipped><NOTE>To save on context only part of this file has been shown to you. You should retry this tool after you have searched inside the file with `grep -n` in order to find the line numbers of what you are looking for.</NOTE>