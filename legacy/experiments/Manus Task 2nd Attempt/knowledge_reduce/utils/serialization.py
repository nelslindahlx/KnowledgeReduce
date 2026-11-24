"""
Serialization utilities for the KnowledgeReduce framework.

This module provides functions for serializing and deserializing knowledge graphs
to enable portability and persistence.
"""

import json
import os
import networkx as nx


class KnowledgeGraphPortable:
    """
    Class for making knowledge graphs portable through serialization.
    
    This class provides methods for converting between different representations
    of knowledge graphs and serializing them to JSON format.
    """
    
    def __init__(self, knowledge_graph):
        """
        Initialize with a knowledge graph.
        
        Args:
            knowledge_graph: KnowledgeGraph instance, NetworkX graph, or compatible structure
        """
        # Check if knowledge_graph is a networkx graph
        if isinstance(knowledge_graph, (nx.Graph, nx.DiGraph, nx.MultiGraph, nx.MultiDiGraph)):
            self.graph = knowledge_graph
        # Check if knowledge_graph has a graph attribute that is a networkx graph
        elif hasattr(knowledge_graph, 'graph') and isinstance(knowledge_graph.graph, 
                                                             (nx.Graph, nx.DiGraph, nx.MultiGraph, nx.MultiDiGraph)):
            self.graph = knowledge_graph.graph
        # Check if knowledge_graph has a data attribute that is a list
        elif hasattr(knowledge_graph, 'data') and isinstance(knowledge_graph.data, list):
            self.graph = self.convert_list_to_graph(knowledge_graph.data)
        else:
            raise ValueError("Unsupported knowledge_graph structure")
    
    def convert_list_to_graph(self, data_list):
        """
        Convert a list of facts to a NetworkX graph.
        
        Args:
            data_list: List of fact dictionaries
            
        Returns:
            nx.DiGraph: NetworkX directed graph
        """
        G = nx.DiGraph()
        
        # Add nodes for each fact
        for item in data_list:
            # Ensure fact_id exists
            if 'fact_id' not in item:
                continue
                
            # Add node with all attributes
            G.add_node(item['fact_id'], **item)
            
            # Add edges for related facts if they exist
            if 'related_facts' in item and item['related_facts']:
                for related_id in item['related_facts']:
                    G.add_edge(item['fact_id'], related_id, relationship_type="related")
        
        return G
    
    def serialize_to_json(self, output_file):
        """
        Serialize the graph to a JSON file using NetworkX's node-link format.
        
        Args:
            output_file: Path to save the serialized graph
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Convert graph to node-link data
            graph_data = nx.node_link_data(self.graph)
            
            # Write to file
            with open(output_file, 'w') as file:
                json.dump(graph_data, file, indent=4)
                
            return True
        except Exception as e:
            print(f"Error serializing graph to JSON: {e}")
            return False
    
    def deserialize_from_json(self, input_file):
        """
        Deserialize a graph from a JSON file.
        
        Args:
            input_file: Path to the serialized graph file
            
        Returns:
            nx.DiGraph: The deserialized graph or None if failed
        """
        try:
            # Read from file
            with open(input_file, 'r') as file:
                graph_data = json.load(file)
            
            # Convert node-link data to graph
            self.graph = nx.node_link_graph(graph_data, directed=True)
            
            return self.graph
        except Exception as e:
            print(f"Error deserializing graph from JSON: {e}")
            return None
    
    def serialize_sharded(self, output_dir, shard_size=100, prefix="kg_shard_"):
        """
        Serialize the graph to multiple sharded JSON files.
        
        Args:
            output_dir: Directory to save the sharded files
            shard_size: Number of nodes per shard
            prefix: Prefix for shard filenames
            
        Returns:
            list: Paths to the created shard files or empty list if failed
        """
        try:
            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            # Get all nodes
            nodes = list(self.graph.nodes(data=True))
            
            # Create shards
            shard_files = []
            for i in range(0, len(nodes), shard_size):
                # Get nodes for this shard
                shard_nodes = nodes[i:i+shard_size]
                
                # Create subgraph with these nodes
                subgraph = self.graph.subgraph([node for node, _ in shard_nodes])
                
                # Convert to node-link data
                graph_data = nx.node_link_data(subgraph)
                
                # Create shard filename
                shard_file = os.path.join(output_dir, f"{prefix}{i//shard_size}.json")
                
                # Write to file
                with open(shard_file, 'w') as file:
                    json.dump(graph_data, file, indent=4)
                
                shard_files.append(shard_file)
            
            # Create metadata file
            metadata = {
                "total_nodes": len(nodes),
                "shard_size": shard_size,
                "shard_count": len(shard_files),
                "shard_files": [os.path.basename(f) for f in shard_files]
            }
            
            metadata_file = os.path.join(output_dir, f"{prefix}metadata.json")
            with open(metadata_file, 'w') as file:
                json.dump(metadata, file, indent=4)
            
            return shard_files
        except Exception as e:
            print(f"Error serializing sharded graph: {e}")
            return []
    
    def deserialize_sharded(self, metadata_file):
        """
        Deserialize a graph from sharded JSON files.
        
        Args:
            metadata_file: Path to the metadata file
            
        Returns:
            nx.DiGraph: The combined graph or None if failed
        """
        try:
            # Read metadata
            with open(metadata_file, 'r') as file:
                metadata = json.load(file)
            
            # Get directory of metadata file
            directory = os.path.dirname(metadata_file)
            
            # Create empty graph
            combined_graph = nx.DiGraph()
            
            # Load each shard
            for shard_file in metadata["shard_files"]:
                # Get full path
                full_path = os.path.join(directory, shard_file)
                
                # Deserialize shard
                with open(full_path, 'r') as file:
                    shard_data = json.load(file)
                
                # Convert to graph
                shard_graph = nx.node_link_graph(shard_data, directed=True)
                
                # Add to combined graph
                combined_graph.add_nodes_from(shard_graph.nodes(data=True))
                combined_graph.add_edges_from(shard_graph.edges(data=True))
            
            self.graph = combined_graph
            return combined_graph
        except Exception as e:
            print(f"Error deserializing sharded graph: {e}")
            return None


def serialize_knowledge_graph(knowledge_graph, output_file):
    """
    Convenience function to serialize a knowledge graph to JSON.
    
    Args:
        knowledge_graph: KnowledgeGraph instance
        output_file: Path to save the serialized graph
        
    Returns:
        bool: True if successful, False otherwise
    """
    portable = KnowledgeGraphPortable(knowledge_graph)
    return portable.serialize_to_json(output_file)


def deserialize_knowledge_graph(input_file, knowledge_graph_class=None):
    """
    Convenience function to deserialize a knowledge graph from JSON.
    
    Args:
        input_file: Path to the serialized graph file
        knowledge_graph_class: Optional class to instantiate (must have a graph attribute)
        
    Returns:
        object: KnowledgeGraph instance or NetworkX graph
    """
    portable = KnowledgeGraphPortable(nx.DiGraph())
    graph = portable.deserialize_from_json(input_file)
    
    if knowledge_graph_class is not None:
        # Create instance of the provided class
        kg = knowledge_graph_class()
        kg.graph = graph
        
        # Rebuild data list if the class has one
        if hasattr(kg, 'data'):
            kg.data = [dict(graph.nodes[node]) for node in graph.nodes]
        
        return kg
    
    return graph
