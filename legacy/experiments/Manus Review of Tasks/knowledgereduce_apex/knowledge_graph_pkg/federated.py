"""
Federated knowledge graph with collaborative capabilities.

This module provides capabilities for federated knowledge graphs with
collaborative editing, permissions management, and synchronization.
"""

import uuid
import time
import json
import hashlib
from typing import Dict, List, Any, Union, Optional, Tuple, Set, Callable
from datetime import datetime
from .core import KnowledgeGraph, ReliabilityRating

class FederatedKnowledgeGraph:
    """
    Class for federated knowledge graph operations.
    
    This class provides methods for creating and managing federated knowledge
    graphs with collaborative editing and synchronization capabilities.
    
    Attributes:
        kg: The knowledge graph to enhance with federation capabilities
        node_id: Unique identifier for this node in the federation
        peers: Dictionary of peer nodes in the federation
        permissions: Dictionary of user permissions
        change_log: Log of changes for synchronization
    """
    
    def __init__(self, knowledge_graph: KnowledgeGraph, node_id: Optional[str] = None):
        """
        Initialize a FederatedKnowledgeGraph with a knowledge graph.
        
        Args:
            knowledge_graph: KnowledgeGraph instance to enhance
            node_id: Unique identifier for this node (generated if None)
        """
        self.kg = knowledge_graph
        self.node_id = node_id or str(uuid.uuid4())
        self.peers = {}
        self.permissions = {}
        self.change_log = []
        self.max_change_log = 1000
        self.users = {}
        self.user_sessions = {}
        
    def add_fact_collaborative(self, 
                             user_id: str,
                             fact_id: str, 
                             fact_statement: str, 
                             category: str, 
                             tags: List[str], 
                             reliability_rating: ReliabilityRating, 
                             source_id: str, 
                             **kwargs) -> Dict[str, Any]:
        """
        Add a fact with collaborative tracking.
        
        Args:
            user_id: ID of the user adding the fact
            fact_id: Unique identifier for the fact
            fact_statement: The actual fact statement
            category: Category of the fact
            tags: List of tags associated with the fact
            reliability_rating: ReliabilityRating enum value
            source_id: Identifier for the source
            **kwargs: Additional fact attributes
            
        Returns:
            Dictionary with fact and change information
        """
        # Check user permissions
        if not self._check_permission(user_id, 'add'):
            raise PermissionError(f"User {user_id} does not have permission to add facts")
            
        # Add the fact to the knowledge graph
        self.kg.add_fact(
            fact_id=fact_id,
            fact_statement=fact_statement,
            category=category,
            tags=tags,
            date_recorded=kwargs.get('date_recorded', datetime.now()),
            last_updated=kwargs.get('last_updated', datetime.now()),
            reliability_rating=reliability_rating,
            source_id=source_id,
            source_title=kwargs.get('source_title', ''),
            author_creator=kwargs.get('author_creator', ''),
            publication_date=kwargs.get('publication_date', datetime.now()),
            url_reference=kwargs.get('url_reference', ''),
            related_facts=kwargs.get('related_facts', []),
            contextual_notes=kwargs.get('contextual_notes', ''),
            access_level=kwargs.get('access_level', 'public'),
            usage_count=kwargs.get('usage_count', 0)
        )
        
        # Add collaborative metadata
        self.kg.update_fact(fact_id, 
                          created_by=user_id,
                          created_at=datetime.now().isoformat(),
                          last_modified_by=user_id,
                          last_modified_at=datetime.now().isoformat(),
                          node_id=self.node_id,
                          version=1)
        
        # Log the change
        change = {
            'id': str(uuid.uuid4()),
            'type': 'add_fact',
            'user_id': user_id,
            'fact_id': fact_id,
            'timestamp': datetime.now().isoformat(),
            'node_id': self.node_id,
            'data': {
                'fact_statement': fact_statement,
                'category': category,
                'tags': tags,
                'reliability_rating': reliability_rating.name,
                'source_id': source_id,
                **kwargs
            }
        }
        
        self._add_to_change_log(change)
        
        return {
            'fact_id': fact_id,
            'change_id': change['id'],
            'version': 1
        }
        
    def update_fact_collaborative(self, 
                                user_id: str,
                                fact_id: str, 
                                **updates) -> Dict[str, Any]:
        """
        Update a fact with collaborative tracking.
        
        Args:
            user_id: ID of the user updating the fact
            fact_id: ID of the fact to update
            **updates: Attributes to update
            
        Returns:
            Dictionary with update information
        """
        # Check user permissions
        if not self._check_permission(user_id, 'edit'):
            raise PermissionError(f"User {user_id} does not have permission to edit facts")
            
        # Get the current fact
        try:
            fact = self.kg.get_fact(fact_id)
        except Exception as e:
            raise ValueError(f"Fact not found: {e}")
            
        # Check if the user can edit this specific fact
        if 'access_level' in fact and fact['access_level'] == 'private':
            if 'created_by' in fact and fact['created_by'] != user_id:
                if not self._check_permission(user_id, 'admin'):
                    raise PermissionError(f"User {user_id} cannot edit private fact created by another user")
                    
        # Get current version
        current_version = fact.get('version', 1)
        new_version = current_version + 1
        
        # Update collaborative metadata
        updates['last_modified_by'] = user_id
        updates['last_modified_at'] = datetime.now().isoformat()
        updates['version'] = new_version
        
        # Update the fact
        self.kg.update_fact(fact_id, **updates)
        
        # Log the change
        change = {
            'id': str(uuid.uuid4()),
            'type': 'update_fact',
            'user_id': user_id,
            'fact_id': fact_id,
            'timestamp': datetime.now().isoformat(),
            'node_id': self.node_id,
            'data': updates,
            'previous_version': current_version,
            'new_version': new_version
        }
        
        self._add_to_change_log(change)
        
        return {
            'fact_id': fact_id,
            'change_id': change['id'],
            'version': new_version
        }
        
    def delete_fact_collaborative(self, 
                                user_id: str,
                                fact_id: str) -> Dict[str, Any]:
        """
        Delete a fact with collaborative tracking.
        
        Args:
            user_id: ID of the user deleting the fact
            fact_id: ID of the fact to delete
            
        Returns:
            Dictionary with deletion information
        """
        # Check user permissions
        if not self._check_permission(user_id, 'delete'):
            raise PermissionError(f"User {user_id} does not have permission to delete facts")
            
        # Get the current fact
        try:
            fact = self.kg.get_fact(fact_id)
        except Exception as e:
            raise ValueError(f"Fact not found: {e}")
            
        # Check if the user can delete this specific fact
        if 'access_level' in fact and fact['access_level'] == 'private':
            if 'created_by' in fact and fact['created_by'] != user_id:
                if not self._check_permission(user_id, 'admin'):
                    raise PermissionError(f"User {user_id} cannot delete private fact created by another user")
                    
        # Delete the fact
        self.kg.graph.remove_node(fact_id)
        
        # Log the change
        change = {
            'id': str(uuid.uuid4()),
            'type': 'delete_fact',
            'user_id': user_id,
            'fact_id': fact_id,
            'timestamp': datetime.now().isoformat(),
            'node_id': self.node_id,
            'data': {
                'fact_statement': fact.get('fact_statement', ''),
                'category': fact.get('category', ''),
                'version': fact.get('version', 1)
            }
        }
        
        self._add_to_change_log(change)
        
        return {
            'fact_id': fact_id,
            'change_id': change['id'],
            'status': 'deleted'
        }
        
    def register_user(self, 
                    user_id: str,
                    username: str,
                    role: str = 'contributor') -> Dict[str, Any]:
        """
        Register a user in the federated knowledge graph.
        
        Args:
            user_id: Unique identifier for the user
            username: Display name for the user
            role: Role of the user (admin, contributor, viewer)
            
        Returns:
            User information
        """
        # Create user record
        user = {
            'user_id': user_id,
            'username': username,
            'role': role,
            'registered_at': datetime.now().isoformat(),
            'registered_by_node': self.node_id,
            'last_active': datetime.now().isoformat()
        }
        
        # Add to users dictionary
        self.users[user_id] = user
        
        # Set permissions based on role
        self._set_role_permissions(user_id, role)
        
        return user
        
    def create_user_session(self, 
                          user_id: str) -> Dict[str, Any]:
        """
        Create a session for a user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Session information
        """
        # Check if user exists
        if user_id not in self.users:
            raise ValueError(f"User {user_id} not registered")
            
        # Create session
        session_id = str(uuid.uuid4())
        session = {
            'session_id': session_id,
            'user_id': user_id,
            'created_at': datetime.now().isoformat(),
            'last_active': datetime.now().isoformat(),
            'node_id': self.node_id
        }
        
        # Add to sessions dictionary
        self.user_sessions[session_id] = session
        
        # Update user last active
        self.users[user_id]['last_active'] = datetime.now().isoformat()
        
        return session
        
    def add_peer(self, 
               peer_id: str,
               peer_url: str,
               peer_name: str = "") -> Dict[str, Any]:
        """
        Add a peer node to the federation.
        
        Args:
            peer_id: Unique identifier for the peer
            peer_url: URL for connecting to the peer
            peer_name: Display name for the peer
            
        Returns:
            Peer information
        """
        # Create peer record
        peer = {
            'peer_id': peer_id,
            'peer_url': peer_url,
            'peer_name': peer_name or f"Peer {peer_id}",
            'added_at': datetime.now().isoformat(),
            'last_sync': None,
            'status': 'registered'
        }
        
        # Add to peers dictionary
        self.peers[peer_id] = peer
        
        return peer
        
    def synchronize_with_peer(self, 
                            peer_id: str,
                            peer_changes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Synchronize changes with a peer node.
        
        Args:
            peer_id: ID of the peer to synchronize with
            peer_changes: List of changes from the peer
            
        Returns:
            Synchronization results
        """
        # Check if peer exists
        if peer_id not in self.peers:
            raise ValueError(f"Peer {peer_id} not registered")
            
        # Process peer changes
        applied_changes = []
        conflicts = []
        
        for change in peer_changes:
            try:
                # Apply the change
                result = self._apply_change(change, peer_id)
                
                if result.get('status') == 'conflict':
                    conflicts.append({
                        'change': change,
                        'reason': result.get('reason', 'Unknown conflict')
                    })
                else:
                    applied_changes.append(change['id'])
            except Exception as e:
                conflicts.append({
                    'change': change,
                    'reason': str(e)
                })
                
        # Update peer last sync time
        self.peers[peer_id]['last_sync'] = datetime.now().isoformat()
        
        # Return synchronization results
        return {
            'peer_id': peer_id,
            'applied_changes': len(applied_changes),
            'conflicts': len(conflicts),
            'conflict_details': conflicts,
            'timestamp': datetime.now().isoformat()
        }
        
    def get_changes_since(self, 
                        timestamp: str) -> List[Dict[str, Any]]:
        """
        Get changes since a specific timestamp.
        
        Args:
            timestamp: ISO format timestamp
            
        Returns:
            List of changes since the timestamp
        """
        # Parse the timestamp
        since_time = datetime.fromisoformat(timestamp)
        
        # Filter changes
        recent_changes = []
        
        for change in self.change_log:
            change_time = datetime.fromisoformat(change['timestamp'])
            if change_time > since_time:
                recent_changes.append(change)
                
        return recent_changes
        
    def get_fact_history(self, 
                       fact_id: str) -> List[Dict[str, Any]]:
        """
        Get the complete history of a fact.
        
        Args:
            fact_id: ID of the fact
            
        Returns:
            List of changes related to the fact
        """
        # Filter changes for this fact
        fact_changes = []
        
        for change in self.change_log:
            if change['fact_id'] == fact_id:
                fact_changes.append(change)
                
        # Sort by timestamp
        fact_changes.sort(key=lambda x: x['timestamp'])
        
        return fact_changes
        
    def get_user_contributions(self, 
                             user_id: str) -> Dict[str, Any]:
        """
        Get contributions made by a specific user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Dictionary with user contribution statistics
        """
        # Filter changes by this user
        user_changes = []
        
        for change in self.change_log:
            if change['user_id'] == user_id:
                user_changes.append(change)
                
        # Count by change type
        change_counts = {
            'add_fact': 0,
            'update_fact': 0,
            'delete_fact': 0
        }
        
        for change in user_changes:
            change_type = change['type']
            if change_type in change_counts:
                change_counts[change_type] += 1
                
        # Get unique facts modified
        unique_facts = set()
        for change in user_changes:
            unique_facts.add(change['fact_id'])
            
        return {
            'user_id': user_id,
            'username': self.users.get(user_id, {}).get('username', 'Unknown'),
            'total_changes': len(user_changes),
            'change_counts': change_counts,
            'unique_facts': len(unique_facts),
            'first_contribution': user_changes[0]['timestamp'] if user_changes else None,
            'last_contribution': user_changes[-1]['timestamp'] if user_changes else None
        }
        
    def export_federation_state(self, 
                              filename: str) -> None:
        """
        Export the federation state to a file.
        
        Args:
            filename: Path to save the federation state
        """
        # Create state object
        state = {
            'node_id': self.node_id,
            'timestamp': datetime.now().isoformat(),
            'peers': self.peers,
            'users': self.users,
            'change_log': self.change_log
        }
        
        # Save to file
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
            
    def import_federation_state(self, 
                              filename: str) -> Dict[str, Any]:
        """
        Import federation state from a file.
        
        Args:
            filename: Path to load the federation state from
            
        Returns:
            Import statistics
        """
        # Load from file
        with open(filename, 'r', encoding='utf-8') as f:
            state = json.load(f)
            
        # Update state
        self.node_id = state.get('node_id', self.node_id)
        self.peers = state.get('peers', {})
        self.users = state.get('users', {})
        
        # Process change log
        imported_changes = 0
        conflicts = 0
        
        for change in state.get('change_log', []):
            try:
                result = self._apply_change(change, state.get('node_id', 'imported'))
                
                if result.get('status') == 'applied':
                    imported_changes += 1
                else:
                    conflicts += 1
            except Exception:
                conflicts += 1
                
        return {
            'imported_node_id': state.get('node_id'),
            'peers_imported': len(self.peers),
            'users_imported': len(self.users),
            'changes_imported': imported_changes,
            'conflicts': conflicts
        }
        
    def _check_permission(self, 
                        user_id: str, 
                        permission: str) -> bool:
        """
        Check if a user has a specific permission.
        
        Args:
            user_id: ID of the user
            permission: Permission to check
            
        Returns:
            True if the user has the permission, False otherwise
        """
        # Check if user exists
        if user_id not in self.permissions:
            return False
            
        # Check if user has the permission
        return permission in self.permissions[user_id]
        
    def _set_role_permissions(self, 
                            user_id: str, 
                            role: str) -> None:
        """
        Set permissions for a user based on their role.
        
        Args:
            user_id: ID of the user
            role: Role of the user
        """
        # Define permissions for each role
        role_permissions = {
            'admin': ['view', 'add', 'edit', 'delete', 'manage_users', 'manage_peers'],
            'contributor': ['view', 'add', 'edit'],
            'viewer': ['view']
        }
        
        # Set permissions
        if role in role_permissions:
            self.permissions[user_id] = set(role_permissions[role])
        else:
            # Default to viewer
            self.permissions[user_id] = set(['view'])
            
    def _add_to_change_log(self, 
                         change: Dict[str, Any]) -> None:
        """
        Add a change to the change log.
        
        Args:
            change: Change to add
        """
        # Add to change log
        self.change_log.append(change)
        
        # Trim change log if needed
        if len(self.change_log) > self.max_change_log:
            self.change_log = self.change_log[-self.max_change_log:]
            
    def _apply_change(self, 
                    change: Dict[str, Any], 
                    source_id: str) -> Dict[str, Any]:
        """
        Apply a change from a peer.
        
        Args:
            change: Change to apply
            source_id: ID of the source (peer or import)
            
        Returns:
            Result of applying the change
        """
        change_type = change['type']
        fact_id = change['fact_id']
        
        # Check for conflicts
        if change_type in ['update_fact', 'delete_fact']:
            if fact_id not in self.kg.graph:
                return {
                    'status': 'conflict',
                    'reason': f"Fact {fact_id} not found"
                }
                
            # Check for version conflicts
            if change_type == 'update_fact':
                fact = self.kg.get_fact(fact_id)
                current_version = fact.get('version', 1)
                
                if 'previous_version' in change and change['previous_version'] != current_version:
                    return {
                        'status': 'conflict',
                        'reason': f"Version conflict: expected {change['previous_version']}, found {current_version}"
                    }
                    
        # Apply the change
        if change_type == 'add_fact':
            # Check if fact already exists
            if fact_id in self.kg.graph:
                return {
                    'status': 'conflict',
                    'reason': f"Fact {fact_id} already exists"
                }
                
            # Add the fact
            data = change['data']
            
            # Convert reliability rating from string to enum if needed
            reliability = data.get('reliability_rating', 'UNVERIFIED')
            if isinstance(reliability, str):
                reliability = getattr(ReliabilityRating, reliability)
                
            # Add the fact
            self.kg.add_fact(
                fact_id=fact_id,
                fact_statement=data.get('fact_statement', ''),
                category=data.get('category', ''),
                tags=data.get('tags', []),
                date_recorded=data.get('date_recorded', datetime.now()),
                last_updated=data.get('last_updated', datetime.now()),
                reliability_rating=reliability,
                source_id=data.get('source_id', ''),
                source_title=data.get('source_title', ''),
                author_creator=data.get('author_creator', ''),
                publication_date=data.get('publication_date', datetime.now()),
                url_reference=data.get('url_reference', ''),
                related_facts=data.get('related_facts', []),
                contextual_notes=data.get('contextual_notes', ''),
                access_level=data.get('access_level', 'public'),
                usage_count=data.get('usage_count', 0)
            )
            
            # Add collaborative metadata
            self.kg.update_fact(fact_id, 
                              created_by=change['user_id'],
                              created_at=change['timestamp'],
                              last_modified_by=change['user_id'],
                              last_modified_at=change['timestamp'],
                              node_id=change['node_id'],
                              version=1,
                              synced_from=source_id)
                              
        elif change_type == 'update_fact':
            # Update the fact
            data = change['data']
            
            # Convert reliability rating from string to enum if needed
            if 'reliability_rating' in data and isinstance(data['reliability_rating'], str):
                data['reliability_rating'] = getattr(ReliabilityRating, data['reliability_rating'])
                
            # Add sync metadata
            data['last_modified_by'] = change['user_id']
            data['last_modified_at'] = change['timestamp']
            data['synced_from'] = source_id
            
            # Update the fact
            self.kg.update_fact(fact_id, **data)
            
        elif change_type == 'delete_fact':
            # Delete the fact
            self.kg.graph.remove_node(fact_id)
            
        else:
            return {
                'status': 'conflict',
                'reason': f"Unknown change type: {change_type}"
            }
            
        return {
            'status': 'applied',
            'change_id': change['id']
        }
