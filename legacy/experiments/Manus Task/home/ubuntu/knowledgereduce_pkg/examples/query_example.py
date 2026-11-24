"""
Query Example

This example demonstrates how to query a knowledge graph in various ways.
"""

from knowledgereduce import KnowledgeReduceFramework, ReliabilityRating

# Create a knowledge graph about books
framework = KnowledgeReduceFramework()

# Add facts about books
framework.add_fact(
    fact_id="book_1984",
    fact_statement="1984 is a dystopian novel by George Orwell published in 1949",
    category="Fiction",
    tags=["1984", "orwell", "dystopian", "novel"],
    reliability_rating=ReliabilityRating.VERIFIED,
    author_creator="George Orwell",
    publication_date="1949"
)

framework.add_fact(
    fact_id="book_brave_new_world",
    fact_statement="Brave New World is a dystopian novel by Aldous Huxley published in 1932",
    category="Fiction",
    tags=["brave new world", "huxley", "dystopian", "novel"],
    reliability_rating=ReliabilityRating.VERIFIED,
    author_creator="Aldous Huxley",
    publication_date="1932"
)

framework.add_fact(
    fact_id="book_fahrenheit_451",
    fact_statement="Fahrenheit 451 is a dystopian novel by Ray Bradbury published in 1953",
    category="Fiction",
    tags=["fahrenheit 451", "bradbury", "dystopian", "novel"],
    reliability_rating=ReliabilityRating.VERIFIED,
    author_creator="Ray Bradbury",
    publication_date="1953"
)

framework.add_fact(
    fact_id="book_lord_of_the_rings",
    fact_statement="The Lord of the Rings is a fantasy novel by J.R.R. Tolkien published in 1954-1955",
    category="Fiction",
    tags=["lord of the rings", "tolkien", "fantasy", "novel"],
    reliability_rating=ReliabilityRating.VERIFIED,
    author_creator="J.R.R. Tolkien",
    publication_date="1954-1955"
)

framework.add_fact(
    fact_id="book_harry_potter",
    fact_statement="Harry Potter is a fantasy novel series by J.K. Rowling published from 1997 to 2007",
    category="Fiction",
    tags=["harry potter", "rowling", "fantasy", "novel", "series"],
    reliability_rating=ReliabilityRating.VERIFIED,
    author_creator="J.K. Rowling",
    publication_date="1997-2007"
)

# Add relationships
framework.add_relationship("book_1984", "book_brave_new_world", "similar_to", weight=0.8)
framework.add_relationship("book_1984", "book_fahrenheit_451", "similar_to", weight=0.7)
framework.add_relationship("book_brave_new_world", "book_fahrenheit_451", "similar_to", weight=0.6)
framework.add_relationship("book_lord_of_the_rings", "book_harry_potter", "similar_to", weight=0.5)

# Save the knowledge graph
framework.save_to_file("books_graph.json")

# Query the graph in different ways

# 1. Basic query with no filters
print("All books:")
results = framework.query().execute()
for fact_id, fact_data in results:
    print(f"- {fact_id}: {fact_data['fact_statement']}")

# 2. Filter by category
print("\nFiction books:")
results = framework.query().filter_by_category("Fiction").execute()
for fact_id, fact_data in results:
    print(f"- {fact_id}: {fact_data['fact_statement']}")

# 3. Filter by tag
print("\nDystopian novels:")
results = framework.query().filter_by_tag("dystopian").execute()
for fact_id, fact_data in results:
    print(f"- {fact_id}: {fact_data['fact_statement']}")

# 4. Filter by multiple tags (any match)
print("\nBooks with either 'fantasy' or 'dystopian' tags:")
results = framework.query().filter_by_tags(["fantasy", "dystopian"]).execute()
for fact_id, fact_data in results:
    print(f"- {fact_id}: {fact_data['fact_statement']}")

# 5. Filter by multiple tags (all match)
print("\nBooks with both 'novel' and 'dystopian' tags:")
results = framework.query().filter_by_tags(["novel", "dystopian"], match_all=True).execute()
for fact_id, fact_data in results:
    print(f"- {fact_id}: {fact_data['fact_statement']}")

# 6. Filter by author
print("\nBooks by George Orwell:")
results = framework.query().filter_by_author("George Orwell").execute()
for fact_id, fact_data in results:
    print(f"- {fact_id}: {fact_data['fact_statement']}")

# 7. Filter by text content
print("\nBooks with 'dystopian' in the description:")
results = framework.query().filter_by_text("dystopian").execute()
for fact_id, fact_data in results:
    print(f"- {fact_id}: {fact_data['fact_statement']}")

# 8. Filter by regex pattern
print("\nBooks published in the 1950s:")
results = framework.query().filter_by_regex(r"published in 195\d").execute()
for fact_id, fact_data in results:
    print(f"- {fact_id}: {fact_data['fact_statement']}")

# 9. Filter by related fact
print("\nBooks similar to '1984':")
results = framework.query().filter_by_related_fact("book_1984").execute()
for fact_id, fact_data in results:
    print(f"- {fact_id}: {fact_data['fact_statement']}")

# 10. Sort results
print("\nBooks sorted by publication date:")
results = framework.query().sort_by("publication_date").execute()
for fact_id, fact_data in results:
    print(f"- {fact_id} ({fact_data['publication_date']}): {fact_data['fact_statement']}")

# 11. Chain multiple filters
print("\nDystopian novels published before 1950:")
results = framework.query().filter_by_tag("dystopian").filter_by_regex(r"published in 19[0-4]\d").execute()
for fact_id, fact_data in results:
    print(f"- {fact_id}: {fact_data['fact_statement']}")

# 12. Use specialized query functions
print("\nBooks with 'similar_to' relationships:")
results = framework.get_with_relationship("similar_to")
print("Sources:", results["sources"])
print("Targets:", results["targets"])

# 13. Get related facts
print("\nBooks related to '1984':")
related_facts = framework.get_related("book_1984")
for fact_id in related_facts:
    fact = framework.get_fact(fact_id)
    print(f"- {fact_id}: {fact['fact_statement']}")

# 14. Find facts by pattern
print("\nBooks published in specific years:")
results = framework.find_by_pattern(r"published in \d{4}$")
for fact_id in results:
    fact = framework.get_fact(fact_id)
    print(f"- {fact_id}: {fact['fact_statement']}")

# 15. Visualize query results
dystopian_books = [fact_id for fact_id, _ in framework.query().filter_by_tag("dystopian").execute()]
framework.visualize(highlight_nodes=dystopian_books, show_labels=True)
