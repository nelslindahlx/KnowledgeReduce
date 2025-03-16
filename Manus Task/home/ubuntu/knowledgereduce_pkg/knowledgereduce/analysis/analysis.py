"""
Analysis module for knowledge graphs.
This module provides functions for analyzing knowledge graphs and extracting insights.
"""

import networkx as nx
import numpy as np
from collections import Counter, defaultdict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import community as community_louvain
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

# Download required NLTK resources if not already present
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

def identify_central_facts(knowledge_graph, top_n=10, method='betweenness'):
    """
    Identify the most central facts in the knowledge graph.
    
    Args:
        knowledge_graph: The knowledge graph to analyze
        top_n (int, optional): Number of top central facts to return. Defaults to 10.
        method (str, optional): Centrality measure to use ('degree', 'betweenness', 'eigenvector', 'pagerank'). Defaults to 'betweenness'.
        
    Returns:
        list: List of tuples (fact_id, centrality_score) sorted by centrality score
    """
    # Get the graph
    G = knowledge_graph.graph
    
    # Calculate centrality based on method
    if method == 'degree':
        centrality = nx.degree_centrality(G)
    elif method == 'betweenness':
        centrality = nx.betweenness_centrality(G)
    elif method == 'eigenvector':
        centrality = nx.eigenvector_centrality_numpy(G)
    elif method == 'pagerank':
        centrality = nx.pagerank(G)
    else:
        raise ValueError(f"Unsupported centrality method: {method}. Use 'degree', 'betweenness', 'eigenvector', or 'pagerank'.")
    
    # Sort by centrality score
    sorted_centrality = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
    
    # Return top N
    return sorted_centrality[:top_n]

def identify_fact_clusters(knowledge_graph, min_cluster_size=3, resolution=1.0):
    """
    Identify clusters of related facts in the knowledge graph.
    
    Args:
        knowledge_graph: The knowledge graph to analyze
        min_cluster_size (int, optional): Minimum size of clusters to return. Defaults to 3.
        resolution (float, optional): Resolution parameter for community detection. Higher values give smaller communities. Defaults to 1.0.
        
    Returns:
        list: List of fact clusters, where each cluster is a list of fact IDs
    """
    # Get the graph
    G = knowledge_graph.graph
    
    # Convert directed graph to undirected for community detection
    if G.is_directed():
        G_undirected = G.to_undirected()
    else:
        G_undirected = G
    
    # Detect communities using Louvain method
    partition = community_louvain.best_partition(G_undirected, resolution=resolution)
    
    # Group facts by community
    communities = defaultdict(list)
    for node, community_id in partition.items():
        communities[community_id].append(node)
    
    # Filter by minimum size
    clusters = [cluster for cluster in communities.values() if len(cluster) >= min_cluster_size]
    
    # Sort clusters by size (largest first)
    clusters.sort(key=len, reverse=True)
    
    return clusters

def calculate_fact_similarity(knowledge_graph, fact_id1, fact_id2, method='content'):
    """
    Calculate similarity between two facts.
    
    Args:
        knowledge_graph: The knowledge graph
        fact_id1 (str): ID of the first fact
        fact_id2 (str): ID of the second fact
        method (str, optional): Similarity method ('content', 'structural', 'combined'). Defaults to 'content'.
        
    Returns:
        float: Similarity score between 0 and 1
        
    Raises:
        ValueError: If either fact ID is not found in the graph
    """
    # Get the graph
    G = knowledge_graph.graph
    
    # Check if facts exist
    if fact_id1 not in G:
        raise ValueError(f"Fact ID '{fact_id1}' not found in the graph.")
    if fact_id2 not in G:
        raise ValueError(f"Fact ID '{fact_id2}' not found in the graph.")
    
    # Content-based similarity
    if method in ['content', 'combined']:
        # Get fact statements
        statement1 = G.nodes[fact_id1].get('fact_statement', '')
        statement2 = G.nodes[fact_id2].get('fact_statement', '')
        
        # Calculate content similarity using TF-IDF and cosine similarity
        if statement1 and statement2:
            vectorizer = TfidfVectorizer()
            try:
                tfidf_matrix = vectorizer.fit_transform([statement1, statement2])
                content_similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            except:
                # Fallback if TF-IDF fails
                content_similarity = 0.0
                if statement1.lower() == statement2.lower():
                    content_similarity = 1.0
        else:
            content_similarity = 0.0
    else:
        content_similarity = 0.0
    
    # Structural similarity
    if method in ['structural', 'combined']:
        # Get common neighbors
        neighbors1 = set(G.neighbors(fact_id1))
        neighbors2 = set(G.neighbors(fact_id2))
        common_neighbors = neighbors1.intersection(neighbors2)
        
        # Calculate Jaccard similarity
        if neighbors1 or neighbors2:
            structural_similarity = len(common_neighbors) / len(neighbors1.union(neighbors2))
        else:
            structural_similarity = 0.0
    else:
        structural_similarity = 0.0
    
    # Combined similarity
    if method == 'combined':
        # Weight content similarity higher
        similarity = 0.7 * content_similarity + 0.3 * structural_similarity
    elif method == 'content':
        similarity = content_similarity
    else:  # structural
        similarity = structural_similarity
    
    return similarity

def find_similar_facts(knowledge_graph, fact_id, threshold=0.5, max_results=10, method='content'):
    """
    Find facts similar to a given fact.
    
    Args:
        knowledge_graph: The knowledge graph
        fact_id (str): ID of the reference fact
        threshold (float, optional): Minimum similarity score. Defaults to 0.5.
        max_results (int, optional): Maximum number of results. Defaults to 10.
        method (str, optional): Similarity method ('content', 'structural', 'combined'). Defaults to 'content'.
        
    Returns:
        list: List of tuples (fact_id, similarity_score) sorted by similarity score
        
    Raises:
        ValueError: If fact_id is not found in the graph
    """
    # Get the graph
    G = knowledge_graph.graph
    
    # Check if fact exists
    if fact_id not in G:
        raise ValueError(f"Fact ID '{fact_id}' not found in the graph.")
    
    # Get reference fact statement
    ref_statement = G.nodes[fact_id].get('fact_statement', '')
    
    # Content-based similarity
    if method in ['content', 'combined']:
        # Collect all fact statements
        fact_statements = {}
        for node_id, node_data in G.nodes(data=True):
            if node_id != fact_id and 'fact_statement' in node_data:
                fact_statements[node_id] = node_data['fact_statement']
        
        # Calculate content similarity using TF-IDF and cosine similarity
        if fact_statements and ref_statement:
            all_statements = [ref_statement] + list(fact_statements.values())
            vectorizer = TfidfVectorizer()
            try:
                tfidf_matrix = vectorizer.fit_transform(all_statements)
                similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:])
                content_similarities = {node_id: similarities[0][i] for i, node_id in enumerate(fact_statements.keys())}
            except:
                # Fallback if TF-IDF fails
                content_similarities = {node_id: 0.0 for node_id in fact_statements.keys()}
                for node_id, statement in fact_statements.items():
                    if statement.lower() == ref_statement.lower():
                        content_similarities[node_id] = 1.0
        else:
            content_similarities = {node_id: 0.0 for node_id in G.nodes() if node_id != fact_id}
    
    # Structural similarity
    if method in ['structural', 'combined']:
        # Get reference fact neighbors
        ref_neighbors = set(G.neighbors(fact_id))
        
        # Calculate structural similarity for each fact
        structural_similarities = {}
        for node_id in G.nodes():
            if node_id != fact_id:
                node_neighbors = set(G.neighbors(node_id))
                common_neighbors = ref_neighbors.intersection(node_neighbors)
                
                # Calculate Jaccard similarity
                if ref_neighbors or node_neighbors:
                    structural_similarities[node_id] = len(common_neighbors) / len(ref_neighbors.union(node_neighbors))
                else:
                    structural_similarities[node_id] = 0.0
    
    # Combine similarities
    similarities = {}
    for node_id in G.nodes():
        if node_id != fact_id:
            if method == 'content':
                similarities[node_id] = content_similarities.get(node_id, 0.0)
            elif method == 'structural':
                similarities[node_id] = structural_similarities.get(node_id, 0.0)
            else:  # combined
                content_sim = content_similarities.get(node_id, 0.0)
                structural_sim = structural_similarities.get(node_id, 0.0)
                similarities[node_id] = 0.7 * content_sim + 0.3 * structural_sim
    
    # Filter by threshold and sort
    filtered_similarities = {node_id: sim for node_id, sim in similarities.items() if sim >= threshold}
    sorted_similarities = sorted(filtered_similarities.items(), key=lambda x: x[1], reverse=True)
    
    # Return top results
    return sorted_similarities[:max_results]

def analyze_fact_categories(knowledge_graph):
    """
    Analyze the distribution of fact categories.
    
    Args:
        knowledge_graph: The knowledge graph
        
    Returns:
        dict: Dictionary with category statistics
    """
    # Get the graph
    G = knowledge_graph.graph
    
    # Get categories
    categories = nx.get_node_attributes(G, 'category')
    
    # Count categories
    category_counts = Counter(categories.values())
    
    # Calculate percentages
    total_facts = len(G.nodes())
    category_percentages = {cat: count / total_facts * 100 for cat, count in category_counts.items()}
    
    # Find most common categories
    most_common = category_counts.most_common()
    
    # Calculate average quality score per category
    quality_scores = nx.get_node_attributes(G, 'quality_score')
    category_quality = defaultdict(list)
    
    for node_id, category in categories.items():
        if node_id in quality_scores:
            category_quality[category].append(quality_scores[node_id])
    
    category_avg_quality = {cat: sum(scores) / len(scores) if scores else 0 
                           for cat, scores in category_quality.items()}
    
    # Return statistics
    return {
        'total_facts': total_facts,
        'num_categories': len(category_counts),
        'category_counts': dict(category_counts),
        'category_percentages': category_percentages,
        'most_common_categories': most_common,
        'category_avg_quality': category_avg_quality
    }

def find_path_between_facts(knowledge_graph, source_id, target_id, max_length=None):
    """
    Find the shortest path between two facts.
    
    Args:
        knowledge_graph: The knowledge graph
        source_id (str): ID of the source fact
        target_id (str): ID of the target fact
        max_length (int, optional): Maximum path length. Defaults to None.
        
    Returns:
        list: List of fact IDs representing the path
        
    Raises:
        ValueError: If either fact ID is not found in the graph or no path exists
    """
    # Get the graph
    G = knowledge_graph.graph
    
    # Check if facts exist
    if source_id not in G:
        raise ValueError(f"Source fact ID '{source_id}' not found in the graph.")
    if target_id not in G:
        raise ValueError(f"Target fact ID '{target_id}' not found in the graph.")
    
    # Find shortest path
    try:
        if max_length is not None:
            # Use BFS with cutoff
            path = nx.shortest_path(G, source=source_id, target=target_id, cutoff=max_length)
        else:
            path = nx.shortest_path(G, source=source_id, target=target_id)
        
        return path
    except nx.NetworkXNoPath:
        raise ValueError(f"No path exists between '{source_id}' and '{target_id}'.")
    except nx.NetworkXError as e:
        raise ValueError(f"Error finding path: {e}")

def extract_keywords_from_fact(knowledge_graph, fact_id, num_keywords=5):
    """
    Extract keywords from a fact statement.
    
    Args:
        knowledge_graph: The knowledge graph
        fact_id (str): ID of the fact
        num_keywords (int, optional): Number of keywords to extract. Defaults to 5.
        
    Returns:
        list: List of keywords
        
    Raises:
        ValueError: If fact ID is not found in the graph
    """
    # Get the graph
    G = knowledge_graph.graph
    
    # Check if fact exists
    if fact_id not in G:
        raise ValueError(f"Fact ID '{fact_id}' not found in the graph.")
    
    # Get fact statement
    statement = G.nodes[fact_id].get('fact_statement', '')
    
    if not statement:
        return []
    
    # Tokenize and remove stopwords
    stop_words = set(stopwords.words('english'))
    tokens = word_tokenize(statement.lower())
    filtered_tokens = [token for token in tokens if token.isalnum() and token not in stop_words]
    
    # Count token frequencies
    token_counts = Counter(filtered_tokens)
    
    # Return top keywords
    return [keyword for keyword, _ in token_counts.most_common(num_keywords)]

def analyze_fact_reliability(knowledge_graph):
    """
    Analyze the reliability of facts in the knowledge graph.
    
    Args:
        knowledge_graph: The knowledge graph
        
    Returns:
        dict: Dictionary with reliability statistics
    """
    # Get the graph
    G = knowledge_graph.graph
    
    # Get reliability ratings
    reliability_ratings = nx.get_node_attributes(G, 'reliability_rating')
    
    # Convert enum to value if needed
    reliability_values = {}
    for node_id, rating in reliability_ratings.items():
        if hasattr(rating, 'value'):
            reliability_values[node_id] = rating.value
        else:
            reliability_values[node_id] = rating
    
    # Count reliability levels
    reliability_counts = Counter(reliability_values.values())
    
    # Calculate percentages
    total_facts = len(G.nodes())
    reliability_percentages = {level: count / total_facts * 100 for level, count in reliability_counts.items()}
    
    # Calculate average reliability
    avg_reliability = sum(reliability_values.values()) / len(reliability_values) if reliability_values else 0
    
    # Return statistics
    return {
        'total_facts': total_facts,
        'reliability_counts': dict(reliability_counts),
        'reliability_percentages': reliability_percentages,
        'avg_reliability': avg_reliability
    }

def identify_conflicting_facts(knowledge_graph, threshold=0.7):
    """
    Identify potentially conflicting facts in the knowledge graph.
    
    Args:
        knowledge_graph: The knowledge graph
        threshold (float, optional): Similarity threshold for potential conflicts. Defaults to 0.7.
        
    Returns:
        list: List of tuples (fact_id1, fact_id2, similarity_score) representing potential conflicts
    """
    # Get the graph
    G = knowledge_graph.graph
    
    # Get fact statem<response clipped><NOTE>To save on context only part of this file has been shown to you. You should retry this tool after you have searched inside the file with `grep -n` in order to find the line numbers of what you are looking for.</NOTE>