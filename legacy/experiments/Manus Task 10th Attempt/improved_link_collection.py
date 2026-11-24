"""
Improved Link Collection Module for CivicHonorsKG

This module enhances the original notebook with advanced link collection capabilities:
- Link extraction from pages
- URL queue management
- Depth control for crawling
- Domain filtering
- URL normalization
- Visited URL tracking
- Robots.txt compliance
- Rate limiting
- Error handling
- Metadata extraction
"""

import requests
from bs4 import BeautifulSoup
import time
import urllib.parse
import re
from urllib.robotparser import RobotFileParser
from collections import deque
import logging
from typing import List, Dict, Set, Tuple, Optional, Union, Callable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('link_collector')

class LinkCollector:
    """Class for collecting links from websites with advanced features."""
    
    def __init__(self, 
                 start_urls: List[str] = None,
                 allowed_domains: List[str] = None,
                 max_depth: int = 2,
                 respect_robots_txt: bool = True,
                 rate_limit: float = 1.0,
                 user_agent: str = 'CivicHonorsKG/1.0',
                 max_urls: int = 100,
                 link_filters: List[Callable[[str], bool]] = None):
        """
        Initialize the LinkCollector.
        
        Args:
            start_urls: List of URLs to start crawling from
            allowed_domains: List of domains to restrict crawling to
            max_depth: Maximum depth to crawl (0 = only start_urls)
            respect_robots_txt: Whether to respect robots.txt files
            rate_limit: Minimum time between requests in seconds
            user_agent: User agent string to use for requests
            max_urls: Maximum number of URLs to collect
            link_filters: List of filter functions that take a URL and return True if it should be followed
        """
        self.start_urls = start_urls or []
        self.allowed_domains = allowed_domains or []
        self.max_depth = max_depth
        self.respect_robots_txt = respect_robots_txt
        self.rate_limit = rate_limit
        self.user_agent = user_agent
        self.max_urls = max_urls
        self.link_filters = link_filters or []
        
        # Internal state
        self.url_queue = deque()  # Queue of (url, depth) tuples
        self.visited_urls = set()  # Set of visited URLs
        self.robots_parsers = {}  # Cache of RobotFileParser objects
        self.last_request_time = 0  # Time of last request
        self.collected_pages = {}  # Dictionary of {url: {'html': html, 'soup': soup, 'links': links, 'metadata': metadata}}
        
        # Initialize queue with start URLs
        for url in self.start_urls:
            self.url_queue.append((self._normalize_url(url), 0))
    
    def _normalize_url(self, url: str) -> str:
        """
        Normalize a URL to prevent duplicates.
        
        Args:
            url: URL to normalize
            
        Returns:
            Normalized URL
        """
        # Parse the URL
        parsed = urllib.parse.urlparse(url)
        
        # Normalize the path
        path = parsed.path
        if not path:
            path = '/'
        
        # Remove trailing slash except for root
        if path != '/' and path.endswith('/'):
            path = path[:-1]
        
        # Reconstruct the URL without fragments and with default ports removed
        normalized = urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            path,
            parsed.params,
            parsed.query,
            ''  # Remove fragment
        ))
        
        return normalized
    
    def _get_domain(self, url: str) -> str:
        """
        Extract the domain from a URL.
        
        Args:
            url: URL to extract domain from
            
        Returns:
            Domain name
        """
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc
    
    def _is_allowed_domain(self, url: str) -> bool:
        """
        Check if a URL's domain is in the allowed domains list.
        
        Args:
            url: URL to check
            
        Returns:
            True if domain is allowed or no restrictions set
        """
        if not self.allowed_domains:
            return True
        
        domain = self._get_domain(url)
        
        for allowed_domain in self.allowed_domains:
            if domain == allowed_domain or domain.endswith('.' + allowed_domain):
                return True
        
        return False
    
    def _can_fetch(self, url: str) -> bool:
        """
        Check if a URL can be fetched according to robots.txt.
        
        Args:
            url: URL to check
            
        Returns:
            True if URL can be fetched
        """
        if not self.respect_robots_txt:
            return True
        
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc
        scheme = parsed.scheme
        
        # Get or create robots parser for this domain
        if domain not in self.robots_parsers:
            robots_url = f"{scheme}://{domain}/robots.txt"
            parser = RobotFileParser()
            parser.set_url(robots_url)
            try:
                parser.read()
                self.robots_parsers[domain] = parser
            except Exception as e:
                logger.warning(f"Error reading robots.txt for {domain}: {e}")
                # If we can't read robots.txt, assume we can fetch
                return True
        
        # Check if we can fetch this URL
        return self.robots_parsers[domain].can_fetch(self.user_agent, url)
    
    def _apply_rate_limit(self):
        """Apply rate limiting between requests."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.rate_limit:
            time.sleep(self.rate_limit - time_since_last_request)
        
        self.last_request_time = time.time()
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """
        Extract all links from a BeautifulSoup object.
        
        Args:
            soup: BeautifulSoup object
            base_url: Base URL for resolving relative links
            
        Returns:
            List of absolute URLs
        """
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
            
            # Apply custom filters
            if all(filter_func(normalized_url) for filter_func in self.link_filters):
                links.append(normalized_url)
        
        return links
    
    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict:
        """
        Extract metadata from a page.
        
        Args:
            soup: BeautifulSoup object
            url: URL of the page
            
        Returns:
            Dictionary of metadata
        """
        metadata = {
            'title': None,
            'description': None,
            'keywords': None,
            'author': None,
            'published_date': None,
        }
        
        # Extract title
        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.get_text().strip()
        
        # Extract meta tags
        for meta in soup.find_all('meta'):
            name = meta.get('name', '').lower()
            property = meta.get('property', '').lower()
            content = meta.get('content', '')
            
            if name == 'description' or property == 'og:description':
                metadata['description'] = content
            elif name == 'keywords':
                metadata['keywords'] = content
            elif name == 'author':
                metadata['author'] = content
            elif name == 'article:published_time' or property == 'article:published_time':
                metadata['published_date'] = content
        
        return metadata
    
    def fetch_url(self, url: str) -> Tuple[Optional[str], Optional[BeautifulSoup]]:
        """
        Fetch a URL and return its HTML content and BeautifulSoup object.
        
        Args:
            url: URL to fetch
            
        Returns:
            Tuple of (html_content, soup_object) or (None, None) if fetch failed
        """
        logger.info(f"Fetching URL: {url}")
        
        # Apply rate limiting
        self._apply_rate_limit()
        
        # Check robots.txt
        if not self._can_fetch(url):
            logger.info(f"Skipping URL {url} (disallowed by robots.txt)")
            return None, None
        
        # Fetch the URL
        try:
            headers = {'User-Agent': self.user_agent}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')
            
            return html, soup
        
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error fetching {url}: {e}")
            return None, None
    
    def collect_links(self) -> Dict[str, Dict]:
        """
        Collect links starting from the start_urls.
        
        Returns:
            Dictionary of collected pages
        """
        while self.url_queue and len(self.visited_urls) < self.max_urls:
            # Get the next URL and depth from the queue
            url, depth = self.url_queue.popleft()
            
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
    
    def get_collected_urls(self) -> List[str]:
        """
        Get list of collected URLs.
        
        Returns:
            List of URLs
        """
        return list(self.collected_pages.keys())
    
    def get_page_content(self, url: str) -> Optional[Dict]:
        """
        Get content for a specific URL.
        
        Args:
            url: URL to get content for
            
        Returns:
            Dictionary with page content or None if not found
        """
        return self.collected_pages.get(url)


# Example filter functions
def filter_pdf_urls(url: str) -> bool:
    """Filter out PDF URLs."""
    return not url.lower().endswith('.pdf')

def filter_image_urls(url: str) -> bool:
    """Filter out image URLs."""
    return not url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg'))

def filter_by_keywords(url: str, keywords: List[str]) -> bool:
    """Filter URLs by keywords in the URL."""
    url_lower = url.lower()
    return any(keyword.lower() in url_lower for keyword in keywords)
