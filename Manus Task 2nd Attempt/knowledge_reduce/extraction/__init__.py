"""
Initialization file for the extraction module.

This module provides functionality for extracting data from various sources
to be used in building knowledge graphs.
"""

from .web import (
    extract_text,
    find_facts,
    scrape_website,
    extract_facts_from_url,
    extract_facts_from_multiple_urls,
    populate_knowledge_graph_from_urls
)

__all__ = [
    'extract_text',
    'find_facts',
    'scrape_website',
    'extract_facts_from_url',
    'extract_facts_from_multiple_urls',
    'populate_knowledge_graph_from_urls'
]
