"""Graph traversal, centrality, and community detection helpers."""

from __future__ import annotations

from typing import Literal

import networkx as nx

from knowledgereduce.models import KnowledgeReduceError


def k_hop_neighborhood(
    graph: nx.MultiDiGraph,
    center_node_id: str,
    k: int = 2,
    *,
    directed: bool = False,
) -> nx.MultiDiGraph:
    """Return the induced subgraph within *k* hops of *center_node_id*."""
    if center_node_id not in graph:
        raise KnowledgeReduceError(f"Node {center_node_id!r} not found in graph.")
    if k < 0:
        raise KnowledgeReduceError(f"k must be >= 0 (got {k}).")

    view = graph if directed else graph.to_undirected(as_view=True)
    distances = nx.single_source_shortest_path_length(view, center_node_id, cutoff=k)
    return graph.subgraph(distances.keys()).copy()


def bounded_shortest_path(
    graph: nx.MultiDiGraph,
    source_id: str,
    target_id: str,
    *,
    max_hops: int = 6,
    directed: bool = False,
) -> list[str] | None:
    """Return a shortest node path between *source_id* and *target_id* within *max_hops*."""
    if source_id not in graph or target_id not in graph:
        return None
    if max_hops < 0:
        return None
    view = graph if directed else graph.to_undirected(as_view=True)
    try:
        path = list(nx.shortest_path(view, source=source_id, target=target_id))
    except nx.NetworkXNoPath:
        return None
    if len(path) - 1 > max_hops:
        return None
    return [str(node) for node in path]


def central_nodes(
    graph: nx.MultiDiGraph,
    *,
    metric: Literal["pagerank", "degree", "betweenness"] = "pagerank",
    top_k: int = 10,
) -> list[tuple[str, float]]:
    """Rank top *top_k* central nodes using a safe empty/edgeless-aware metric."""
    if graph.number_of_nodes() == 0 or top_k <= 0:
        return []

    if metric == "degree":
        scores = {str(n): float(v) for n, v in nx.degree_centrality(graph).items()}
    elif metric == "betweenness":
        scores = {str(n): float(v) for n, v in nx.betweenness_centrality(graph).items()}
    else:
        if graph.number_of_edges() == 0:
            uniform = 1.0 / graph.number_of_nodes()
            scores = {str(n): uniform for n in graph.nodes()}
        else:
            scores = {str(n): float(v) for n, v in nx.pagerank(nx.DiGraph(graph)).items()}

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return ranked[:top_k]


def detect_communities(
    graph: nx.MultiDiGraph,
    *,
    seed: int = 42,
) -> list[list[str]]:
    """Detect node communities using NetworkX native Louvain modularity."""
    if graph.number_of_nodes() == 0:
        return []
    if graph.number_of_edges() == 0:
        return [[str(n)] for n in sorted(str(node) for node in graph.nodes())]

    undirected = nx.Graph()
    for node_id in graph.nodes():
        undirected.add_node(str(node_id))
    for src, dst in graph.edges():
        if src != dst:
            undirected.add_edge(str(src), str(dst))

    communities = nx.community.louvain_communities(undirected, seed=seed)
    return sorted(
        (sorted(str(node) for node in comm) for comm in communities), key=lambda c: (-len(c), c[0])
    )
