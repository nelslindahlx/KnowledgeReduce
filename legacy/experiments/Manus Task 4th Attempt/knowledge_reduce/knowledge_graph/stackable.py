"""
Stackable Knowledge module for KnowledgeReduce.

This module provides specialized data structures and algorithms for implementing
the stackable knowledge concept in the KnowledgeReduce framework.
"""

from typing import Dict, List, Any, Optional, Union, Set
import os
import json
import logging
from datetime import datetime
import networkx as nx

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KnowledgeStack:
    """
    Class representing a stack of knowledge in the KnowledgeReduce framework.
    
    A knowledge stack is a collection of entities and relationships that form a
    coherent unit of knowledge, which can be layered with other stacks.
    """
    
    def __init__(self, name: str, description: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize a KnowledgeStack.
        
        Args:
            name: Name of the knowledge stack.
            description: Optional description of the knowledge stack.
            metadata: Optional metadata for the knowledge stack.
        """
        self.name = name
        self.description = description
        self.metadata = metadata or {}
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.entities = set()
        self.relationships = set()
        self.parent_stacks = set()
        self.child_stacks = set()
        self.confidence_level = 1.0  # Default confidence level
        logger.info(f"KnowledgeStack initialized: {name}")
    
    def add_entity(self, entity_id: str):
        """
        Add an entity to the stack.
        
        Args:
            entity_id: ID of the entity to add.
        """
        self.entities.add(entity_id)
        self.updated_at = datetime.now().isoformat()
    
    def add_relationship(self, relationship_id: str):
        """
        Add a relationship to the stack.
        
        Args:
            relationship_id: ID of the relationship to add.
        """
        self.relationships.add(relationship_id)
        self.updated_at = datetime.now().isoformat()
    
    def add_parent_stack(self, stack_name: str):
        """
        Add a parent stack to this stack.
        
        Args:
            stack_name: Name of the parent stack.
        """
        self.parent_stacks.add(stack_name)
        self.updated_at = datetime.now().isoformat()
    
    def add_child_stack(self, stack_name: str):
        """
        Add a child stack to this stack.
        
        Args:
            stack_name: Name of the child stack.
        """
        self.child_stacks.add(stack_name)
        self.updated_at = datetime.now().isoformat()
    
    def set_confidence_level(self, confidence_level: float):
        """
        Set the confidence level of the stack.
        
        Args:
            confidence_level: Confidence level between 0 and 1.
        """
        if confidence_level < 0 or confidence_level > 1:
            raise ValueError("Confidence level must be between 0 and 1")
        
        self.confidence_level = confidence_level
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self):
        """
        Convert the KnowledgeStack to a dictionary for serialization.
        
        Returns:
            Dictionary representation of the KnowledgeStack.
        """
        return {
            'name': self.name,
            'description': self.description,
            'metadata': self.metadata,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'entities': list(self.entities),
            'relationships': list(self.relationships),
            'parent_stacks': list(self.parent_stacks),
            'child_stacks': list(self.child_stacks),
            'confidence_level': self.confidence_level
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """
        Create a KnowledgeStack from a dictionary.
        
        Args:
            data: Dictionary representation of a KnowledgeStack.
            
        Returns:
            KnowledgeStack object.
        """
        stack = cls(data['name'], data.get('description'), data.get('metadata', {}))
        stack.created_at = data.get('created_at', stack.created_at)
        stack.updated_at = data.get('updated_at', stack.updated_at)
        stack.entities = set(data.get('entities', []))
        stack.relationships = set(data.get('relationships', []))
        stack.parent_stacks = set(data.get('parent_stacks', []))
        stack.child_stacks = set(data.get('child_stacks', []))
        stack.confidence_level = data.get('confidence_level', 1.0)
        return stack


class StackableKnowledgeManager:
    """
    Manager class for stackable knowledge in the KnowledgeReduce framework.
    
    This class handles the creation, management, and operations on knowledge stacks.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize a StackableKnowledgeManager.
        
        Args:
            config: Optional configuration dictionary for customizing stackable knowledge behavior.
        """
        self.config = config or {}
        self.stacks = {}
        self.current_stack = None
        self.graph = nx.MultiDiGraph()  # Graph of stack relationships
        logger.info("StackableKnowledgeManager initialized")
    
    def create_stack(self, name: str, description: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        """
        Create a new knowledge stack.
        
        Args:
            name: Name of the knowledge stack.
            description: Optional description of the knowledge stack.
            metadata: Optional metadata for the knowledge stack.
            
        Returns:
            The created knowledge stack.
        """
        logger.info(f"Creating knowledge stack: {name}")
        
        if name in self.stacks:
            logger.warning(f"Stack {name} already exists, returning existing stack")
            return self.stacks[name]
        
        stack = KnowledgeStack(name, description, metadata)
        self.stacks[name] = stack
        self.current_stack = name
        
        # Add stack to the stack relationship graph
        self.graph.add_node(name, **stack.metadata)
        
        logger.info(f"Knowledge stack created: {name}")
        return stack
    
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
    
    def add_to_current_stack(self, entities: List[Dict[str, Any]], relationships: List[Dict[str, Any]]):
        """
        Add entities and relationships to the current stack.
        
        Args:
            entities: List of entities to add.
            relationships: List of relationships to add.
        """
        if not self.current_stack:
            logger.warning("No current stack set, creating default stack")
            self.create_stack("default")
        
        stack = self.stacks[self.current_stack]
        
        # Add entity IDs to stack
        for entity in entities:
            entity_id = entity.get('id')
            if entity_id:
                stack.add_entity(entity_id)
        
        # Add relationship IDs to stack
        for relationship in relationships:
            relationship_id = relationship.get('id')
            if relationship_id:
                stack.add_relationship(relationship_id)
        
        logger.info(f"Added {len(entities)} entities and {len(relationships)} relationships to stack {self.current_stack}")
    
    def create_stack_hierarchy(self, parent_name: str, child_name: str):
        """
        Create a hierarchical relationship between two stacks.
        
        Args:
            parent_name: Name of the parent stack.
            child_name: Name of the child stack.
        """
        if parent_name not in self.stacks:
            logger.warning(f"Parent stack {parent_name} does not exist, creating it")
            self.create_stack(parent_name)
        
        if child_name not in self.stacks:
            logger.warning(f"Child stack {child_name} does not exist, creating it")
            self.create_stack(child_name)
        
        parent_stack = self.stacks[parent_name]
        child_stack = self.stacks[child_name]
        
        parent_stack.add_child_stack(child_name)
        child_stack.add_parent_stack(parent_name)
        
        # Update the stack relationship graph
        self.graph.add_edge(parent_name, child_name, type='parent_of')
        
        logger.info(f"Created stack hierarchy: {parent_name} -> {child_name}")
    
    def merge_stacks(self, stack_names: List[str], new_stack_name: str, merge_type: str = 'union'):
        """
        Merge multiple knowledge stacks into a new stack.
        
        Args:
            stack_names: List of stack names to merge.
            new_stack_name: Name of the new merged stack.
            merge_type: Type of merge operation ('union', 'intersection', 'difference').
            
        Returns:
            The merged knowledge stack.
        """
        logger.info(f"Merging stacks {stack_names} into {new_stack_name} using {merge_type}")
        
        if not stack_names:
            logger.warning("No stacks to merge")
            return None
        
        # Check if all stacks exist
        for stack_name in stack_names:
            if stack_name not in self.stacks:
                logger.warning(f"Stack {stack_name} does not exist, skipping merge")
                return None
        
        # Create new stack
        merged_stack = self.create_stack(new_stack_name)
        
        # Get the first stack as the base
        base_stack = self.stacks[stack_names[0]]
        
        # Initialize merged entities and relationships
        if merge_type == 'union':
            # Union: include all entities and relationships from all stacks
            merged_entities = set(base_stack.entities)
            merged_relationships = set(base_stack.relationships)
            
            for stack_name in stack_names[1:]:
                stack = self.stacks[stack_name]
                merged_entities.update(stack.entities)
                merged_relationships.update(stack.relationships)
        
        elif merge_type == 'intersection':
            # Intersection: include only entities and relationships that are in all stacks
            merged_entities = set(base_stack.entities)
            merged_relationships = set(base_stack.relationships)
            
            for stack_name in stack_names[1:]:
                stack = self.stacks[stack_name]
                merged_entities.intersection_update(stack.entities)
                merged_relationships.intersection_update(stack.relationships)
        
        elif merge_type == 'difference':
            # Difference: include only entities and relationships that are in the first stack but not in others
            merged_entities = set(base_stack.entities)
            merged_relationships = set(base_stack.relationships)
            
            for stack_name in stack_names[1:]:
                stack = self.stacks[stack_name]
                merged_entities.difference_update(stack.entities)
                merged_relationships.difference_update(stack.relationships)
        
        else:
            raise ValueError(f"Unsupported merge type: {merge_type}")
        
        # Update the merged stack
        merged_stack.entities = merged_entities
        merged_stack.relationships = merged_relationships
        
        # Create relationships between the merged stack and its source stacks
        for stack_name in stack_names:
            self.graph.add_edge(stack_name, new_stack_name, type='merged_into')
            self.stacks[stack_name].add_child_stack(new_stack_name)
            merged_stack.add_parent_stack(stack_name)
        
        logger.info(f"Merged {len(stack_names)} stacks into {new_stack_name}")
        return merged_stack
    
    def filter_stack(self, stack_name: str, filter_criteria: Dict[str, Any], new_stack_name: str):
        """
        Create a new stack by filtering an existing stack.
        
        Args:
            stack_name: Name of the stack to filter.
            filter_criteria: Criteria for filtering entities and relationships.
            new_stack_name: Name of the new filtered stack.
            
        Returns:
            The filtered knowledge stack.
        """
        if stack_name not in self.stacks:
            logger.warning(f"Stack {stack_name} does not exist")
            return None
        
        logger.info(f"Filtering stack {stack_name} into {new_stack_name}")
        
        source_stack = self.stacks[stack_name]
        filtered_stack = self.create_stack(new_stack_name)
        
        # Create relationship between the source and filtered stacks
        self.graph.add_edge(stack_name, new_stack_name, type='filtered_into')
        source_stack.add_child_stack(new_stack_name)
        filtered_stack.add_parent_stack(stack_name)
        
        # TODO: Implement actual filtering based on criteria
        # This would require access to the actual entity and relationship data
        # For now, just copy all entities and relationships
        filtered_stack.entities = set(source_stack.entities)
        filtered_stack.relationships = set(source_stack.relationships)
        
        logger.info(f"Filtered stack {stack_name} into {new_stack_name}")
        return filtered_stack
    
    def get_stack_hierarchy(self, stack_name: str):
        """
        Get the hierarchy of a stack (parents and children).
        
        Args:
            stack_name: Name of the stack.
            
        Returns:
            Dictionary containing parent and child stacks.
        """
        if stack_name not in self.stacks:
            logger.warning(f"Stack {stack_name} does not exist")
            return None
        
        stack = self.stacks[stack_name]
        
        return {
            'name': stack_name,
            'parents': list(stack.parent_stacks),
            'children': list(stack.child_stacks)
        }
    
    def get_stack_lineage(self, stack_name: str):
        """
        Get the complete lineage of a stack (all ancestors and descendants).
        
        Args:
            stack_name: Name of the stack.
            
        Returns:
            Dictionary containing all ancestor and descendant stacks.
        """
        if stack_name not in self.stacks:
            logger.warning(f"Stack {stack_name} does not exist")
            return None
        
        # Get all ancestors (predecessors in the graph)
        ancestors = list(nx.ancestors(self.graph, stack_name))
        
        # Get all descendants (successors in the graph)
        descendants = list(nx.descendants(self.graph, stack_name))
        
        return {
            'name': stack_name,
            'ancestors': ancestors,
            'descendants': descendants
        }
    
    def visualize_stack_hierarchy(self, output_path: str):
        """
        Visualize the stack hierarchy as a graph.
        
        Args:
            output_path: Path where the visualization will be saved.
            
        Returns:
            Path to the visualization file.
        """
        import matplotlib.pyplot as plt
        
        logger.info(f"Visualizing stack hierarchy to {output_path}")
        
        plt.figure(figsize=(12, 8))
        pos = nx.spring_layout(self.graph)
        
        # Draw nodes
        nx.draw_networkx_nodes(self.graph, pos, node_size=500, node_color='lightblue')
        
        # Draw edges
        nx.draw_networkx_edges(self.graph, pos, width=1.0, alpha=0.5)
        
        # Draw labels
        nx.draw_networkx_labels(self.graph, pos, font_size=10, font_family='sans-serif')
        
        # Draw edge labels
        edge_labels = {(u, v): d['type'] for u, v, d in self.graph.edges(data=True)}
        nx.draw_networkx_edge_labels(self.graph, pos, edge_labels=edge_labels, font_size=8)
        
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(output_path)
        plt.close()
        
        logger.info(f"Stack hierarchy visualization saved to {output_path}")
        return output_path
    
    def save_state(self, path: str):
        """
        Save the current state of the StackableKnowledgeManager.
        
        Args:
            path: Directory path where the state will be saved.
        """
        os.makedirs(path, exist_ok=True)
        
        # Save configuration
        with open(os.path.join(path, 'config.json'), 'w') as f:
            json.dump(self.config, f, indent=2)
        
        # Save stacks
        stacks_data = {}
        for name, stack in self.stacks.items():
            stacks_data[name] = stack.to_dict()
        
        with open(os.path.join(path, 'stacks.json'), 'w') as f:
            json.dump(stacks_data, f, indent=2)
        
        # Save current stack
        with open(os.path.join(path, 'current_stack.txt'), 'w') as f:
            f.write(self.current_stack or '')
        
        # Save stack relationship graph
        nx.write_graphml(self.graph, os.path.join(path, 'stack_graph.graphml'))
        
        logger.info(f"StackableKnowledgeManager state saved to {path}")
    
    def load_state(self, path: str):
        """
        Load a previously saved state of the StackableKnowledgeManager.
        
        Args:
            path: Directory path where the state was saved.
        """
        # Load configuration
        with open(os.path.join(path, 'config.json'), 'r') as f:
            self.config = json.load(f)
        
        # Load stacks
        with open(os.path.join(path, 'stacks.json'), 'r') as f:
            stacks_data = json.load(f)
        
        self.stacks = {}
        for name, stack_data in stacks_data.items():
            self.stacks[name] = KnowledgeStack.from_dict(stack_data)
        
        # Load current stack
        with open(os.path.join(path, 'current_stack.txt'), 'r') as f:
            self.current_stack = f.read().strip() or None
        
        # Load stack relationship graph
        self.graph = nx.read_graphml(os.path.join(path, 'stack_graph.graphml'))
        
        logger.info(f"StackableKnowledgeManager state loaded from {path}")
