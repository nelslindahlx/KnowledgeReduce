"""
Multi-modal knowledge graph with image, audio, and video integration.

This module provides capabilities for creating and managing knowledge graphs
that incorporate multi-modal data including images, audio, and video.
"""

import os
import hashlib
import base64
from typing import Dict, List, Any, Union, Optional, Tuple, Set, Callable, BinaryIO
from datetime import datetime
import json
from .core import KnowledgeGraph, ReliabilityRating

class MultiModalKnowledgeGraph:
    """
    Class for multi-modal knowledge graph operations.
    
    This class provides methods for creating and managing knowledge graphs
    that incorporate multi-modal data including images, audio, and video.
    
    Attributes:
        kg: The knowledge graph to enhance with multi-modal capabilities
        media_dir: Directory to store media files
        media_index: Index of media files and their metadata
    """
    
    def __init__(self, knowledge_graph: KnowledgeGraph, media_dir: str = "media"):
        """
        Initialize a MultiModalKnowledgeGraph with a knowledge graph.
        
        Args:
            knowledge_graph: KnowledgeGraph instance to enhance
            media_dir: Directory to store media files
        """
        self.kg = knowledge_graph
        self.media_dir = media_dir
        self.media_index = {}
        
        # Create media directory if it doesn't exist
        os.makedirs(media_dir, exist_ok=True)
        
        # Load existing media index if available
        self._load_media_index()
        
    def add_image_fact(self, 
                     fact_id: str,
                     image_data: Union[bytes, BinaryIO, str],
                     caption: str,
                     category: str,
                     tags: List[str],
                     reliability_rating: ReliabilityRating,
                     source_id: str,
                     **kwargs) -> Dict[str, Any]:
        """
        Add a fact with an associated image.
        
        Args:
            fact_id: Unique identifier for the fact
            image_data: Image data as bytes, file-like object, or path to file
            caption: Caption describing the image
            category: Category of the fact
            tags: List of tags associated with the fact
            reliability_rating: ReliabilityRating enum value
            source_id: Identifier for the source
            **kwargs: Additional fact attributes
            
        Returns:
            Dictionary with fact and media information
        """
        # Process image data
        image_info = self._process_media(image_data, "image", fact_id)
        
        # Create fact statement incorporating the image reference
        fact_statement = f"[IMAGE] {caption}"
        
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
            contextual_notes=kwargs.get('contextual_notes', f"Image fact: {caption}"),
            access_level=kwargs.get('access_level', 'public'),
            usage_count=kwargs.get('usage_count', 0)
        )
        
        # Add media metadata to the fact
        self.kg.update_fact(fact_id, media_info=image_info)
        
        return {
            'fact_id': fact_id,
            'media_info': image_info
        }
        
    def add_audio_fact(self, 
                     fact_id: str,
                     audio_data: Union[bytes, BinaryIO, str],
                     description: str,
                     category: str,
                     tags: List[str],
                     reliability_rating: ReliabilityRating,
                     source_id: str,
                     **kwargs) -> Dict[str, Any]:
        """
        Add a fact with an associated audio file.
        
        Args:
            fact_id: Unique identifier for the fact
            audio_data: Audio data as bytes, file-like object, or path to file
            description: Description of the audio content
            category: Category of the fact
            tags: List of tags associated with the fact
            reliability_rating: ReliabilityRating enum value
            source_id: Identifier for the source
            **kwargs: Additional fact attributes
            
        Returns:
            Dictionary with fact and media information
        """
        # Process audio data
        audio_info = self._process_media(audio_data, "audio", fact_id)
        
        # Create fact statement incorporating the audio reference
        fact_statement = f"[AUDIO] {description}"
        
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
            contextual_notes=kwargs.get('contextual_notes', f"Audio fact: {description}"),
            access_level=kwargs.get('access_level', 'public'),
            usage_count=kwargs.get('usage_count', 0)
        )
        
        # Add media metadata to the fact
        self.kg.update_fact(fact_id, media_info=audio_info)
        
        return {
            'fact_id': fact_id,
            'media_info': audio_info
        }
        
    def add_video_fact(self, 
                     fact_id: str,
                     video_data: Union[bytes, BinaryIO, str],
                     description: str,
                     category: str,
                     tags: List[str],
                     reliability_rating: ReliabilityRating,
                     source_id: str,
                     **kwargs) -> Dict[str, Any]:
        """
        Add a fact with an associated video file.
        
        Args:
            fact_id: Unique identifier for the fact
            video_data: Video data as bytes, file-like object, or path to file
            description: Description of the video content
            category: Category of the fact
            tags: List of tags associated with the fact
            reliability_rating: ReliabilityRating enum value
            source_id: Identifier for the source
            **kwargs: Additional fact attributes
            
        Returns:
            Dictionary with fact and media information
        """
        # Process video data
        video_info = self._process_media(video_data, "video", fact_id)
        
        # Create fact statement incorporating the video reference
        fact_statement = f"[VIDEO] {description}"
        
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
            contextual_notes=kwargs.get('contextual_notes', f"Video fact: {description}"),
            access_level=kwargs.get('access_level', 'public'),
            usage_count=kwargs.get('usage_count', 0)
        )
        
        # Add media metadata to the fact
        self.kg.update_fact(fact_id, media_info=video_info)
        
        return {
            'fact_id': fact_id,
            'media_info': video_info
        }
        
    def get_media_path(self, fact_id: str) -> Optional[str]:
        """
        Get the path to the media file associated with a fact.
        
        Args:
            fact_id: ID of the fact
            
        Returns:
            Path to the media file, or None if no media is associated
        """
        try:
            fact = self.kg.get_fact(fact_id)
            
            if 'media_info' not in fact:
                return None
                
            media_info = fact['media_info']
            return os.path.join(self.media_dir, media_info['filename'])
            
        except Exception as e:
            print(f"Error getting media path for fact {fact_id}: {e}")
            return None
            
    def get_media_info(self, fact_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about the media associated with a fact.
        
        Args:
            fact_id: ID of the fact
            
        Returns:
            Dictionary with media information, or None if no media is associated
        """
        try:
            fact = self.kg.get_fact(fact_id)
            
            if 'media_info' not in fact:
                return None
                
            return fact['media_info']
            
        except Exception as e:
            print(f"Error getting media info for fact {fact_id}: {e}")
            return None
            
    def search_media_facts(self, media_type: Optional[str] = None, tags: Optional[List[str]] = None) -> List[str]:
        """
        Search for facts with associated media.
        
        Args:
            media_type: Type of media to search for (image, audio, video)
            tags: List of tags to filter by
            
        Returns:
            List of fact IDs matching the criteria
        """
        matching_facts = []
        
        for node, data in self.kg.graph.nodes(data=True):
            if 'media_info' not in data:
                continue
                
            # Check media type
            if media_type and data['media_info']['type'] != media_type:
                continue
                
            # Check tags
            if tags:
                if 'tags' not in data:
                    continue
                    
                if not all(tag in data['tags'] for tag in tags):
                    continue
                    
            matching_facts.append(node)
            
        return matching_facts
        
    def export_media_index(self, filename: str) -> None:
        """
        Export the media index to a file.
        
        Args:
            filename: Path to save the media index
        """
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.media_index, f, indent=2)
            
    def import_media_index(self, filename: str) -> int:
        """
        Import a media index from a file.
        
        Args:
            filename: Path to load the media index from
            
        Returns:
            Number of media entries imported
        """
        with open(filename, 'r', encoding='utf-8') as f:
            self.media_index = json.load(f)
            
        return len(self.media_index)
        
    def _process_media(self, media_data: Union[bytes, BinaryIO, str], media_type: str, fact_id: str) -> Dict[str, Any]:
        """
        Process media data and save to file.
        
        Args:
            media_data: Media data as bytes, file-like object, or path to file
            media_type: Type of media (image, audio, video)
            fact_id: ID of the associated fact
            
        Returns:
            Dictionary with media information
        """
        # Convert media_data to bytes
        if isinstance(media_data, str):
            # Assume it's a file path
            with open(media_data, 'rb') as f:
                data = f.read()
        elif hasattr(media_data, 'read'):
            # File-like object
            data = media_data.read()
        else:
            # Assume it's already bytes
            data = media_data
            
        # Calculate hash of the data
        media_hash = hashlib.sha256(data).hexdigest()
        
        # Determine file extension based on media type
        extensions = {
            "image": ".jpg",
            "audio": ".mp3",
            "video": ".mp4"
        }
        extension = extensions.get(media_type, ".bin")
        
        # Create filename
        filename = f"{media_type}_{media_hash[:10]}_{fact_id}{extension}"
        
        # Save the file
        file_path = os.path.join(self.media_dir, filename)
        with open(file_path, 'wb') as f:
            f.write(data)
            
        # Create media info
        media_info = {
            'type': media_type,
            'filename': filename,
            'hash': media_hash,
            'size': len(data),
            'path': file_path,
            'date_added': datetime.now().isoformat()
        }
        
        # Add to media index
        self.media_index[filename] = media_info
        
        # Save media index
        self._save_media_index()
        
        return media_info
        
    def _load_media_index(self) -> None:
        """
        Load the media index from file.
        """
        index_path = os.path.join(self.media_dir, "media_index.json")
        
        if os.path.exists(index_path):
            try:
                with open(index_path, 'r', encoding='utf-8') as f:
                    self.media_index = json.load(f)
            except Exception as e:
                print(f"Error loading media index: {e}")
                self.media_index = {}
                
    def _save_media_index(self) -> None:
        """
        Save the media index to file.
        """
        index_path = os.path.join(self.media_dir, "media_index.json")
        
        try:
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(self.media_index, f, indent=2)
        except Exception as e:
            print(f"Error saving media index: {e}")
