"""
Serialization module for knowledge graphs.
This module provides functions for serializing and deserializing knowledge graphs in various formats.
"""

import json
import os
import math
import networkx as nx
from datetime import datetime

class KnowledgeGraphSerializer:
    """
    Class for serializing and deserializing knowledge graphs in various formats.
    
    This class provides methods for converting knowledge graphs to and from
    different serialization formats, with support for sharding large graphs.
    """
    
    @staticmethod
    def to_json(knowledge_graph, filepath, shard_size=100):
        """
        Serialize a knowledge graph to JSON format with optional sharding.
        
        Args:
            knowledge_graph: The knowledge graph to serialize
            filepath (str): Base path for the JSON file(s)
            shard_size (int, optional): Number of nodes per shard. If 0, no sharding is used. Defaults to 100.
            
        Returns:
            list: List of file paths created
        """
        try:
            # Convert graph to a dictionary
            graph_data = nx.node_link_data(knowledge_graph.graph)
            
            # If no sharding is requested or graph is small enough
            if shard_size <= 0 or len(graph_data['nodes']) <= shard_size:
                with open(filepath, 'w') as file:
                    json.dump(graph_data, file, indent=2)
                return [filepath]
            
            # Sharding logic
            file_paths = []
            base_name, ext = os.path.splitext(filepath)
            
            # Calculate number of shards needed
            num_shards = math.ceil(len(graph_data['nodes']) / shard_size)
            
            # Create metadata file with sharding info
            metadata = {
                'total_nodes': len(graph_data['nodes']),
                'total_edges': len(graph_data['links']),
                'shard_size': shard_size,
                'num_shards': num_shards,
                'base_name': os.path.basename(base_name),
                'extension': ext
            }
            
            metadata_path = f"{base_name}_metadata{ext}"
            with open(metadata_path, 'w') as file:
                json.dump(metadata, file, indent=2)
            file_paths.append(metadata_path)
            
            # Create shards
            for i in range(num_shards):
                start_idx = i * shard_size
                end_idx = min((i + 1) * shard_size, len(graph_data['nodes']))
                
                # Get nodes for this shard
                shard_nodes = graph_data['nodes'][start_idx:end_idx]
                shard_node_ids = [node['id'] for node in shard_nodes]
                
                # Get edges that connect nodes in this shard
                shard_links = [link for link in graph_data['links'] 
                              if link['source'] in shard_node_ids or link['target'] in shard_node_ids]
                
                # Create shard data
                shard_data = {
                    'directed': graph_data['directed'],
                    'multigraph': graph_data['multigraph'],
                    'graph': graph_data['graph'],
                    'nodes': shard_nodes,
                    'links': shard_links,
                    'shard_info': {
                        'shard_number': i + 1,
                        'total_shards': num_shards,
                        'node_count': len(shard_nodes),
                        'link_count': len(shard_links)
                    }
                }
                
                # Write shard to file
                shard_path = f"{base_name}_shard_{i+1:03d}{ext}"
                with open(shard_path, 'w') as file:
                    json.dump(shard_data, file, indent=2)
                file_paths.append(shard_path)
            
            return file_paths
        except Exception as e:
            raise Exception(f"Error serializing to JSON: {e}")
    
    @staticmethod
    def from_json(filepath, knowledge_graph=None):
        """
        Deserialize a knowledge graph from JSON format, handling sharded files if necessary.
        
        Args:
            filepath (str): Path to the JSON file or metadata file for sharded graphs
            knowledge_graph: Optional existing knowledge graph to populate. If None, a new one is created.
            
        Returns:
            The deserialized knowledge graph
        """
        from ..core.core import KnowledgeGraph
        
        # Create a new knowledge graph if none provided
        if knowledge_graph is None:
            knowledge_graph = KnowledgeGraph()
        
        try:
            # Check if this is a metadata file for a sharded graph
            with open(filepath, 'r') as file:
                data = json.load(file)
            
            # If this is a metadata file
            if 'num_shards' in data and 'base_name' in data:
                # This is a metadata file for a sharded graph
                base_dir = os.path.dirname(filepath)
                base_name = data['base_name']
                ext = data['extension']
                num_shards = data['num_shards']
                
                # Initialize an empty graph
                combined_graph = {
                    'directed': True,
                    'multigraph': False,
                    'graph': {},
                    'nodes': [],
                    'links': []
                }
                
                # Load each shard and combine
                for i in range(num_shards):
                    shard_path = os.path.join(base_dir, f"{base_name}_shard_{i+1:03d}{ext}")
                    with open(shard_path, 'r') as shard_file:
                        shard_data = json.load(shard_file)
                    
                    # Add nodes and links from this shard
                    combined_graph['nodes'].extend(shard_data['nodes'])
                    combined_graph['links'].extend(shard_data['links'])
                    
                    # Update graph properties if needed
                    if i == 0:
                        combined_graph['directed'] = shard_data['directed']
                        combined_graph['multigraph'] = shard_data['multigraph']
                        combined_graph['graph'] = shard_data['graph']
                
                # Create graph from combined data
                knowledge_graph.graph = nx.node_link_graph(combined_graph)
            else:
                # This is a regular (non-sharded) JSON file
                knowledge_graph.graph = nx.node_link_graph(data)
            
            return knowledge_graph
        except Exception as e:
            raise Exception(f"Error deserializing from JSON: {e}")
    
    @staticmethod
    def to_gexf(knowledge_graph, filepath):
        """
        Serialize a knowledge graph to GEXF format.
        
        Args:
            knowledge_graph: The knowledge graph to serialize
            filepath (str): Path to save the GEXF file
            
        Returns:
            bool: True if serialization was successful
        """
        try:
            nx.write_gexf(knowledge_graph.graph, filepath)
            return True
        except Exception as e:
            raise Exception(f"Error serializing to GEXF: {e}")
    
    @staticmethod
    def from_gexf(filepath, knowledge_graph=None):
        """
        Deserialize a knowledge graph from GEXF format.
        
        Args:
            filepath (str): Path to the GEXF file
            knowledge_graph: Optional existing knowledge graph to populate. If None, a new one is created.
            
        Returns:
            The deserialized knowledge graph
        """
        from ..core.core import KnowledgeGraph
        
        # Create a new knowledge graph if none provided
        if knowledge_graph is None:
            knowledge_graph = KnowledgeGraph()
        
        try:
            knowledge_graph.graph = nx.read_gexf(filepath)
            return knowledge_graph
        except Exception as e:
            raise Exception(f"Error deserializing from GEXF: {e}")
    
    @staticmethod
    def to_graphml(knowledge_graph, filepath):
        """
        Serialize a knowledge graph to GraphML format.
        
        Args:
            knowledge_graph: The knowledge graph to serialize
            filepath (str): Path to save the GraphML file
            
        Returns:
            bool: True if serialization was successful
        """
        try:
            nx.write_graphml(knowledge_graph.graph, filepath)
            return True
        except Exception as e:
            raise Exception(f"Error serializing to GraphML: {e}")
    
    @staticmethod
    def from_graphml(filepath, knowledge_graph=None):
        """
        Deserialize a knowledge graph from GraphML format.
        
        Args:
            filepath (str): Path to the GraphML file
            knowledge_graph: Optional existing knowledge graph to populate. If None, a new one is created.
            
        Returns:
            The deserialized knowledge graph
        """
        from ..core.core import KnowledgeGraph
        
        # Create a new knowledge graph if none provided
        if knowledge_graph is None:
            knowledge_graph = KnowledgeGraph()
        
        try:
            knowledge_graph.graph = nx.read_graphml(filepath)
            return knowledge_graph
        except Exception as e:
            raise Exception(f"Error deserializing from GraphML: {e}")

class StackableKnowledgeGraphSerializer:
    """
    Class for serializing and deserializing stackable knowledge graphs.
    
    This class provides methods for converting stackable knowledge graphs to and from
    different serialization formats, preserving layer structure and inheritance rules.
    """
    
    @staticmethod
    def to_json(stackable_knowledge_graph, directory, shard_size=100):
        """
        Serialize a stackable knowledge graph to JSON format.
        
        Args:
            stackable_knowledge_graph: The stackable knowledge graph to serialize
            directory (str): Directory to save the JSON files
            shard_size (int, optional): Number of nodes per shard. Defaults to 100.
            
        Returns:
            dict: Dictionary mapping layer names to lists of file paths
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(directory, exist_ok=True)
            
            # Serialize metadata
            metadata = {
                'layer_order': stackable_knowledge_graph.layer_order,
                'inheritance_rules': stackable_knowledge_graph.inheritance_rules
            }
            
            metadata_path = os.path.join(directory, 'metadata.json')
            with open(metadata_path, 'w') as file:
                json.dump(metadata, file, indent=2)
            
            # Serialize each layer
            layer_files = {}
            for layer_name in stackable_knowledge_graph.layer_order:
                layer = stackable_knowledge_graph.layers[layer_name]
                layer_dir = os.path.join(directory, layer_name)
                os.makedirs(layer_dir, exist_ok=True)
                
                layer_path = os.path.join(layer_dir, f"{layer_name}.json")
                layer_files[layer_name] = KnowledgeGraphSerializer.to_json(layer, layer_path, shard_size)
            
            return layer_files
        except Exception as e:
            raise Exception(f"Error serializing stackable knowledge graph: {e}")
    
    @staticmethod
    def from_json(directory):
        """
        Deserialize a stackable knowledge graph from JSON format.
        
        Args:
            directory (str): Directory containing the JSON files
            
        Returns:
            The deserialized stackable knowledge graph
        """
        from ..core.core import StackableKnowledgeGraph, KnowledgeGraph
        
        try:
            # Create a new stackable knowledge graph
            stackable_kg = StackableKnowledgeGraph()
            
            # Load metadata
            metadata_path = os.path.join(directory, 'metadata.json')
            with open(metadata_path, 'r') as file:
                metadata = json.load(file)
            
            # Clear default layer
            stackable_kg.layers = {}
            stackable_kg.layer_order = []
            stackable_kg.inheritance_rules = {}
            
            # Set layer order and inheritance rules
            stackable_kg.layer_order = metadata['layer_order']
            stackable_kg.inheritance_rules = metadata['inheritance_rules']
            
            # Load each layer
            for layer_name in stackable_kg.layer_order:
                layer_dir = os.path.join(directory, layer_name)
                layer_path = os.path.join(layer_dir, f"{layer_name}.json")
                
                # Check if this is a regular file or a metadata file for shards
                if os.path.exists(layer_path):
                    # Regular file
                    stackable_kg.layers[layer_name] = KnowledgeGraphSerializer.from_json(layer_path)
                else:
                    # Check for metadata file
                    metadata_path = os.path.join(layer_dir, f"{layer_name}_metadata.json")
                    if os.path.exists(metadata_path):
                        stackable_kg.layers[layer_name] = KnowledgeGraphSerializer.from_json(metadata_path)
                    else:
                        # Create empty layer if files not found
                        stackable_kg.layers[layer_name] = KnowledgeGraph()
            
            return stackable_kg
        except Exception as e:
            raise Exception(f"Error deserializing stackable knowledge graph: {e}")
