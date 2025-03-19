"""
Knowledge Graph module for KnowledgeReduce.

This module handles the storage, management, and querying of the knowledge graph
for the KnowledgeReduce framework, with special support for stackable knowledge.
"""

from typing import Dict, List, Any, Optional, Union
import os
import json
import logging
import networkx as nx
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KnowledgeGraph:
    """
    Class for managing the knowledge graph in the KnowledgeReduce framework.
    
    This class handles the storage, management, and querying of the knowledge graph,
    with special support for stackable knowledge.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the KnowledgeGraph.
        
        Args:
            config: Optional configuration dictionary for customizing knowledge graph behavior.
        """
        self.config = config or {}
        self.graph = nx.MultiDiGraph()
        self.stacks = {}
        self.current_stack = None
        logger.info("KnowledgeGraph initialized")
    
    def build(self, reduced_data: Dict[str, Any]):
        """
        Build the knowledge graph from reduced data.
        
        Args:
            reduced_data: Dictionary containing entities and relationships from the reducing phase.
        """
        logger.info("Building knowledge graph")
        
        entities = reduced_data.get('entities', [])
        relationships = reduced_data.get('relationships', [])
        
        # Clear existing graph if not in append mode
        if not self.config.get('append_mode', False):
            self.graph = nx.MultiDiGraph()
        
        # Add entities as nodes
        for entity in entities:
            entity_id = entity.get('id')
            if entity_id:
                self.graph.add_node(entity_id, **entity)
        
        # Add relationships as edges
        for relationship in relationships:
            source_id = relationship.get('source')
            target_id = relationship.get('target')
            rel_type = relationship.get('type')
            
            if source_id and target_id and rel_type:
                self.graph.add_edge(source_id, target_id, key=rel_type, **relationship)
        
        # If a current stack is set, associate the new data with it
        if self.current_stack:
            self._add_to_stack(self.current_stack, entities, relationships)
        
        logger.info(f"Knowledge graph built with {len(entities)} entities and {len(relationships)} relationships")
    
    def query(self, query_string: str, params: Optional[Dict[str, Any]] = None):
        """
        Query the knowledge graph.
        
        Args:
            query_string: Query string in a graph query language.
            params: Optional parameters for the query.
            
        Returns:
            Query results.
        """
        logger.info(f"Querying knowledge graph: {query_string}")
        
        # This is a simplified implementation
        # In a real implementation, you would use a graph query language parser
        
        if query_string.startswith("MATCH"):
            return self._execute_match_query(query_string, params)
        elif query_string.startswith("FIND"):
            return self._execute_find_query(query_string, params)
        else:
            raise ValueError(f"Unsupported query type: {query_string}")
    
    def _execute_match_query(self, query_string, params):
        """
        Execute a MATCH query.
        
        Args:
            query_string: MATCH query string.
            params: Optional parameters for the query.
            
        Returns:
            Query results.
        """
        # This is a simplified implementation
        # In a real implementation, you would parse the query and execute it
        
        # Example: MATCH (n:Person) RETURN n
        # Example: MATCH (n)-[r:KNOWS]->(m) RETURN n, r, m
        
        # For now, just return a subset of nodes and edges
        results = {
            'nodes': [],
            'edges': []
        }
        
        # Get nodes
        for node_id, node_data in self.graph.nodes(data=True):
            results['nodes'].append({
                'id': node_id,
                **node_data
            })
        
        # Get edges
        for source, target, key, edge_data in self.graph.edges(data=True, keys=True):
            results['edges'].append({
                'source': source,
                'target': target,
                'type': key,
                **edge_data
            })
        
        return results
    
    def _execute_find_query(self, query_string, params):
        """
        Execute a FIND query.
        
        Args:
            query_string: FIND query string.
            params: Optional parameters for the query.
            
        Returns:
            Query results.
        """
        # This is a simplified implementation
        # In a real implementation, you would parse the query and execute it
        
        # Example: FIND ENTITY WHERE type = 'Person'
        # Example: FIND RELATIONSHIP WHERE type = 'KNOWS'
        
        # For now, just return a subset of nodes or edges
        if "ENTITY" in query_string:
            results = []
            for node_id, node_data in self.graph.nodes(data=True):
                results.append({
                    'id': node_id,
                    **node_data
                })
            return results
        elif "RELATIONSHIP" in query_string:
            results = []
            for source, target, key, edge_data in self.graph.edges(data=True, keys=True):
                results.append({
                    'source': source,
                    'target': target,
                    'type': key,
                    **edge_data
                })
            return results
        else:
            raise ValueError(f"Unsupported FIND query: {query_string}")
    
    def export(self, output_path: str, format: str = 'graphml'):
        """
        Export the knowledge graph to a file.
        
        Args:
            output_path: Path where the exported file will be saved.
            format: Format of the exported file (e.g., 'graphml', 'json', 'gexf').
            
        Returns:
            Path to the exported file.
        """
        logger.info(f"Exporting knowledge graph to {output_path} in {format} format")
        
        if format == 'graphml':
            nx.write_graphml(self.graph, output_path)
        elif format == 'json':
            data = nx.node_link_data(self.graph)
            with open(output_path, 'w') as f:
                json.dump(data, f, indent=2)
        elif format == 'gexf':
            nx.write_gexf(self.graph, output_path)
        else:
            raise ValueError(f"Unsupported export format: {format}")
        
        logger.info(f"Knowledge graph exported to {output_path}")
        return output_path
    
    def create_stack(self, name: str, description: Optional[str] = None):
        """
        Create a new knowledge stack.
        
        Args:
            name: Name of the knowledge stack.
            description: Optional description of the knowledge stack.
            
        Returns:
            The created knowledge stack.
        """
        logger.info(f"Creating knowledge stack: {name}")
        
        if name in self.stacks:
            logger.warning(f"Stack {name} already exists, returning existing stack")
            return self.stacks[name]
        
        stack = {
            'name': name,
            'description': description,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'entities': set(),
            'relationships': set(),
            'metadata': {}
        }
        
        self.stacks[name] = stack
        self.current_stack = name
        
        logger.info(f"Knowledge stack created: {name}")
        return stack
    
    def _add_to_stack(self, stack_name: str, entities: List[Dict[str, Any]], relationships: List[Dict[str, Any]]):
        """
        Add entities and relationships to a stack.
        
        Args:
            stack_name: Name of the stack to add to.
            entities: List of entities to add.
            relationships: List of relationships to add.
        """
        if stack_name not in self.stacks:
            logger.warning(f"Stack {stack_name} does not exist, creating it")
            self.create_stack(stack_name)
        
        stack = self.stacks[stack_name]
        
        # Add entity IDs to stack
        for entity in entities:
            entity_id = entity.get('id')
            if entity_id:
                stack['entities'].add(entity_id)
        
        # Add relationship IDs to stack
        for relationship in relationships:
            relationship_id = relationship.get('id')
            if relationship_id:
                stack['relationships'].add(relationship_id)
        
        stack['updated_at'] = datetime.now().isoformat()
        
        logger.info(f"Added {len(entities)} entities and {len(relationships)} relationships to stack {stack_name}")
    
    def get_stack(self, name: str):
        """
        Get a knowledge stack by name.
        
        Args:
            name: Name of the knowledge stack.
            
        Returns:
            The knowledge stack.
        """
        if name not in self.stacks:
            logger.warning(f"Stack {name} does not exist")
            return None
        
        return self.stacks[name]
    
    def set_current_stack(self, name: str):
        """
        Set the current knowledge stack.
        
        Args:
            name: Name of the knowledge stack.
        """
        if name not in self.stacks:
            logger.warning(f"Stack {name} does not exist, creating it")
            self.create_stack(name)
        
        self.current_stack = name
        logger.info(f"Current stack set to: {name}")
    
    def merge_stacks(self, stack_names: List[str], new_stack_name: str):
        """
        Merge multiple knowledge stacks into a new stack.
        
        Args:
            stack_names: List of stack names to merge.
            new_stack_name: Name of the new merged stack.
            
        Returns:
            The merged knowledge stack.
        """
        logger.info(f"Merging stacks {stack_names} into {new_stack_name}")
        
        # Create new stack
        merged_stack = self.create_stack(new_stack_name)
        
        # Merge entities and relationships from all stacks
        for stack_name in stack_names:
            if stack_name not in self.stacks:
                logger.warning(f"Stack {stack_name} does not exist, skipping")
                continue
            
            stack = self.stacks[stack_name]
            merged_stack['entities'].update(stack['entities'])
            merged_stack['relationships'].update(stack['relationships'])
        
        merged_stack['updated_at'] = datetime.now().isoformat()
        
        logger.info(f"Merged {len(stack_names)} stacks into {new_stack_name}")
        return merged_stack
    
    def get_stack_graph(self, stack_name: str):
        """
        Get a subgraph for a specific knowledge stack.
        
        Args:
            stack_name: Name of the knowledge stack.
            
        Returns:
            Subgraph for the specified stack.
        """
        if stack_name not in self.stacks:
            logger.warning(f"Stack {stack_name} does not exist")
            return None
        
        stack = self.stacks[stack_name]
        
        # Create a subgraph with the stack's entities
        subgraph = self.graph.subgraph(stack['entities'])
        
        logger.info(f"Created subgraph for stack {stack_name} with {len(subgraph.nodes)} nodes and {len(subgraph.edges)} edges")
        return subgraph
    
    def save_state(self, path: str):
        """
        Save the current state of the KnowledgeGraph.
        
        Args:
            path: Directory path where the state will be saved.
        """
        os.makedirs(path, exist_ok=True)
        
        # Save configuration
        with open(os.path.join(path, 'config.json'), 'w') as f:
            json.dump(self.config, f, indent=2)
        
        # Save graph
        nx.write_graphml(self.graph, os.path.join(path, 'graph.graphml'))
        
        # Save stacks
        serializable_stacks = {}
        for name, stack in self.stacks.items():
            serializable_stack = stack.copy()
            serializable_stack['entities'] = list(stack['entities'])
            serializable_stack['relationships'] = list(stack['relationships'])
            serializable_stacks[name] = serializable_stack
        
        with open(os.path.join(path, 'stacks.json'), 'w') as f:
            json.dump(serializable_stacks, f, indent=2)
        
        # Save current stack
        with open(os.path.join(path, 'current_stack.txt'), 'w') as f:
            f.write(self.current_stack or '')
        
        logger.info(f"KnowledgeGraph state saved to {path}")
    
    def load_state(self, path: str):
        """
        Load a previously saved state of the KnowledgeGraph.
        
        Args:
            path: Directory path where the state was saved.
        """
        # Load configuration
        with open(os.path.join(path, 'config.json'), 'r') as f:
            self.config = json.load(f)
        
        # Load graph
        self.graph = nx.read_graphml(os.path.join(path, 'graph.graphml'))
        
        # Load stacks
        with open(os.path.join(path, 'stacks.json'), 'r') as f:
            serializable_stacks = json.load(f)
        
        self.stacks = {}
        for name, serializable_stack in serializable_stacks.items():
            stack = serializable_stack.copy()
            stack['entities'] = set(serializable_stack['entities'])
            stack['relationships'] = set(serializable_stack['relationships'])
            self.stacks[name] = stack
        
        # Load current stack
        with open(os.path.join(path, 'current_stack.txt'), 'r') as f:
            self.current_stack = f.read().strip() or None
        
        logger.info(f"KnowledgeGraph state loaded from {path}")
