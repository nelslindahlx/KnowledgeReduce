#!/usr/bin/env python3
"""
Knowledge Stacking Algorithm for KnowledgeReduce

This module implements the knowledge stacking algorithm of the KnowledgeReduce framework,
which is responsible for aggregating extracted facts, resolving conflicts,
and synthesizing a comprehensive knowledge graph.
"""

import os
import json
import networkx as nx
from typing import List, Dict, Tuple, Any, Optional, Set
from collections import defaultdict

class EntityAggregator:
    """
    Component for aggregating information about the same entities from different sources.
    """
    
    def __init__(self):
        """
        Initialize the entity aggregator.
        """
        pass
    
    def aggregate_entities(self, entity_sets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate entities from multiple sets.
        
        Args:
            entity_sets: List of entity sets to aggregate
            
        Returns:
            Dictionary containing aggregated entities
        """
        aggregated_entities = {}
        
        # Process each entity set
        for entity_set in entity_sets:
            for entity in entity_set.get('nodes', []):
                entity_id = entity['id']
                
                if entity_id in aggregated_entities:
                    # Update existing entity
                    aggregated_entities[entity_id]['mentions'] += entity.get('mentions', 1)
                    
                    # Merge any additional attributes
                    for key, value in entity.items():
                        if key not in ['id', 'text', 'type', 'mentions']:
                            if key not in aggregated_entities[entity_id]:
                                aggregated_entities[entity_id][key] = value
                            elif isinstance(value, list) and isinstance(aggregated_entities[entity_id][key], list):
                                # Merge lists without duplicates
                                aggregated_entities[entity_id][key] = list(set(aggregated_entities[entity_id][key] + value))
                else:
                    # Add new entity
                    aggregated_entities[entity_id] = entity.copy()
        
        return aggregated_entities


class ConflictResolver:
    """
    Component for resolving conflicts between different sources of information.
    """
    
    def __init__(self, trust_scores: Dict[str, float] = None):
        """
        Initialize the conflict resolver.
        
        Args:
            trust_scores: Dictionary mapping source IDs to trust scores
        """
        self.trust_scores = trust_scores or {}
        self.default_trust_score = 0.5
    
    def resolve_conflicts(self, edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Resolve conflicts between edges.
        
        Args:
            edges: List of edges to resolve conflicts for
            
        Returns:
            List of resolved edges
        """
        # Group edges by source and target
        edge_groups = defaultdict(list)
        for edge in edges:
            key = (edge['source'], edge['target'])
            edge_groups[key].append(edge)
        
        resolved_edges = []
        
        # Process each group of edges
        for key, group in edge_groups.items():
            if len(group) == 1:
                # No conflict, add the edge as is
                resolved_edges.append(group[0])
            else:
                # Resolve conflict using majority voting and trust scores
                type_counts = defaultdict(float)
                for edge in group:
                    edge_type = edge['type']
                    source = edge.get('source_id', 'unknown')
                    trust_score = self.trust_scores.get(source, self.default_trust_score)
                    type_counts[edge_type] += trust_score
                
                # Find the edge type with the highest score
                best_type = max(type_counts.items(), key=lambda x: x[1])[0]
                
                # Create a new edge with the resolved type
                resolved_edge = group[0].copy()
                resolved_edge['type'] = best_type
                resolved_edge['confidence'] = type_counts[best_type] / sum(type_counts.values())
                
                # Add sources information
                sources = [edge.get('source_id', 'unknown') for edge in group]
                resolved_edge['sources'] = list(set(sources))
                
                resolved_edges.append(resolved_edge)
        
        return resolved_edges


class GraphSynthesizer:
    """
    Component for synthesizing a knowledge graph from aggregated entities and relationships.
    """
    
    def __init__(self):
        """
        Initialize the graph synthesizer.
        """
        self.graph = nx.DiGraph()
    
    def create_graph(self, entities: Dict[str, Any], edges: List[Dict[str, Any]]) -> nx.DiGraph:
        """
        Create a knowledge graph from entities and edges.
        
        Args:
            entities: Dictionary of aggregated entities
            edges: List of resolved edges
            
        Returns:
            NetworkX DiGraph representing the knowledge graph
        """
        # Create a new graph
        self.graph = nx.DiGraph()
        
        # Add nodes
        for entity_id, entity in entities.items():
            self.graph.add_node(entity_id, **entity)
        
        # Add edges
        for edge in edges:
            source = edge['source']
            target = edge['target']
            
            # Skip edges with missing nodes
            if source not in self.graph or target not in self.graph:
                continue
            
            # Add the edge with its attributes
            edge_attrs = {k: v for k, v in edge.items() if k not in ['source', 'target']}
            self.graph.add_edge(source, target, **edge_attrs)
        
        return self.graph
    
    def export_graph_json(self, output_file: str) -> None:
        """
        Export the knowledge graph to a JSON file.
        
        Args:
            output_file: Path to the output file
        """
        # Convert the graph to a dictionary
        graph_dict = {
            'nodes': [],
            'edges': []
        }
        
        # Add nodes
        for node_id, node_data in self.graph.nodes(data=True):
            node_dict = {'id': node_id}
            node_dict.update(node_data)
            graph_dict['nodes'].append(node_dict)
        
        # Add edges
        for source, target, edge_data in self.graph.edges(data=True):
            edge_dict = {
                'source': source,
                'target': target
            }
            edge_dict.update(edge_data)
            graph_dict['edges'].append(edge_dict)
        
        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(graph_dict, f, indent=2)


class KnowledgeStacker:
    """
    Main class for stacking knowledge from multiple sources, combining entity aggregation,
    conflict resolution, and graph synthesis.
    """
    
    def __init__(self, trust_scores: Dict[str, float] = None):
        """
        Initialize the knowledge stacker.
        
        Args:
            trust_scores: Dictionary mapping source IDs to trust scores
        """
        self.entity_aggregator = EntityAggregator()
        self.conflict_resolver = ConflictResolver(trust_scores)
        self.graph_synthesizer = GraphSynthesizer()
    
    def stack_knowledge(self, fact_sets: List[Dict[str, Any]]) -> nx.DiGraph:
        """
        Stack knowledge from multiple fact sets.
        
        Args:
            fact_sets: List of fact sets to stack
            
        Returns:
            NetworkX DiGraph representing the stacked knowledge graph
        """
        # Aggregate entities
        aggregated_entities = self.entity_aggregator.aggregate_entities(fact_sets)
        
        # Collect all edges
        all_edges = []
        for fact_set in fact_sets:
            all_edges.extend(fact_set.get('edges', []))
        
        # Resolve conflicts
        resolved_edges = self.conflict_resolver.resolve_conflicts(all_edges)
        
        # Synthesize graph
        knowledge_graph = self.graph_synthesizer.create_graph(aggregated_entities, resolved_edges)
        
        return knowledge_graph
    
    def stack_knowledge_from_files(self, file_paths: List[str]) -> nx.DiGraph:
        """
        Stack knowledge from multiple JSON files.
        
        Args:
            file_paths: List of paths to JSON files containing fact sets
            
        Returns:
            NetworkX DiGraph representing the stacked knowledge graph
        """
        fact_sets = []
        
        for file_path in file_paths:
            with open(file_path, 'r', encoding='utf-8') as f:
                fact_set = json.load(f)
                fact_sets.append(fact_set)
        
        return self.stack_knowledge(fact_sets)
    
    def export_graph(self, output_file: str) -> None:
        """
        Export the knowledge graph to a JSON file.
        
        Args:
            output_file: Path to the output file
        """
        self.graph_synthesizer.export_graph_json(output_file)


# Example usage
if __name__ == "__main__":
    # Create knowledge stacker
    knowledge_stacker = KnowledgeStacker()
    
    # Example fact sets
    fact_set1 = {
        'nodes': [
            {'id': 'person:john_doe', 'text': 'John Doe', 'type': 'person', 'mentions': 2},
            {'id': 'organization:acme_corp', 'text': 'Acme Corp', 'type': 'organization', 'mentions': 1}
        ],
        'edges': [
            {'source': 'person:john_doe', 'target': 'organization:acme_corp', 'type': 'work_for'}
        ]
    }
    
    fact_set2 = {
        'nodes': [
            {'id': 'person:john_doe', 'text': 'John Doe', 'type': 'person', 'mentions': 1},
            {'id': 'location:new_york', 'text': 'New York', 'type': 'location', 'mentions': 1}
        ],
        'edges': [
            {'source': 'person:john_doe', 'target': 'location:new_york', 'type': 'live_in'}
        ]
    }
    
    # Stack knowledge
    knowledge_graph = knowledge_stacker.stack_knowledge([fact_set1, fact_set2])
    
    # Print graph information
    print(f"Knowledge graph has {knowledge_graph.number_of_nodes()} nodes and {knowledge_graph.number_of_edges()} edges")
