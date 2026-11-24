#!/usr/bin/env python3
"""
Test Implementation for Enhanced KnowledgeReduce

This script demonstrates the refined KnowledgeReduce technique with enhanced
crawling strategy and database growth mechanisms.
"""

import os
import time
import json
import hashlib
import sqlite3
from datetime import datetime
from collections import deque, defaultdict
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup

# Create directory for test results
os.makedirs('test_results', exist_ok=True)

class ReliabilityRating:
    """Enum for reliability ratings of facts"""
    LIKELY_TRUE = 'Likely True'
    POSSIBLY_TRUE = 'Possibly True'
    UNCERTAIN = 'Uncertain'
    POSSIBLY_FALSE = 'Possibly False'
    LIKELY_FALSE = 'Likely False'

class KnowledgeDatabase:
    """Database for storing knowledge graph data"""
    def __init__(self, db_path="test_results/knowledge_reduce.db"):
        """Initialize database connection."""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.create_tables()
        
    def create_tables(self):
        """Create necessary database tables if they don't exist."""
        cursor = self.conn.cursor()
        
        # Table for crawled URLs
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS crawled_urls (
            url TEXT PRIMARY KEY,
            domain TEXT,
            last_crawled TIMESTAMP,
            content_hash TEXT,
            title TEXT,
            http_status INTEGER,
            next_scheduled_crawl REAL
        )
        ''')
        
        # Table for content elements
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS content_elements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            element_type TEXT,
            text TEXT,
            html_class TEXT,
            html_id TEXT,
            FOREIGN KEY (url) REFERENCES crawled_urls (url)
        )
        ''')
        
        # Table for entities
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            entity_type TEXT,
            source_url TEXT,
            source_text TEXT,
            FOREIGN KEY (source_url) REFERENCES crawled_urls (url)
        )
        ''')
        
        # Table for relationships
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            predicate TEXT,
            object TEXT,
            source_url TEXT,
            source_text TEXT,
            FOREIGN KEY (source_url) REFERENCES crawled_urls (url)
        )
        ''')
        
        # Table for knowledge graph facts
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS knowledge_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact_statement TEXT,
            category TEXT,
            tags TEXT,
            date_recorded TIMESTAMP,
            last_updated TIMESTAMP,
            reliability_rating TEXT,
            source_url TEXT,
            source_title TEXT,
            FOREIGN KEY (source_url) REFERENCES crawled_urls (url)
        )
        ''')
        
        # Table for URL crawl history
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS url_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            timestamp REAL,
            content_hash TEXT,
            http_status INTEGER,
            FOREIGN KEY (url) REFERENCES crawled_urls (url)
        )
        ''')
        
        # Table for content metadata
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS content_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            categories TEXT,
            tags TEXT,
            FOREIGN KEY (url) REFERENCES crawled_urls (url)
        )
        ''')
        
        # Table for crawl statistics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS crawl_statistics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            urls_crawled INTEGER,
            new_facts_added INTEGER,
            entities_found INTEGER,
            relationships_found INTEGER,
            errors_encountered INTEGER
        )
        ''')
        
        self.conn.commit()
        
    def save_crawl_result(self, url, content, entities=None, relationships=None):
        """Save crawl results to database."""
        cursor = self.conn.cursor()
        
        # Save URL info
        cursor.execute('''
        INSERT OR REPLACE INTO crawled_urls 
        (url, domain, last_crawled, content_hash, title, http_status)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            url,
            content.get('domain', urlparse(url).netloc),
            time.time(),
            hashlib.md5(str(content).encode()).hexdigest(),
            content.get('title', ''),
            200  # Assuming successful crawl
        ))
        
        # Save content elements
        for element in content.get('content_elements', []):
            cursor.execute('''
            INSERT INTO content_elements
            (url, element_type, text, html_class, html_id)
            VALUES (?, ?, ?, ?, ?)
            ''', (
                url,
                element.get('type', ''),
                element.get('text', ''),
                ','.join(element.get('html_class', [])),
                element.get('html_id', '')
            ))
            
        # Generate and save knowledge facts
        for element in content.get('content_elements', []):
            text = element.get('text', '')
            if len(text) > 20:  # Only consider substantial text
                cursor.execute('''
                INSERT INTO knowledge_facts
                (fact_statement, category, tags, date_recorded, last_updated, 
                reliability_rating, source_url, source_title)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    text,
                    "General",
                    content.get('domain', urlparse(url).netloc),
                    time.time(),
                    time.time(),
                    ReliabilityRating.LIKELY_TRUE,
                    url,
                    content.get('title', '')
                ))
        
        self.conn.commit()
        
    def export_knowledge_graph(self, output_file):
        """Export knowledge graph to JSON file."""
        cursor = self.conn.cursor()
        
        # Get all facts
        cursor.execute("SELECT * FROM knowledge_facts")
        facts = cursor.fetchall()
        
        # Create graph structure
        graph = {
            "nodes": [],
            "edges": [],
            "metadata": {
                "exported_at": datetime.now().isoformat(),
                "fact_count": len(facts)
            }
        }
        
        # Add facts as nodes
        for fact in facts:
            graph["nodes"].append({
                "id": fact[0],
                "statement": fact[1],
                "category": fact[2],
                "reliability": fact[6],
                "source_url": fact[7]
            })
                
        # Write to file
        with open(output_file, 'w') as f:
            json.dump(graph, f, indent=2)
            
        return len(facts)

class EnhancedCrawler:
    """Enhanced web crawler with depth control and politeness"""
    def __init__(self, start_urls=None, max_depth=2, max_pages_per_domain=10):
        self.start_urls = start_urls or []
        self.max_depth = max_depth
        self.max_pages_per_domain = max_pages_per_domain
        self.visited_urls = set()
        self.url_queue = deque()
        self.domain_page_counts = defaultdict(int)
        self.user_agent = 'KnowledgeReduce Test Crawler/1.0'
        self.delay = 1  # seconds between requests to same domain
        self.last_request_time = {}  # domain -> timestamp
        
    def add_start_url(self, url):
        """Add a starting URL to the crawler."""
        self.start_urls.append(url)
        
    def extract_domain(self, url):
        """Extract domain from URL."""
        parsed_url = urlparse(url)
        return parsed_url.netloc
        
    def should_crawl(self, url, depth):
        """Determine if a URL should be crawled based on constraints."""
        if depth > self.max_depth:
            return False
            
        domain = self.extract_domain(url)
        if self.domain_page_counts[domain] >= self.max_pages_per_domain:
            return False
            
        if url in self.visited_urls:
            return False
            
        return True
        
    def rate_limit(self, domain):
        """Implement rate limiting for polite crawling."""
        current_time = time.time()
        if domain in self.last_request_time:
            elapsed = current_time - self.last_request_time[domain]
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
        self.last_request_time[domain] = time.time()
        
    def extract_links(self, soup, base_url):
        """Extract links from a page."""
        links = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            # Convert relative URLs to absolute
            absolute_url = urljoin(base_url, href)
            # Filter out non-HTTP/HTTPS URLs and anchors
            if absolute_url.startswith(('http://', 'https://')) and '#' not in absolute_url:
                links.append(absolute_url)
        return links
        
    def crawl(self):
        """Start the crawling process."""
        # Initialize queue with start URLs
        for url in self.start_urls:
            self.url_queue.append((url, 0))  # (url, depth)
            
        while self.url_queue:
            url, depth = self.url_queue.popleft()
            
            if not self.should_crawl(url, depth):
                continue
                
            domain = self.extract_domain(url)
            self.rate_limit(domain)
            
            try:
                print(f"Crawling {url} (depth {depth})")
                response = requests.get(url, headers={'User-Agent': self.user_agent}, timeout=10)
                response.raise_for_status()
                
                self.visited_urls.add(url)
                self.domain_page_counts[domain] += 1
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Process the page content
                yield url, soup
                
                # Add new links to the queue
                if depth < self.max_depth:
                    links = self.extract_links(soup, url)
                    for link in links:
                        if link not in self.visited_urls:
                            self.url_queue.append((link, depth + 1))
                            
            except Exception as e:
                print(f"Error crawling {url}: {e}")

class ContentExtractor:
    """Extracts structured content from web pages"""
    def __init__(self, site_specific_rules=None):
        self.site_specific_rules = site_specific_rules or {}
        
    def add_site_rule(self, domain, selectors):
        """Add site-specific CSS selectors for content extraction."""
        self.site_specific_rules[domain] = selectors
        
    def get_site_rules(self, domain):
        """Get site-specific rules or return default rules."""
        return self.site_specific_rules.get(domain, {
            'content': ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'table', 'dl', 'blockquote'],
            'title': ['title', 'h1.title', '.page-title', '.post-title', 'h1'],
            'date': ['.date', '.published', 'time', '.post-date'],
            'author': ['.author', '.byline', '.post-author']
        })
        
    def extract_structured_content(self, soup, url):
        """Extract structured content from a page."""
        domain = urlparse(url).netloc
        rules = self.get_site_rules(domain)
        
        result = {
            'url': url,
            'domain': domain,
            'title': None,
            'date': None,
            'author': None,
            'content_elements': [],
            'hierarchical_content': {}
        }
        
        # Extract title
        for selector in rules['title']:
            try:
                title_elem = soup.select_one(selector)
                if title_elem and title_elem.text.strip():
                    result['title'] = title_elem.text.strip()
                    break
            except Exception:
                continue
                
        # Extract date
        for selector in rules['date']:
            try:
                date_elem = soup.select_one(selector)
                if date_elem and date_elem.text.strip():
                    result['date'] = date_elem.text.strip()
                    break
            except Exception:
                continue
                
        # Extract author
        for selector in rules['author']:
            try:
                author_elem = soup.select_one(selector)
                if author_elem and author_elem.text.strip():
                    result['author'] = author_elem.text.strip()
                    break
            except Exception:
                continue
                
        # Extract content elements
        for selector in rules['content']:
            try:
                elements = soup.select(selector)
                for elem in elements:
                    text = ' '.join(elem.stripped_strings)
                    if text:
                        result['content_elements'].append({
                            'type': elem.name,
                            'text': text,
                            'html_class': elem.get('class', []),
                            'html_id': elem.get('id', '')
                        })
            except Exception:
                continue
                    
        return result

class KnowledgeReduceTest:
    """Test implementation of the enhanced KnowledgeReduce system"""
    def __init__(self, db_path="test_results/knowledge_reduce.db"):
        """Initialize the test system."""
        self.db = KnowledgeDatabase(db_path)
        self.crawler = EnhancedCrawler()
        self.content_extractor = ContentExtractor()
        
    def add_start_url(self, url):
        """Add a starting URL for crawling."""
        self.crawler.add_start_url(url)
        
    def add_site_specific_rules(self, domain, rules):
        """Add site-specific extraction rules."""
        self.content_extractor.add_site_rule(domain, rules)
        
    def run(self, max_pages=10):
        """Run the test implementation."""
        pages_processed = 0
        start_time = time.time()
        
        stats = {
            'urls_crawled': 0,
            'facts_added': 0,
            'start_time': start_time
        }
        
        for url, soup in self.crawler.crawl():
            if pages_processed >= max_pages:
                break
                
            try:
                # Extract structured content
                content = self.content_extractor.extract_structured_content(soup, url)
                
                # Save to database
                self.db.save_crawl_result(url, content)
                
                pages_processed += 1
                stats['urls_crawled'] += 1
                stats['facts_added'] += len(content['content_elements'])
                
                print(f"Processed {url} ({pages_processed}/{max_pages})")
                print(f"  Title: {content.get('title', 'Unknown')}")
                print(f"  Content elements: {len(content.get('content_elements', []))}")
                
            except Exception as e:
                print(f"Error processing {url}: {e}")
                
        end_time = time.time()
        stats['end_time'] = end_time
        stats['duration'] = end_time - start_time
        
        print(f"\nCrawling complete. Processed {pages_processed} pages in {stats['duration']:.2f} seconds.")
        print(f"Total facts added: {stats['facts_added']}")
        
        # Export the knowledge graph
        output_file = "test_results/knowledge_graph.json"
        fact_count = self.db.export_knowledge_graph(output_file)
        print(f"Knowledge graph exported to {output_file} with {fact_count} facts.")
        
        # Save stats
        with open("test_results/crawl_stats.json", "w") as f:
            json.dump(stats, f, indent=2)
            
        return stats

def main():
    """Main function to run the test implementation."""
    print("Starting KnowledgeReduce Test Implementation")
    
    # Initialize the test system
    kr = KnowledgeReduceTest()
    
    # Add starting URLs
    kr.add_start_url("https://en.wikipedia.org/wiki/Knowledge_graph")
    kr.add_start_url("https://en.wikipedia.org/wiki/Web_crawler")
    kr.add_start_url("https://en.wikipedia.org/wiki/Natural_language_processing")
    
    # Add site-specific rules for Wikipedia
    kr.add_site_specific_rules("en.wikipedia.org", {
        'content': ['p', '.mw-parser-output > p', '.mw-parser-output > h2', '.mw-parser-output > h3', '.mw-parser-output > ul > li'],
        'title': ['h1#firstHeading'],
        'date': ['.lastmod'],
        'author': []  # Wikipedia doesn't have clear author information
    })
    
    # Run the test implementation
    kr.run(max_pages=10)
    
    print("\nTest implementation completed successfully.")

if __name__ == "__main__":
    main()
