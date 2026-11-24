"""
Initialization file for the processing module.

This module provides functionality for cleaning, deduplicating, and refining
data in knowledge graphs.
"""

from .cleaning import (
    remove_duplicate_facts,
    advanced_cleaning,
    semantic_cleaning,
    clean_knowledge_graph
)

__all__ = [
    'remove_duplicate_facts',
    'advanced_cleaning',
    'semantic_cleaning',
    'clean_knowledge_graph'
]
