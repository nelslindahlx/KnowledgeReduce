"""
Advanced analysis module for knowledge graphs.
This module provides functions for analyzing and extracting insights from knowledge graphs.
"""
import networkx as nx
import numpy as np
from collections import Counter

def identify_central_facts(knowledge_graph, top_n=10, method='betweenness'):
    """
    Identify the most central facts in the knowledge graph.
    
    Args:
        knowledge_graph: The knowledge graph object
        top_n (int): Number of top central facts to return
        method (str): Centrality measure to use ('betweenness', 'degree', 'eigenvector', 'pagerank')
        
    Returns:
        list: List of tuples (fact_id, centrality_score) for the most central facts
    """
    G = knowledge_graph.graph
    
    if len(G.nodes) == 0:
        return []
    
    # Calculate centrality based on specified method
    if method == 'betweenness':
        centrality = nx.betweenness_centrality(G)
    elif method == 'degree':
        centrality = nx.degree_centrality(G)
    elif method == 'eigenvector':
        centrality = nx.eigenvector_centrality(G, max_iter=1000)
    elif method == 'pagerank':
        centrality = nx.pagerank(G)
    else:
        raise ValueError(f"Unknown centrality method: {method}")
    
    # Sort facts by centrality score
    sorted_facts = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
    
    # Return top N facts
    return sorted_facts[:top_n]

def identify_fact_clusters(knowledge_graph, min_cluster_size=3):
    """
    Identify clusters of related facts in the knowledge graph.
    
    Args:
        knowledge_graph: The knowledge graph object
        min_cluster_size (int): Minimum size of clusters to return
        
    Returns:
        list: List of fact clusters (each cluster is a list of fact IDs)
    """
    G = knowledge_graph.graph
    
    if len(G.nodes) == 0:
        return []
    
    # Find connected components for directed graph
    if nx.is_directed(G):
        # Convert to undirected for community detection
        undirected_G = G.to_undirected()
        components = list(nx.connected_components(undirected_G))
    else:
        components = list(nx.connected_components(G))
    
    # Filter components by minimum size
    clusters = [list(component) for component in components if len(component) >= min_cluster_size]
    
    return clusters

def calculate_fact_similarity(knowledge_graph, fact_id1, fact_id2):
    """
    Calculate similarity between two facts based on their attributes and connections.
    
    Args:
        knowledge_graph: The knowledge graph object
        fact_id1 (str): ID of the first fact
        fact_id2 (str): ID of the second fact
        
    Returns:
        float: Similarity score between 0 and 1
    """
    G = knowledge_graph.graph
    
    # Check if facts exist
    if fact_id1 not in G or fact_id2 not in G:
        raise ValueError("One or both fact IDs not found in the graph")
    
    # Get fact attributes
    fact1 = G.nodes[fact_id1]
    fact2 = G.nodes[fact_id2]
    
    # Initialize similarity components
    attribute_sim = 0
    connection_sim = 0
    
    # Calculate attribute similarity
    # Compare tags if available
    if 'tags' in fact1 and 'tags' in fact2:
        tags1 = set(fact1['tags'].split(', ')) if fact1['tags'] else set()
        tags2 = set(fact2['tags'].split(', ')) if fact2['tags'] else set()
        
        if tags1 and tags2:
            # Jaccard similarity for tags
            attribute_sim += len(tags1.intersection(tags2)) / len(tags1.union(tags2))
    
    # Compare categories if available
    if 'category' in fact1 and 'category' in fact2:
        if fact1['category'] == fact2['category']:
            attribute_sim += 1
    
    # Normalize attribute similarity
    attribute_sim = attribute_sim / 2  # Divided by number of attribute comparisons
    
    # Calculate connection similarity using common neighbors
    neighbors1 = set(G.neighbors(fact_id1))
    neighbors2 = set(G.neighbors(fact_id2))
    
    if neighbors1 or neighbors2:
        # Jaccard similarity for neighbors
        connection_sim = len(neighbors1.intersection(neighbors2)) / max(1, len(neighbors1.union(neighbors2)))
    
    # Combine similarities (equal weight)
    return (attribute_sim + connection_sim) / 2

def find_similar_facts(knowledge_graph, fact_id, threshold=0.5, max_results=10):
    """
    Find facts similar to a given fact.
    
    Args:
        knowledge_graph: The knowledge graph object
        fact_id (str): ID of the reference fact
        threshold (float): Minimum similarity score (0-1)
        max_results (int): Maximum number of results to return
        
    Returns:
        list: List of tuples (fact_id, similarity_score) for similar facts
    """
    G = knowledge_graph.graph
    
    # Check if fact exists
    if fact_id not in G:
        raise ValueError(f"Fact ID '{fact_id}' not found in the graph")
    
    similar_facts = []
    
    # Calculate similarity with all other facts
    for other_id in G.nodes:
        if other_id != fact_id:
            similarity = calculate_fact_similarity(knowledge_graph, fact_id, other_id)
            if similarity >= threshold:
                similar_facts.append((other_id, similarity))
    
    # Sort by similarity (descending)
    similar_facts.sort(key=lambda x: x[1], reverse=True)
    
    return similar_facts[:max_results]

def analyze_fact_categories(knowledge_graph):
    """
    Analyze the distribution of fact categories in the knowledge graph.
    
    Args:
        knowledge_graph: The knowledge graph object
        
    Returns:
        dict: Dictionary with category statistics
    """
    G = knowledge_graph.graph
    
    categories = []
    for _, data in G.nodes(data=True):
        if 'category' in data:
            categories.append(data['category'])
    
    # Count categories
    category_counts = Counter(categories)
    
    # Calculate percentages
    total = len(categories)
    category_percentages = {cat: count/total*100 for cat, count in category_counts.items()} if total > 0 else {}
    
    return {
        'total_facts': total,
        'unique_categories': len(category_counts),
        'category_counts': dict(category_counts),
        'category_percentages': category_percentages
    }

def find_path_between_facts(knowledge_graph, source_id, target_id, max_length=None):
    """
    Find the shortest path between two facts in the knowledge graph.
    
    Args:
        knowledge_graph: The knowledge graph object
        source_id (str): ID of the source fact
        target_id (str): ID of the target fact
        max_length (int, optional): Maximum path length to consider
        
    Returns:
        list: List of fact IDs representing the path, or empty list if no path exists
    """
    G = knowledge_graph.graph
    
    # Check if facts exist
    if source_id not in G:
        raise ValueError(f"Source fact ID '{source_id}' not found in the graph")
    if target_id not in G:
        raise ValueError(f"Target fact ID '{target_id}' not found in the graph")
    
    try:
        # Find shortest path
        if max_length:
            # Use cutoff to limit path length
            path = nx.shortest_path(G, source=source_id, target=target_id, cutoff=max_length)
        else:
            path = nx.shortest_path(G, source=source_id, target=target_id)
        return path
    except nx.NetworkXNoPath:
        # No path exists
        return []