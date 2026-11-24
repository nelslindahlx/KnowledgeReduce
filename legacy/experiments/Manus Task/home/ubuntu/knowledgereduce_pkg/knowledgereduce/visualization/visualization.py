"""
Visualization module for knowledge graphs.
This module provides functions for visualizing knowledge graphs in various formats.
"""

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
import io
import base64
from collections import Counter

def visualize_graph(knowledge_graph, max_nodes=50, layout='spring', node_size_by='quality_score', 
                   edge_width_by='weight', node_color_by='category', title=None, figsize=(12, 10),
                   show_labels=True, label_font_size=8, return_html=False):
    """
    Visualize a knowledge graph.
    
    Args:
        knowledge_graph: The knowledge graph to visualize
        max_nodes (int, optional): Maximum number of nodes to display. Defaults to 50.
        layout (str, optional): Layout algorithm ('spring', 'circular', 'kamada_kawai', 'spectral'). Defaults to 'spring'.
        node_size_by (str, optional): Node attribute to determine size. Defaults to 'quality_score'.
        edge_width_by (str, optional): Edge attribute to determine width. Defaults to 'weight'.
        node_color_by (str, optional): Node attribute to determine color. Defaults to 'category'.
        title (str, optional): Plot title. Defaults to None.
        figsize (tuple, optional): Figure size. Defaults to (12, 10).
        show_labels (bool, optional): Whether to show node labels. Defaults to True.
        label_font_size (int, optional): Font size for labels. Defaults to 8.
        return_html (bool, optional): Whether to return HTML for interactive visualization. Defaults to False.
        
    Returns:
        matplotlib.figure.Figure or str: The figure object or HTML string if return_html is True
    """
    # Get the graph
    G = knowledge_graph.graph
    
    # If graph is too large, take a subset
    if len(G) > max_nodes:
        # Get top nodes by quality score or degree if quality score not available
        if node_size_by == 'quality_score' and nx.get_node_attributes(G, 'quality_score'):
            quality_scores = nx.get_node_attributes(G, 'quality_score')
            top_nodes = sorted(quality_scores.items(), key=lambda x: x[1], reverse=True)[:max_nodes]
            top_nodes = [node for node, _ in top_nodes]
        else:
            # Use degree centrality as fallback
            centrality = nx.degree_centrality(G)
            top_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:max_nodes]
            top_nodes = [node for node, _ in top_nodes]
        
        # Create subgraph with top nodes
        G = G.subgraph(top_nodes)
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Choose layout
    if layout == 'spring':
        pos = nx.spring_layout(G, seed=42)
    elif layout == 'circular':
        pos = nx.circular_layout(G)
    elif layout == 'kamada_kawai':
        pos = nx.kamada_kawai_layout(G)
    elif layout == 'spectral':
        pos = nx.spectral_layout(G)
    else:
        pos = nx.spring_layout(G, seed=42)
    
    # Get node sizes
    if node_size_by and nx.get_node_attributes(G, node_size_by):
        node_sizes = nx.get_node_attributes(G, node_size_by)
        # Normalize sizes between 100 and 1000
        if node_sizes:
            min_size = min(node_sizes.values())
            max_size = max(node_sizes.values())
            if min_size != max_size:
                node_sizes = {k: 100 + 900 * (v - min_size) / (max_size - min_size) for k, v in node_sizes.items()}
            else:
                node_sizes = {k: 500 for k in node_sizes}
        else:
            node_sizes = {node: 300 for node in G.nodes()}
    else:
        node_sizes = {node: 300 for node in G.nodes()}
    
    # Get edge widths
    if edge_width_by and nx.get_edge_attributes(G, edge_width_by):
        edge_widths = nx.get_edge_attributes(G, edge_width_by)
        # Normalize widths between 1 and 5
        if edge_widths:
            min_width = min(edge_widths.values())
            max_width = max(edge_widths.values())
            if min_width != max_width:
                edge_widths = {k: 1 + 4 * (v - min_width) / (max_width - min_width) for k, v in edge_widths.items()}
            else:
                edge_widths = {k: 2 for k in edge_widths}
        else:
            edge_widths = {edge: 1 for edge in G.edges()}
    else:
        edge_widths = {edge: 1 for edge in G.edges()}
    
    # Get node colors
    if node_color_by and nx.get_node_attributes(G, node_color_by):
        node_colors = nx.get_node_attributes(G, node_color_by)
        # Map categories to colors
        unique_categories = set(node_colors.values())
        color_map = {}
        cmap = plt.cm.get_cmap('tab20', len(unique_categories))
        for i, category in enumerate(unique_categories):
            color_map[category] = cmap(i)
        node_colors = [color_map[node_colors[node]] for node in G.nodes()]
    else:
        node_colors = ['skyblue' for _ in G.nodes()]
    
    # Draw the graph
    nx.draw_networkx_edges(G, pos, width=[edge_widths.get(edge, 1) for edge in G.edges()], alpha=0.5, edge_color='gray')
    nx.draw_networkx_nodes(G, pos, node_size=[node_sizes.get(node, 300) for node in G.nodes()], node_color=node_colors, alpha=0.8)
    
    if show_labels:
        # Get node labels (use fact_statement if available, otherwise node ID)
        node_labels = {}
        for node in G.nodes():
            if 'fact_statement' in G.nodes[node]:
                # Truncate long statements
                statement = G.nodes[node]['fact_statement']
                if len(statement) > 30:
                    statement = statement[:27] + '...'
                node_labels[node] = statement
            else:
                node_labels[node] = node
        
        nx.draw_networkx_labels(G, pos, labels=node_labels, font_size=label_font_size, font_color='black')
    
    # Add legend for node colors if using categories
    if node_color_by == 'category' and nx.get_node_attributes(G, 'category'):
        categories = nx.get_node_attributes(G, 'category')
        unique_categories = set(categories.values())
        color_map = {}
        cmap = plt.cm.get_cmap('tab20', len(unique_categories))
        for i, category in enumerate(unique_categories):
            color_map[category] = cmap(i)
        
        # Create legend patches
        from matplotlib.patches import Patch
        legend_elements = [Patch(facecolor=color_map[cat], edgecolor='gray', label=cat) for cat in unique_categories]
        ax.legend(handles=legend_elements, loc='upper right', title='Categories')
    
    # Set title
    if title:
        plt.title(title)
    else:
        plt.title(f'Knowledge Graph Visualization ({len(G.nodes())} nodes, {len(G.edges())} edges)')
    
    # Remove axis
    plt.axis('off')
    
    # Tight layout
    plt.tight_layout()
    
    if return_html:
        # Convert to HTML for interactive visualization
        from IPython.display import HTML
        
        # Save figure to buffer
        buf = io.BytesIO()
        fig.savefig(buf, format='png')
        buf.seek(0)
        
        # Convert to base64
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        
        # Create HTML
        html = f"""
        <html>
        <head>
            <style>
                .graph-container {{
                    text-align: center;
                    margin: 20px;
                }}
                .graph-image {{
                    max-width: 100%;
                    height: auto;
                }}
                .graph-title {{
                    font-size: 18px;
                    font-weight: bold;
                    margin-bottom: 10px;
                }}
                .graph-info {{
                    font-size: 14px;
                    margin-top: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="graph-container">
                <div class="graph-title">{title or 'Knowledge Graph Visualization'}</div>
                <img src="data:image/png;base64,{img_str}" class="graph-image">
                <div class="graph-info">
                    Nodes: {len(G.nodes())}, Edges: {len(G.edges())}
                </div>
            </div>
        </body>
        </html>
        """
        
        plt.close(fig)
        return html
    
    return fig

def visualize_fact_neighborhood(knowledge_graph, fact_id, depth=1, layout='spring', 
                               include_incoming=True, include_outgoing=True, 
                               title=None, figsize=(10, 8), show_labels=True, 
                               label_font_size=8, return_html=False):
    """
    Visualize a specific fact and its neighborhood in the knowledge graph.
    
    Args:
        knowledge_graph: The knowledge graph
        fact_id (str): ID of the fact to visualize
        depth (int, optional): Depth of neighborhood to include. Defaults to 1.
        layout (str, optional): Layout algorithm. Defaults to 'spring'.
        include_incoming (bool, optional): Whether to include incoming relationships. Defaults to True.
        include_outgoing (bool, optional): Whether to include outgoing relationships. Defaults to True.
        title (str, optional): Plot title. Defaults to None.
        figsize (tuple, optional): Figure size. Defaults to (10, 8).
        show_labels (bool, optional): Whether to show node labels. Defaults to True.
        label_font_size (int, optional): Font size for labels. Defaults to 8.
        return_html (bool, optional): Whether to return HTML for interactive visualization. Defaults to False.
        
    Returns:
        matplotlib.figure.Figure or str: The figure object or HTML string if return_html is True
        
    Raises:
        ValueError: If fact_id is not found in the graph
    """
    # Get the graph
    G = knowledge_graph.graph
    
    # Check if fact exists
    if fact_id not in G:
        raise ValueError(f"Fact ID '{fact_id}' not found in the graph.")
    
    # Create neighborhood subgraph
    nodes = {fact_id}
    current_depth = 0
    frontier = {fact_id}
    
    while current_depth < depth:
        new_frontier = set()
        for node in frontier:
            if include_outgoing:
                new_frontier.update(G.successors(node))
            if include_incoming:
                new_frontier.update(G.predecessors(node))
        
        nodes.update(new_frontier)
        frontier = new_frontier
        current_depth += 1
    
    # Create subgraph
    subgraph = G.subgraph(nodes)
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Choose layout
    if layout == 'spring':
        pos = nx.spring_layout(subgraph, seed=42)
    elif layout == 'circular':
        pos = nx.circular_layout(subgraph)
    elif layout == 'kamada_kawai':
        pos = nx.kamada_kawai_layout(subgraph)
    elif layout == 'spectral':
        pos = nx.spectral_layout(subgraph)
    else:
        pos = nx.spring_layout(subgraph, seed=42)
    
    # Node colors: central node is red, others are blue
    node_colors = ['red' if node == fact_id else 'skyblue' for node in subgraph.nodes()]
    
    # Node sizes: central node is larger
    node_sizes = [600 if node == fact_id else 300 for node in subgraph.nodes()]
    
    # Edge colors: outgoing is blue, incoming is green
    edge_colors = []
    for u, v in subgraph.edges():
        if u == fact_id:
            edge_colors.append('blue')
        elif v == fact_id:
            edge_colors.append('green')
        else:
            edge_colors.append('gray')
    
    # Draw the graph
    nx.draw_networkx_edges(subgraph, pos, edge_color=edge_colors, alpha=0.7)
    nx.draw_networkx_nodes(subgraph, pos, node_color=node_colors, node_size=node_sizes, alpha=0.8)
    
    if show_labels:
        # Get node labels (use fact_statement if available, otherwise node ID)
        node_labels = {}
        for node in subgraph.nodes():
            if 'fact_statement' in subgraph.nodes[node]:
                # Truncate long statements
                statement = subgraph.nodes[node]['fact_statement']
                if len(statement) > 30:
                    statement = statement[:27] + '...'
                node_labels[node] = statement
            else:
                node_labels[node] = node
        
        nx.draw_networkx_labels(subgraph, pos, labels=node_labels, font_size=label_font_size, font_color='black')
    
    # Set title
    if title:
        plt.title(title)
    else:
        plt.title(f'Neighborhood of Fact "{fact_id}" (Depth: {depth})')
    
    # Add legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', markerfacecolor='red', markersize=10, label='Central Fact'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='skyblue', markersize=10, label='Related Facts'),
    ]
    if include_outgoing:
        legend_elements.append(Line2D([0], [0], color='blue', lw=2, label='Outgoing Relationships'))
    if include_incoming:
        legend_elements.append(Line2D([0], [0], color='green', lw=2, label='Incoming Relationships'))
    
    ax.legend(handles=legend_elements, loc='upper right')
    
    # Remove axis
    plt.axis('off')
    
    # Tight layout
    plt.tight_layout()
    
    if return_html:
        # Convert to HTML for interactive visualization
        from IPython.display import HTML
        
        # Save figure to buffer
        buf = io.BytesIO()
        fig.savefig(buf, format='png')
        buf.seek(0)
        
        # Convert to base64
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        
        # Create HTML
        html = f"""
        <html>
        <head>
            <style>
                .graph-container {{
                    text-align: center;
                    margin: 20px;
                }}
                .graph-image {{
                    max-width: 100%;
                    height: auto;
                }}
                .graph-title {{
                    font-size: 18px;
                    font-weight: bold;
                    margin-bottom: 10px;
                }}
                .graph-info {{
                    font-size: 14px;
                    margin-top: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="graph-container">
                <div class="graph-title">{title or f'Neighborhood of Fact "{fact_id}" (Depth: {depth})'}</div>
                <img src="data:image/png;base64,{img_str}" class="graph-image">
                <div class="graph-info">
                    Nodes: {len(subgraph.nodes())}, Edges: {len(subgraph.edges())}
                </div>
            </div>
        </body>
        </html>
        """
        
        plt.close(fig)
        return html
    
    return fig

def create_graph_statistics(knowledge_graph):
    """
    Create statistics about the knowledge graph.
    
    Args:
        knowledge_graph: The knowledge graph
        
    Returns:
        dict: Dictionary with graph statistics
    """
    # Get the graph
    G = knowledge_graph.graph
    
    # Basic statistics
    stats = {
        'num_nodes': len(G.nodes()),
        'num_edges': len(G.edges()),
        'density': nx.density(G),
        'is_directed': G.is_directed(),
        'is_connected': nx.is_weakly_connected(G) if G.is_directed() else nx.is_connected(G),
    }
    
    # Node degree statistics
    if G.nodes():
        in_degrees = [d for n, d in G.in_degree()] if G.is_directed() else []
        out_degrees = [d for n, d in G.out_degree()] if G.is_directed() else []
        degrees = [d for n, d in G.degree()]
        
        stats['degree_stats'] = {
            'min_degree': min(degrees),
            'max_degree': max(degrees),
            'avg_degree': sum(degrees) / len(degrees),
        }
        
        if G.is_directed():
        <response clipped><NOTE>To save on context only part of this file has been shown to you. You should retry this tool after you have searched inside the file with `grep -n` in order to find the line numbers of what you are looking for.</NOTE>