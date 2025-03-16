"""
Visualization utilities for knowledge graphs.
This module provides functions for visualizing knowledge graphs using matplotlib and networkx.
"""
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

def visualize_graph(knowledge_graph, max_nodes=20, figsize=(12, 10), node_size=1000, 
                    font_size=8, edge_width=1.5, title="Knowledge Graph Visualization"):
    """
    Visualize a subset of the knowledge graph.
    
    Args:
        knowledge_graph (KnowledgeGraph): The knowledge graph to visualize
        max_nodes (int, optional): Maximum number of nodes to display. Defaults to 20.
        figsize (tuple, optional): Figure size. Defaults to (12, 10).
        node_size (int, optional): Size of nodes. Defaults to 1000.
        font_size (int, optional): Font size for node labels. Defaults to 8.
        edge_width (float, optional): Width of edges. Defaults to 1.5.
        title (str, optional): Title of the visualization. Defaults to "Knowledge Graph Visualization".
        
    Returns:
        matplotlib.figure.Figure: The figure object
    """
    # Get the graph from the KnowledgeGraph object
    G = knowledge_graph.graph
    
    # If graph is too large, take a subset
    if len(G.nodes) > max_nodes:
        # Take the first max_nodes nodes with highest quality score if available
        if 'quality_score' in next(iter(G.nodes(data=True)))[1]:
            nodes_with_scores = [(node, data.get('quality_score', 0)) 
                                for node, data in G.nodes(data=True)]
            nodes_with_scores.sort(key=lambda x: x[1], reverse=True)
            selected_nodes = [node for node, _ in nodes_with_scores[:max_nodes]]
        else:
            # Otherwise just take the first max_nodes nodes
            selected_nodes = list(G.nodes())[:max_nodes]
        
        # Create a subgraph with the selected nodes
        G = G.subgraph(selected_nodes)
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Set up layout
    pos = nx.spring_layout(G, seed=42)
    
    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_size=node_size, 
                          node_color='lightblue', alpha=0.8, ax=ax)
    
    # Draw edges
    nx.draw_networkx_edges(G, pos, width=edge_width, alpha=0.5, 
                          edge_color='gray', arrows=True, ax=ax)
    
    # Prepare node labels (use fact_statement if available, otherwise node ID)
    labels = {}
    for node, data in G.nodes(data=True):
        if 'fact_statement' in data:
            # Truncate long statements
            statement = data['fact_statement']
            if len(statement) > 30:
                statement = statement[:27] + "..."
            labels[node] = statement
        else:
            labels[node] = node
    
    # Draw node labels
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=font_size, 
                           font_family='sans-serif', ax=ax)
    
    # Draw edge labels if relationship_type is available
    edge_labels = {}
    for u, v, data in G.edges(data=True):
        if 'relationship_type' in data:
            edge_labels[(u, v)] = data['relationship_type']
    
    if edge_labels:
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, 
                                    font_size=font_size-2, ax=ax)
    
    # Set title and remove axis
    plt.title(title)
    plt.axis('off')
    
    return fig

def visualize_fact_neighborhood(knowledge_graph, fact_id, depth=1, max_nodes=15, 
                               figsize=(10, 8), node_size=800, font_size=8):
    """
    Visualize the neighborhood of a specific fact in the knowledge graph.
    
    Args:
        knowledge_graph (KnowledgeGraph): The knowledge graph
        fact_id (str): ID of the fact to visualize neighborhood for
        depth (int, optional): How many steps to expand from the central fact. Defaults to 1.
        max_nodes (int, optional): Maximum number of nodes to display. Defaults to 15.
        figsize (tuple, optional): Figure size. Defaults to (10, 8).
        node_size (int, optional): Size of nodes. Defaults to 800.
        font_size (int, optional): Font size for node labels. Defaults to 8.
        
    Returns:
        matplotlib.figure.Figure: The figure object
        
    Raises:
        ValueError: If fact_id is not found in the graph
    """
    # Get the graph from the KnowledgeGraph object
    G = knowledge_graph.graph
    
    # Check if fact_id exists
    if fact_id not in G:
        raise ValueError(f"Fact ID '{fact_id}' not found in the graph.")
    
    # Get neighborhood subgraph
    neighborhood = set([fact_id])
    current_layer = set([fact_id])
    
    # Expand neighborhood up to specified depth
    for _ in range(depth):
        next_layer = set()
        for node in current_layer:
            # Add successors (outgoing edges)
            next_layer.update(G.successors(node))
            # Add predecessors (incoming edges)
            next_layer.update(G.predecessors(node))
        
        # Update neighborhood and current layer
        neighborhood.update(next_layer)
        current_layer = next_layer
        
        # Check if we've reached the max_nodes limit
        if len(neighborhood) >= max_nodes:
            # Keep the central node and select others to stay within max_nodes
            others = list(neighborhood - {fact_id})
            if len(others) > max_nodes - 1:
                selected = others[:max_nodes - 1]
                neighborhood = set([fact_id] + selected)
            break
    
    # Create subgraph
    subgraph = G.subgraph(neighborhood)
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Set up layout
    pos = nx.spring_layout(subgraph, seed=42)
    
    # Draw nodes with central node highlighted
    node_colors = ['red' if node == fact_id else 'lightblue' for node in subgraph.nodes()]
    nx.draw_networkx_nodes(subgraph, pos, node_size=node_size, 
                          node_color=node_colors, alpha=0.8, ax=ax)
    
    # Draw edges
    nx.draw_networkx_edges(subgraph, pos, width=1.5, alpha=0.5, 
                          edge_color='gray', arrows=True, ax=ax)
    
    # Prepare node labels
    labels = {}
    for node, data in subgraph.nodes(data=True):
        if 'fact_statement' in data:
            # Truncate long statements
            statement = data['fact_statement']
            if len(statement) > 30:
                statement = statement[:27] + "..."
            labels[node] = statement
        else:
            labels[node] = node
    
    # Draw node labels
    nx.draw_networkx_labels(subgraph, pos, labels=labels, font_size=font_size, 
                           font_family='sans-serif', ax=ax)
    
    # Draw edge labels if relationship_type is available
    edge_labels = {}
    for u, v, data in subgraph.edges(data=True):
        if 'relationship_type' in data:
            edge_labels[(u, v)] = data['relationship_type']
    
    if edge_labels:
        nx.draw_networkx_edge_labels(subgraph, pos, edge_labels=edge_labels, 
                                    font_size=font_size-2, ax=ax)
    
    # Set title and remove axis
    plt.title(f"Neighborhood of Fact: {fact_id}")
    plt.axis('off')
    
    return fig

def create_graph_statistics(knowledge_graph):
    """
    Generate statistics about the knowledge graph.
    
    Args:
        knowledge_graph (KnowledgeGraph): The knowledge graph
        
    Returns:
        dict: Dictionary containing various statistics about the graph
    """
    G = knowledge_graph.graph
    
    stats = {
        'num_nodes': len(G.nodes),
        'num_edges': len(G.edges),
        'density': nx.density(G),
        'is_directed': nx.is_directed(G),
        'is_connected': nx.is_weakly_connected(G) if nx.is_directed(G) else nx.is_connected(G),
    }
    
    # Add degree statistics if graph is not empty
    if len(G.nodes) > 0:
        degrees = [d for _, d in G.degree()]
        in_degrees = [d for _, d in G.in_degree()] if nx.is_directed(G) else []
        out_degrees = [d for _, d in G.out_degree()] if nx.is_directed(G) else []
        
        stats.update({
            'avg_degree': sum(degrees) / len(degrees),
            'max_degree': max(degrees) if degrees else 0,
            'min_degree': min(degrees) if degrees else 0,
        })
        
        if nx.is_directed(G):
            stats.update({
                'avg_in_degree': sum(in_degrees) / len(in_degrees) if in_degrees else 0,
                'max_in_degree': max(in_degrees) if in_degrees else 0,
                'min_in_degree': min(in_degrees) if in_degrees else 0,
                'avg_out_degree': sum(out_degrees) / len(out_degrees) if out_degrees else 0,
                'max_out_degree': max(out_degrees) if out_degrees else 0,
                'min_out_degree': min(out_degrees) if out_degrees else 0,
            })
    
    # Add quality score statistics if available
    quality_scores = []
    for _, data in G.nodes(data=True):
        if 'quality_score' in data:
            quality_scores.append(data['quality_score'])
    
    if quality_scores:
        stats.update({
            'avg_quality_score': sum(quality_scores) / len(quality_scores),
            'max_quality_score': max(quality_scores),
            'min_quality_score': min(quality_scores),
        })
    
    return stats
