"""
Lightweight test script for the improved link collection and page search functionality

This script tests the core functionality of the LinkCollector and PageSearcher classes
without requiring heavy dependencies like spaCy and sentence-transformers.
"""

import sys
import os
import logging
import re
from bs4 import BeautifulSoup
import requests
import urllib.parse
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('lightweight_test')

class SimpleLinkCollector:
    """Simplified version of LinkCollector for testing purposes"""
    
    def __init__(self, 
                 start_urls=None,
                 allowed_domains=None,
                 max_depth=1,
                 max_urls=10):
        """Initialize the SimpleLinkCollector"""
        self.start_urls = start_urls or []
        self.allowed_domains = allowed_domains or []
        self.max_depth = max_depth
        self.max_urls = max_urls
        
        # Internal state
        self.url_queue = []  # List of (url, depth) tuples
        self.visited_urls = set()  # Set of visited URLs
        self.collected_pages = {}  # Dictionary of {url: {'html': html, 'soup': soup, 'links': links, 'metadata': metadata}}
        
        # Initialize queue with start URLs
        for url in self.start_urls:
            self.url_queue.append((self._normalize_url(url), 0))
    
    def _normalize_url(self, url):
        """Normalize a URL to prevent duplicates"""
        # Parse the URL
        parsed = urllib.parse.urlparse(url)
        
        # Normalize the path
        path = parsed.path
        if not path:
            path = '/'
        
        # Remove trailing slash except for root
        if path != '/' and path.endswith('/'):
            path = path[:-1]
        
        # Reconstruct the URL without fragments
        normalized = urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            path,
            parsed.params,
            parsed.query,
            ''  # Remove fragment
        ))
        
        return normalized
    
    def _get_domain(self, url):
        """Extract the domain from a URL"""
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc
    
    def _is_allowed_domain(self, url):
        """Check if a URL's domain is in the allowed domains list"""
        if not self.allowed_domains:
            return True
        
        domain = self._get_domain(url)
        
        for allowed_domain in self.allowed_domains:
            if domain == allowed_domain or domain.endswith('.' + allowed_domain):
                return True
        
        return False
    
    def _extract_links(self, soup, base_url):
        """Extract all links from a BeautifulSoup object"""
        links = []
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            
            # Skip empty links, javascript, and mailto links
            if not href or href.startswith(('javascript:', 'mailto:', 'tel:')):
                continue
            
            # Resolve relative URLs
            absolute_url = urllib.parse.urljoin(base_url, href)
            
            # Normalize the URL
            normalized_url = self._normalize_url(absolute_url)
            
            links.append(normalized_url)
        
        return links
    
    def _extract_metadata(self, soup, url):
        """Extract basic metadata from a page"""
        metadata = {
            'title': None,
            'description': None,
        }
        
        # Extract title
        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.get_text().strip()
        
        # Extract meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            metadata['description'] = meta_desc.get('content', '')
        
        return metadata
    
    def fetch_url(self, url):
        """Fetch a URL and return its HTML content and BeautifulSoup object"""
        logger.info(f"Fetching URL: {url}")
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')
            
            return html, soup
        
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error fetching {url}: {e}")
            return None, None
    
    def collect_links(self):
        """Collect links starting from the start_urls"""
        while self.url_queue and len(self.visited_urls) < self.max_urls:
            # Get the next URL and depth from the queue
            url, depth = self.url_queue.pop(0)
            
            # Skip if already visited
            if url in self.visited_urls:
                continue
            
            # Skip if not in allowed domains
            if not self._is_allowed_domain(url):
                continue
            
            # Mark as visited
            self.visited_urls.add(url)
            
            # Fetch the URL
            html, soup = self.fetch_url(url)
            
            if not html or not soup:
                continue
            
            # Extract links
            links = self._extract_links(soup, url)
            
            # Extract metadata
            metadata = self._extract_metadata(soup, url)
            
            # Store the page
            self.collected_pages[url] = {
                'html': html,
                'soup': soup,
                'links': links,
                'metadata': metadata,
                'depth': depth
            }
            
            # If we haven't reached max depth, add links to queue
            if depth < self.max_depth:
                for link in links:
                    if link not in self.visited_urls:
                        self.url_queue.append((link, depth + 1))
            
            logger.info(f"Collected {len(self.visited_urls)} URLs, {len(self.url_queue)} in queue")
        
        return self.collected_pages


class SimplePageSearcher:
    """Simplified version of PageSearcher for testing purposes"""
    
    def __init__(self, min_content_length=20):
        """Initialize the SimplePageSearcher"""
        self.min_content_length = min_content_length
        
        # Initialize storage for extracted information
        self.extracted_facts = []
        self.keyword_index = defaultdict(list)  # Maps keyword -> list of fact indices
        self.url_to_facts = defaultdict(list)  # Maps URL -> list of fact indices
    
    def extract_text_elements(self, soup):
        """Extract text from HTML elements"""
        elements = []
        
        # Get all elements that might contain content
        for tag_name in ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li']:
            for element in soup.find_all(tag_name):
                text = element.get_text().strip()
                
                # Skip empty or very short elements
                if not text or len(text) < self.min_content_length:
                    continue
                
                elements.append({
                    'text': text,
                    'element_type': element.name,
                    'html': str(element)
                })
        
        return elements
    
    def extract_structured_data(self, soup):
        """Extract structured data like tables and lists"""
        structured_data = []
        
        # Extract tables
        tables = soup.find_all('table')
        for table in tables:
            rows = []
            headers = []
            
            # Extract headers
            th_elements = table.find_all('th')
            if th_elements:
                headers = [th.get_text().strip() for th in th_elements]
            
            # Extract rows
            for tr in table.find_all('tr'):
                cells = [td.get_text().strip() for td in tr.find_all(['td', 'th'])]
                if cells and not all(cell == '' for cell in cells):
                    rows.append(cells)
            
            if rows:
                structured_data.append({
                    'type': 'table',
                    'headers': headers,
                    'rows': rows,
                    'html': str(table)
                })
        
        # Extract lists
        for list_tag in soup.find_all(['ul', 'ol']):
            items = [li.get_text().strip() for li in list_tag.find_all('li')]
            if items:
                structured_data.append({
                    'type': 'list',
                    'list_type': list_tag.name,
                    'items': items,
                    'html': str(list_tag)
                })
        
        return structured_data
    
    def search_by_keywords(self, pages, keywords):
        """Search pages for specific keywords"""
        results = []
        
        for url, page_data in pages.items():
            soup = page_data['soup']
            
            # Get all text elements
            elements = self.extract_text_elements(soup)
            
            for element in elements:
                text = element['text'].lower()
                
                # Check if any keyword is in the text
                matches = [keyword for keyword in keywords if keyword.lower() in text]
                
                if matches:
                    results.append({
                        'url': url,
                        'text': element['text'],
                        'element_type': element['element_type'],
                        'matched_keywords': matches,
                        'html': element['html']
                    })
        
        return results
    
    def search_by_regex(self, pages, pattern):
        """Search pages using regular expression pattern"""
        results = []
        regex = re.compile(pattern)
        
        for url, page_data in pages.items():
            soup = page_data['soup']
            
            # Get all text elements
            elements = self.extract_text_elements(soup)
            
            for element in elements:
                text = element['text']
                
                # Find all matches
                matches = regex.findall(text)
                
                if matches:
                    results.append({
                        'url': url,
                        'text': element['text'],
                        'element_type': element['element_type'],
                        'regex_matches': matches,
                        'html': element['html']
                    })
        
        return results
    
    def search_by_css_selector(self, pages, css_selector):
        """Search pages using CSS selector"""
        results = []
        
        for url, page_data in pages.items():
            soup = page_data['soup']
            
            # Find elements matching the CSS selector
            matching_elements = soup.select(css_selector)
            
            for element in matching_elements:
                text = element.get_text().strip()
                
                if text and len(text) >= self.min_content_length:
                    results.append({
                        'url': url,
                        'text': text,
                        'element_type': element.name,
                        'css_selector': css_selector,
                        'html': str(element)
                    })
        
        return results
    
    def extract_facts_from_pages(self, pages):
        """Extract facts from pages"""
        # Reset storage
        self.extracted_facts = []
        self.keyword_index = defaultdict(list)
        self.url_to_facts = defaultdict(list)
        
        for url, page_data in pages.items():
            soup = page_data['soup']
            metadata = page_data['metadata']
            
            # Extract text elements
            elements = self.extract_text_elements(soup)
            
            # Extract structured data
            structured_data = self.extract_structured_data(soup)
            
            # Process text elements
            for element in elements:
                text = element['text']
                
                # Skip if too short
                if len(text) < self.min_content_length:
                    continue
                
                # Create fact
                fact = {
                    'text': text,
                    'url': url,
                    'element_type': element['element_type'],
                    'metadata': metadata,
                    'html': element['html']
                }
                
                # Add to storage
                fact_idx = len(self.extracted_facts)
                self.extracted_facts.append(fact)
                self.url_to_facts[url].append(fact_idx)
                
                # Index keywords (simple approach - split by spaces and remove punctuation)
                words = re.findall(r'\b\w+\b', text.lower())
                for word in words:
                    if len(word) > 3:  # Skip very short words
                        self.keyword_index[word].append(fact_idx)
            
            # Process structured data
            for data in structured_data:
                if data['type'] == 'table':
                    # For tables, create a fact for each row
                    headers = data['headers']
                    for row in data['rows']:
                        if headers and len(headers) == len(row):
                            # Create a text representation of the row
                            row_text = '. '.join([f"{headers[i]}: {row[i]}" for i in range(len(headers))])
                        else:
                            row_text = '. '.join(row)
                        
                        # Skip if too short
                        if len(row_text) < self.min_content_length:
                            continue
                        
                        # Create fact
                        fact = {
                            'text': row_text,
                            'url': url,
                            'element_type': 'table_row',
                            'metadata': metadata,
                            'structured_data': {
                                'type': 'table_row',
                                'headers': headers,
                                'values': row
                            },
                            'html': data['html']
                        }
                        
                        # Add to storage
                        fact_idx = len(self.extracted_facts)
                        self.extracted_facts.append(fact)
                        self.url_to_facts[url].append(fact_idx)
                
                elif data['type'] == 'list':
                    # For lists, create a fact for the entire list
                    list_text = '. '.join(data['items'])
                    
                    # Skip if too short
                    if len(list_text) < self.min_content_length:
                        continue
                    
                    # Create fact
                    fact = {
                        'text': list_text,
                        'url': url,
                        'element_type': f"{data['list_type']}_list",
                        'metadata': metadata,
                        'structured_data': {
                            'type': 'list',
                            'list_type': data['list_type'],
                            'items': data['items']
                        },
                        'html': data['html']
                    }
                    
                    # Add to storage
                    fact_idx = len(self.extracted_facts)
                    self.extracted_facts.append(fact)
                    self.url_to_facts[url].append(fact_idx)
        
        return self.extracted_facts
    
    def search_facts_by_keyword(self, keyword):
        """Search extracted facts by keyword"""
        keyword = keyword.lower()
        fact_indices = self.keyword_index.get(keyword, [])
        return [self.extracted_facts[idx] for idx in fact_indices]
    
    def get_facts_by_url(self, url):
        """Get all facts extracted from a specific URL"""
        fact_indices = self.url_to_facts.get(url, [])
        return [self.extracted_facts[idx] for idx in fact_indices]


def test_lightweight():
    """Run lightweight tests for link collection and page search"""
    logger.info("Starting lightweight tests...")
    
    # Test link collector
    logger.info("Testing SimpleLinkCollector...")
    collector = SimpleLinkCollector(
        start_urls=["https://civichonors.com/", "https://www.nelslindahl.com/"],
        allowed_domains=["civichonors.com", "nelslindahl.com"],
        max_depth=1,
        max_urls=5  # Limit to 5 URLs for quick testing
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
    
    # Test page searcher if we have pages
    if pages:
        logger.info("Testing SimplePageSearcher...")
        searcher = SimplePageSearcher()
        
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
        
        # Test fact extraction
        logger.info("Testing fact extraction...")
        facts = searcher.extract_facts_from_pages(pages)
        logger.info(f"Extracted {len(facts)} facts")
        
        # Test keyword search in facts
        if facts:
            logger.info("Testing keyword search in facts...")
            keyword_facts = searcher.search_facts_by_keyword("civic")
            logger.info(f"Found {len(keyword_facts)} facts containing keyword 'civic'")
        
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
    
    logger.info("Lightweight tests completed.")

if __name__ == "__main__":
    test_lightweight()
