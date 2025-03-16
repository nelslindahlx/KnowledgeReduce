"""
Data extraction utilities for the KnowledgeReduce framework.

This module provides functions for extracting data from various sources,
particularly web pages, to be used in building knowledge graphs.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime


def extract_text(element):
    """
    Extract clean text from a BeautifulSoup element.
    
    Args:
        element: BeautifulSoup element
        
    Returns:
        str: Extracted text with whitespace normalized
    """
    return ' '.join(element.stripped_strings)


def find_facts(soup):
    """
    Extract potential facts from common HTML structures.
    
    Args:
        soup: BeautifulSoup object representing a parsed HTML document
        
    Returns:
        list: Extracted facts as strings
    """
    facts = []
    
    # Extract from paragraphs
    for p in soup.find_all('p'):
        text = extract_text(p)
        if text:
            facts.append(text)
    
    # Extract from headings
    for header_tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
        for header in soup.find_all(header_tag):
            text = extract_text(header)
            if text:
                facts.append(text)
    
    # Extract from list items
    for li in soup.find_all('li'):
        text = extract_text(li)
        if text:
            facts.append(text)
            
    return facts


def scrape_website(url):
    """
    Scrape a website and return its BeautifulSoup object.
    
    Args:
        url: URL of the website to scrape
        
    Returns:
        BeautifulSoup: Parsed HTML or None if request fails
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except requests.exceptions.RequestException as e:
        print(f"Error during request to {url}: {e}")
        return None


def extract_facts_from_url(url, source_id=None, source_title=None):
    """
    Extract facts from a URL.
    
    Args:
        url: URL to extract facts from
        source_id: Identifier for the source (defaults to domain name)
        source_title: Title for the source (defaults to URL)
        
    Returns:
        tuple: (list of facts, source_id, source_title)
    """
    # Set default values for source_id and source_title
    if source_id is None:
        # Extract domain name from URL
        from urllib.parse import urlparse
        source_id = urlparse(url).netloc
    
    if source_title is None:
        source_title = url
    
    # Scrape website
    soup = scrape_website(url)
    if soup is None:
        return [], source_id, source_title
    
    # Try to get a better title if available
    if soup.title and soup.title.string:
        source_title = soup.title.string.strip()
    
    # Extract facts
    facts = find_facts(soup)
    
    return facts, source_id, source_title


def extract_facts_from_multiple_urls(urls):
    """
    Extract facts from multiple URLs.
    
    Args:
        urls: Dictionary mapping source_ids to URLs or list of URLs
        
    Returns:
        dict: Mapping of source_ids to lists of facts and metadata
    """
    results = {}
    
    # Handle both dictionary and list inputs
    if isinstance(urls, dict):
        url_dict = urls
    else:
        url_dict = {f"source_{i}": url for i, url in enumerate(urls)}
    
    # Process each URL
    for source_id, url in url_dict.items():
        facts, actual_source_id, source_title = extract_facts_from_url(url, source_id)
        results[actual_source_id] = {
            'facts': facts,
            'source_title': source_title,
            'url': url,
            'extraction_time': datetime.now().isoformat()
        }
    
    return results


def populate_knowledge_graph_from_urls(knowledge_graph, urls, category="General", 
                                      tags=None, reliability_rating=None):
    """
    Extract facts from URLs and add them to a knowledge graph.
    
    Args:
        knowledge_graph: KnowledgeGraph instance
        urls: Dictionary mapping source_ids to URLs or list of URLs
        category: Category for the facts
        tags: Additional tags for the facts
        reliability_rating: ReliabilityRating for the facts
        
    Returns:
        int: Number of facts added
    """
    from ..graph.core import ReliabilityRating
    
    # Set default values
    if tags is None:
        tags = ["WebScraped"]
    if reliability_rating is None:
        reliability_rating = ReliabilityRating.UNVERIFIED
    
    # Extract facts from URLs
    results = extract_facts_from_multiple_urls(urls)
    
    # Add facts to knowledge graph
    fact_count = 0
    for source_id, source_data in results.items():
        source_tags = tags + [source_id]
        
        for i, fact in enumerate(source_data['facts']):
            fact_id = f"{source_id}_{i}"
            
            knowledge_graph.add_fact(
                fact_id=fact_id,
                fact_statement=fact,
                category=category,
                tags=source_tags,
                date_recorded=datetime.now(),
                last_updated=datetime.now(),
                reliability_rating=reliability_rating,
                source_id=source_id,
                source_title=source_data['source_title'],
                author_creator="Web Scraping",
                publication_date=datetime.now(),
                url_reference=source_data['url'],
                related_facts=[],
                contextual_notes=f"Extracted from {source_id} website",
                access_level="Public",
                usage_count=0
            )
            
            fact_count += 1
    
    return fact_count
