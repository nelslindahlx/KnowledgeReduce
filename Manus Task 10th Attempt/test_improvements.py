"""
Test script for the improved link collection and page search functionality

This script tests the LinkCollector and PageSearcher classes to ensure they work as expected.
"""

import sys
import os
import logging
from pprint import pprint

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('test_script')

# Import the improved modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from improved_link_collection import LinkCollector, filter_pdf_urls, filter_image_urls
from improved_page_search import PageSearcher

def test_link_collector():
    """Test the LinkCollector class"""
    logger.info("Testing LinkCollector...")
    
    # Initialize with test parameters
    collector = LinkCollector(
        start_urls=["https://civichonors.com/", "https://www.nelslindahl.com/"],
        allowed_domains=["civichonors.com", "nelslindahl.com"],
        max_depth=1,  # Only follow links one level deep for testing
        respect_robots_txt=True,
        rate_limit=1.0,
        max_urls=10,  # Limit to 10 URLs for testing
        link_filters=[filter_pdf_urls, filter_image_urls]
    )
    
    # Collect links
    logger.info("Collecting links...")
    pages = collector.collect_links()
    
    # Print results
    logger.info(f"Collected {len(pages)} pages:")
    for url in pages.keys():
        logger.info(f"  - {url}")
        
        # Print number of links found on this page
        links = pages[url]['links']
        logger.info(f"    Found {len(links)} links on this page")
        
        # Print metadata
        metadata = pages[url]['metadata']
        logger.info(f"    Title: {metadata.get('title')}")
    
    return pages

def test_page_searcher(pages):
    """Test the PageSearcher class"""
    logger.info("Testing PageSearcher...")
    
    # Initialize with test parameters
    searcher = PageSearcher()
    
    # Test keyword search
    logger.info("Testing keyword search...")
    keyword_results = searcher.search_by_keywords(pages, ["civic", "honors", "volunteer"])
    logger.info(f"Found {len(keyword_results)} results containing keywords")
    
    # Test regex search
    logger.info("Testing regex search...")
    regex_results = searcher.search_by_regex(pages, r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')  # Email pattern
    logger.info(f"Found {len(regex_results)} results matching email regex")
    
    # Test CSS selector search
    logger.info("Testing CSS selector search...")
    css_results = searcher.search_by_css_selector(pages, 'a.btn')
    logger.info(f"Found {len(css_results)} results matching CSS selector")
    
    # Test semantic search
    logger.info("Testing semantic search...")
    semantic_results = searcher.semantic_search(pages, "community service and volunteering", top_k=5)
    logger.info(f"Found {len(semantic_results)} results for semantic search")
    
    # Test fact extraction
    logger.info("Testing fact extraction...")
    facts = searcher.extract_facts_from_pages(pages, topics=["civic honors", "community service"])
    logger.info(f"Extracted {len(facts)} facts")
    
    # Test entity search
    if facts:
        # Get all entities from the first fact
        first_fact = facts[0]
        all_entities = []
        for entity_list in first_fact['entities'].values():
            all_entities.extend(entity_list)
        
        if all_entities:
            test_entity = all_entities[0]
            logger.info(f"Testing entity search for '{test_entity}'...")
            entity_results = searcher.search_facts_by_entity(test_entity)
            logger.info(f"Found {len(entity_results)} facts containing entity '{test_entity}'")
    
    # Test related facts
    if len(facts) > 1:
        logger.info("Testing related facts...")
        related = searcher.find_related_facts(0, threshold=0.5)
        logger.info(f"Found {len(related)} facts related to the first fact")
    
    return facts

def main():
    """Main test function"""
    logger.info("Starting tests...")
    
    # Test link collector
    pages = test_link_collector()
    
    # Test page searcher if we have pages
    if pages:
        facts = test_page_searcher(pages)
        
        # Save a sample of facts to a file
        if facts:
            import json
            with open('sample_facts.json', 'w') as f:
                # Take up to 5 facts as a sample
                sample = facts[:min(5, len(facts))]
                
                # Convert to serializable format
                serializable_sample = []
                for fact in sample:
                    fact_copy = fact.copy()
                    # Remove soup objects which aren't serializable
                    if 'soup' in fact_copy:
                        del fact_copy['soup']
                    serializable_sample.append(fact_copy)
                
                json.dump(serializable_sample, f, indent=2)
            logger.info(f"Saved {min(5, len(facts))} sample facts to sample_facts.json")
    
    logger.info("Tests completed.")

if __name__ == "__main__":
    main()
