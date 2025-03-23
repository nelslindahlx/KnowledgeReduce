#!/usr/bin/env python3
"""
Visualization Example for KnowledgeReduce

This script demonstrates how to visualize a knowledge graph created with KnowledgeReduce
using NetworkX visualization capabilities.
"""

import sys
import os
from datetime import datetime
import matplotlib.pyplot as plt
import networkx as nx

# Add the parent directory to the path to import the package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from knowledge_graph_pkg import KnowledgeGraph
from knowledge_graph_pkg.core import ReliabilityRating


def create_sample_knowledge_graph():
    """
    Create a sample knowledge graph for visualization.
    
    Returns:
        KnowledgeGraph: A populated knowledge graph instance.
    """
    kg = KnowledgeGraph()
    
    # Add facts about programming languages
    kg.add_fact(
        fact_id="prog_lang_001",
        fact_statement="Python is a high-level programming language",
        category="Computer Science",
        tags=["Python", "programming", "language"],
        date_recorded=datetime.now(),
        last_updated=datetime.now(),
        reliability_rating=ReliabilityRating.VERIFIED,
        source_id="source_001",
        source_title="Python Documentation",
        author_creator="Python Software Foundation",
        publication_date=datetime.now(),
        url_reference="https://python.org",
        related_facts=[],
        contextual_notes="General description of Python",
        access_level="public",
        usage_count=20
    )
    
    kg.add_fact(
        fact_id="python_feature_001",
        fact_statement="Python supports multiple programming paradigms",
        category="Computer Science",
        tags=["Python", "programming", "paradigms"],
        date_recorded=datetime.now(),
        last_updated=datetime.now(),
        reliability_rating=ReliabilityRating.VERIFIED,
        source_id="source_001",
        source_title="Python Documentation",
        author_creator="Python Software Foundation",
        publication_date=datetime.now(),
        url_reference="https://python.org/features",
        related_facts=["prog_lang_001"],
        contextual_notes="Python programming paradigms",
        access_level="public",
        usage_count=15
    )
    
    kg.add_fact(
        fact_id="python_feature_002",
        fact_statement="Python has a comprehensive standard library",
        category="Computer Science",
        tags=["Python", "standard library"],
        date_recorded=datetime.now(),
        last_updated=datetime.now(),
        reliability_rating=ReliabilityRating.VERIFIED,
        source_id="source_001",
        source_title="Python Documentation",
        author_creator="Python Software Foundation",
        publication_date=datetime.now(),
        url_reference="https://python.org/library",
        related_facts=["prog_lang_001"],
        contextual_notes="Python standard library",
        access_level="public",
        usage_count=18
    )
    
    kg.add_fact(
        fact_id="prog_lang_002",
        fact_statement="JavaScript is a high-level programming language",
        category="Computer Science",
        tags=["JavaScript", "programming", "language"],
        date_recorded=datetime.now(),
        last_updated=datetime.now(),
        reliability_rating=ReliabilityRating.VERIFIED,
        source_id="source_002",
        source_title="JavaScript Documentation",
        author_creator="MDN Web Docs",
        publication_date=datetime.now(),
        url_reference="https://developer.mozilla.org/en-US/docs/Web/JavaScript",
        related_facts=[],
        contextual_notes="General description of JavaScript",
        access_level="public",
        usage_count=18
    )
    
    kg.add_fact(
        fact_id="js_feature_001",
        fact_statement="JavaScript is primarily used for web development",
        category="Computer Science",
        tags=["JavaScript", "web development"],
        date_recorded=datetime.now(),
        last_updated=datetime.now(),
        reliability_rating=ReliabilityRating.VERIFIED,
        source_id="source_002",
        source_title="JavaScript Documentation",
        author_creator="MDN Web Docs",
        publication_date=datetime.now(),
        url_reference="https://developer.mozilla.org/en-US/docs/Web/JavaScript/About_JavaScript",
        related_facts=["prog_lang_002"],
        contextual_notes="JavaScript usage",
        access_level="public",
        usage_count=16
    )
    
    # Add relationships between facts
    kg.graph.add_edge("prog_lang_001", "python_feature_001", relationship="has_feature")
    kg.graph.add_edge("prog_lang_001", "python_feature_002", relationship="has_feature")
    kg.graph.add_edge("prog_lang_002", "js_feature_001", relationship="has_feature")
    
    return kg


def visualize_knowledge_graph(kg, output_file=None):
    """
    Visualize a knowledge graph using NetworkX and matplotlib.
    
    Args:
        kg (KnowledgeGraph): The knowledge graph to visualize.
        output_file (str, optional): Path to save the visualization. If None, display only.
    """
    # Create a new figure
    plt.figure(figsize=(12, 8))
    
    # Create a directed graph for visualization
    G = kg.graph
    
    # Define node colors based on categories
    categories = {data.get('category', 'Unknown') for _, data in G.nodes(data=True)}
    category_colors = {category: plt.cm.Set3(i/len(categories)) for i, category in enumerate(categories)}
    
    node_colors = [category_colors[G.nodes[node].get('category', 'Unknown')] for node in G.nodes()]
    
    # Define node sizes based on quality score
    node_sizes = [100 + 10 * G.nodes[node].get('quality_score', 0) for node in G.nodes()]
    
    # Define edge labels based on relationships
    edge_labels = {(u, v): data.get('relationship', '') for u, v, data in G.edges(data=True)}
    
    # Create the layout
    pos = nx.spring_layout(G, seed=42)
    
    # Draw the graph
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes, alpha=0.8)
    nx.draw_networkx_edges(G, pos, width=1.0, alpha=0.5, arrowsize=20)
    nx.draw_networkx_labels(G, pos, font_size=10, font_family='sans-serif')
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=8)
    
    # Add a legend for categories
    legend_patches = [plt.Line2D([0], [0], marker='o', color='w', 
                                 markerfacecolor=color, markersize=10, label=category)
                      for category, color in category_colors.items()]
    plt.legend(handles=legend_patches, title="Categories", loc='upper right')
    
    # Add title and adjust layout
    plt.title("Knowledge Graph Visualization")
    plt.axis('off')
    plt.tight_layout()
    
    # Save or display the figure
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Visualization saved to {output_file}")
    else:
        plt.show()


def export_to_graphml(kg, output_file):
    """
    Export the knowledge graph to GraphML format.
    
    Args:
        kg (KnowledgeGraph): The knowledge graph to export.
        output_file (str): Path to save the GraphML file.
    """
    # Convert ReliabilityRating enum values to strings for export
    for node, data in kg.graph.nodes(data=True):
        if 'reliability_rating' in data and isinstance(data['reliability_rating'], ReliabilityRating):
            data['reliability_rating'] = data['reliability_rating'].name
    
    # Export to GraphML
    nx.write_graphml(kg.graph, output_file)
    print(f"Knowledge graph exported to GraphML: {output_file}")


def main():
    """
    Demonstrate visualization of a knowledge graph.
    """
    print("KnowledgeReduce Visualization Example")
    print("====================================\n")

    # Create a sample knowledge graph
    print("Creating a sample knowledge graph...")
    kg = create_sample_knowledge_graph()
    print(f"Created knowledge graph with {len(kg.graph.nodes)} facts and {len(kg.graph.edges)} relationships.\n")

    # Visualize the knowledge graph
    print("Visualizing the knowledge graph...")
    output_dir = os.path.dirname(os.path.abspath(__file__))
    visualization_file = os.path.join(output_dir, "knowledge_graph_visualization.png")
    visualize_knowledge_graph(kg, visualization_file)
    
    # Export to GraphML
    print("\nExporting the knowledge graph to GraphML format...")
    graphml_file = os.path.join(output_dir, "knowledge_graph.graphml")
    export_to_graphml(kg, graphml_file)
    
    print("\nVisualization example completed successfully.")


if __name__ == "__main__":
    main()
