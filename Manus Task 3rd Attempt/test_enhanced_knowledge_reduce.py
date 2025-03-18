#!/usr/bin/env python3
"""
Test script for the Enhanced KnowledgeReduce technique.
This script demonstrates the improvements made to the original KnowledgeReduce technique,
including enhanced crawling capabilities and database growth mechanisms.
"""

import os
import time
import json
import sqlite3
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import hashlib
from collections import deque, defaultdict
import re
from datetime import datetime

# Create necessary directories
os.makedirs("knowledge_reduce_test", exist_ok=True)
os.makedirs("knowledge_reduce_test/db", exist_ok=True)

print("Enhanced KnowledgeReduce Test Implementation")
print("===========================================")

# Simplified implementation of the enhanced components for testing

class ReliabilityRating:
    """Enum for reliability ratings."""
    LIKELY_TRUE = 'Likely True'
    POSSIBLY_TRUE = 'Possibly True'
    UNCERTAIN = 'Uncertain'
    POSSIBLY_FALSE = 'Possibly False'
    LIKELY_FALSE = 'Likely False'

class EnhancedCrawler:
    """Enhanced crawler with depth control and politeness."""
    
    def __init__(self, start_urls=None, max_depth=2, max_pages_per_domain=5):
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
        print(f"Added start URL: {url}")
    
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
                print(f"Crawling: {url} (depth {depth})")
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
                            
            except requests.exceptions.RequestException as e:
                print(f"Error crawling {url}: {e}")

class ContentExtractor:
    """Enhanced content extractor with site-specific rules."""
    
    def __init__(self, site_specific_rules=None):
        self.site_specific_rules = site_specific_rules or {}
    
    def add_site_rule(self, domain, selectors):
        """Add site-specific CSS selectors for content extraction."""
        self.site_specific_rules[domain] = selectors
        print(f"Added site-specific rules for {domain}")
    
    def get_site_rules(self, domain):
        """Get site-specific rules or return default rules."""
        return self.site_specific_rules.get(domain, {
            'content': ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'table', 'dl', 'blockquote'],
            'title': ['title', 'h1.title', '.page-title', '.post-title'],
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
            title_elem = soup.select_one(selector)
            if title_elem and title_elem.text.strip():
                result['title'] = title_elem.text.strip()
                break
                
        # Extract date
        for selector in rules['date']:
            date_elem = soup.select_one(selector)
            if date_elem and date_elem.text.strip():
                result['date'] = date_elem.text.strip()
                break
                
        # Extract author
        for selector in rules['author']:
            author_elem = soup.select_one(selector)
            if author_elem and author_elem.text.strip():
                result['author'] = author_elem.text.strip()
                break
                
        # Extract content elements
        for selector in rules['content']:
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
        
        return result

class EntityExtractor:
    """Simple entity extractor for testing."""
    
    def __init__(self):
        # Simple patterns for entity extraction
        self.patterns = {
            'PERSON': r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',
            'ORG': r'\b[A-Z][a-z]* (Inc|Corp|Company|Organization|Foundation)\b',
            'GPE': r'\b(United States|USA|UK|China|Russia|Germany|France|Japan)\b',
            'DATE': r'\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b(January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}\b'
        }
    
    def extract_entities(self, text):
        """Extract entities from text using simple patterns."""
        entities = []
        
        for entity_type, pattern in self.patterns.items():
            for match in re.finditer(pattern, text):
                entities.append({
                    'text': match.group(0),
                    'label': entity_type,
                    'start': match.start(),
                    'end': match.end()
                })
        
        return entities
    
    def extract_relationships(self, text):
        """Extract simple subject-verb-object relationships."""
        # This is a very simplified implementation
        relationships = []
        
        # Look for patterns like "X is Y" or "X has Y"
        is_pattern = r'([A-Z][a-z]+ [A-Z][a-z]+) is ([a-z]+)'
        has_pattern = r'([A-Z][a-z]+ [A-Z][a-z]+) has ([a-z]+)'
        
        for match in re.finditer(is_pattern, text):
            relationships.append({
                'subject': match.group(1),
                'predicate': 'is',
                'object': match.group(2)
            })
            
        for match in re.finditer(has_pattern, text):
            relationships.append({
                'subject': match.group(1),
                'predicate': 'has',
                'object': match.group(2)
            })
        
        return relationships
    
    def process_content(self, content):
        """Process extracted content to identify entities and relationships."""
        results = {
            'entities': [],
            'relationships': []
        }
        
        # Process each content element
        for element in content['content_elements']:
            text = element['text']
            
            # Extract entities
            entities = self.extract_entities(text)
            for entity in entities:
                entity['source_text'] = text
                results['entities'].append(entity)
                
            # Extract relationships
            relationships = self.extract_relationships(text)
            for rel in relationships:
                rel['source_text'] = text
                results['relationships'].append(rel)
                
        return results

class KnowledgeDatabase:
    """Database for storing knowledge graph data."""
    
    def __init__(self, db_path):
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
            http_status INTEGER
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
            source_title TEXT
        )
        ''')
        
        self.conn.commit()
        print("Database tables created")
    
    def save_crawl_result(self, url, content, entities, relationships):
        """Save crawl results to database."""
        cursor = self.conn.cursor()
        
        # Save URL info
        cursor.execute('''
        INSERT OR REPLACE INTO crawled_urls 
        (url, domain, last_crawled, content_hash, title, http_status)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            url,
            content['domain'],
            time.time(),
            hashlib.md5(str(content).encode()).hexdigest(),
            content['title'],
            200  # Assuming successful crawl
        ))
        
        # Save content elements
        for element in content['content_elements']:
            cursor.execute('''
            INSERT INTO content_elements
            (url, element_type, text, html_class, html_id)
            VALUES (?, ?, ?, ?, ?)
            ''', (
                url,
                element['type'],
                element['text'],
                ','.join(element['html_class']),
                element['html_id']
            ))
            
        # Save entities
        for entity in entities:
            cursor.execute('''
            INSERT INTO entities
            (text, entity_type, source_url, source_text)
            VALUES (?, ?, ?, ?)
            ''', (
                entity['text'],
                entity['label'],
                url,
                entity['source_text']
            ))
            
        # Save relationships
        for rel in relationships:
            cursor.execute('''
            INSERT INTO relationships
            (subject, predicate, object, source_url, source_text)
            VALUES (?, ?, ?, ?, ?)
            ''', (
                rel['subject'],
                rel['predicate'],
                rel['object'],
                url,
                rel['source_text']
            ))
            
        # Generate and save knowledge facts
        self.generate_knowledge_facts(url, content, entities, relationships)
        
        self.conn.commit()
        print(f"Saved crawl results for {url}")
    
    def generate_knowledge_facts(self, url, content, entities, relationships):
        """Generate knowledge facts from extracted content and relationships."""
        cursor = self.conn.cursor()
        
        # Convert relationships to facts
        for rel in relationships:
            fact_statement = f"{rel['subject']} {rel['predicate']} {rel['object']}"
            
            # Determine category based on entity types
            category = "General"
            for entity in entities:
                if entity['text'] in rel['subject'] or entity['text'] in rel['object']:
                    category = entity['label']
                    break
                    
            cursor.execute('''
            INSERT INTO knowledge_facts
            (fact_statement, category, tags, date_recorded, last_updated, 
             reliability_rating, source_url, source_title)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                fact_statement,
                category,
                content['domain'],
                time.time(),
                time.time(),
                ReliabilityRating.LIKELY_TRUE,
                url,
                content['title'] or url
            ))
        
        # Also create facts from content elements
        for element in content['content_elements']:
            # Only use paragraphs as facts
            if element['type'] == 'p' and len(element['text']) > 50:
                cursor.execute('''
                INSERT INTO knowledge_facts
                (fact_statement, category, tags, date_recorded, last_updated, 
                 reliability_rating, source_url, source_title)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    element['text'],
                    "Content",
                    content['domain'],
                    time.time(),
                    time.time(),
                    ReliabilityRating.POSSIBLY_TRUE,
                    url,
                    content['title'] or url
                ))

class ContentCategorizer:
    """Simple content categorizer for testing."""
    
    def __init__(self):
        self.categories = {
            'technology': ['computer', 'software', 'hardware', 'internet', 'digital', 'tech', 'AI', 'data'],
            'science': ['research', 'study', 'scientific', 'biology', 'physics', 'chemistry', 'experiment'],
            'business': ['company', 'market', 'finance', 'economy', 'industry', 'investment', 'startup'],
            'health': ['medical', 'health', 'disease', 'treatment', 'doctor', 'patient', 'medicine']
        }
    
    def categorize_text(self, text):
        """Categorize text into predefined categories."""
        text_lower = text.lower()
        scores = {category: 0 for category in self.categories}
        
        # Count category keywords
        for category, keywords in self.categories.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    scores[category] += 1
                    
        # Get top categories
        sorted_categories = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Return categories with non-zero scores
        return [category for category, score in sorted_categories if score > 0]
    
    def extract_tags(self, text, max_tags=5):
        """Extract relevant tags from text."""
        # Simple implementation using word frequency
        words = re.findall(r'\b[A-Za-z]{4,}\b', text.lower())
        word_counts = {}
        
        for word in words:
            word_counts[word] = word_counts.get(word, 0) + 1
            
        # Sort by frequency
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Return top tags
        return [word for word, _ in sorted_words[:max_tags]]
    
    def process_content(self, content):
        """Process content to add categories and tags."""
        # Combine all text for categorization
        all_text = ' '.join([elem['text'] for elem in content['content_elements']])
        
        # Get categories
        categories = self.categorize_text(all_text)
        if not categories:
            categories = ['General']
        
        # Get tags
        tags = self.extract_tags(all_text)
        
        # Add to content
        content['categories'] = categories
        content['tags'] = tags
        
        return content

class KnowledgeGraphExpander:
    """Simple knowledge graph expander for testing."""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def find_entity_connections(self):
        """Find connections between entities based on co-occurrence."""
        cursor = self.db.conn.cursor()
        
        # Find entities that co-occur in the same fact
        cursor.execute('''
        SELECT COUNT(*) FROM entities
        ''')
        entity_count = cursor.fetchone()[0]
        
        if entity_count < 2:
            print("Not enough entities to find connections")
            return 0
        
        cursor.execute('''
        SELECT e1.id, e2.id, e1.text, e2.text, e1.source_url
        FROM entities e1
        JOIN entities e2 ON e1.source_url = e2.source_url
        WHERE e1.id < e2.id  -- Avoid duplicates
        AND e1.text != e2.text  -- Avoid self-connections
        LIMIT 100
        ''')
        
        co_occurrences = cursor.fetchall()
        print(f"Found {len(co_occurrences)} entity co-occurrences")
        
        return len(co_occurrences)
    
    def infer_new_relationships(self):
        """Infer new relationships based on existing ones."""
        cursor = self.db.conn.cursor()
        
        # Count existing relationships
        cursor.execute('SELECT COUNT(*) FROM relationships')
        relationship_count = cursor.fetchone()[0]
        
        if relationship_count < 2:
            print("Not enough relationships to infer new ones")
            return 0
        
        # Find potential transitive relationships
        cursor.execute('''
        SELECT r1.subject, r2.object, r1.predicate
        FROM relationships r1
        JOIN relationships r2 ON r1.object = r2.subject
        WHERE r1.predicate = r2.predicate
        LIMIT 10
        ''')
        
        inferred = cursor.fetchall()
        print(f"Inferred {len(inferred)} new relationships")
        
        # We're not actually storing these in this simplified test
        return len(inferred)

class EnhancedKnowledgeReduce:
    """Main class for the Enhanced KnowledgeReduce implementation."""
    
    def __init__(self, db_path="knowledge_reduce_test/db/knowledge.db"):
        """Initialize the enhanced KnowledgeReduce system."""
        self.db = KnowledgeDatabase(db_path)
        self.crawler = EnhancedCrawler()
        self.content_extractor = ContentExtractor()
        self.entity_extractor = EntityExtractor()
        self.content_categorizer = ContentCategorizer()
        self.graph_expander = KnowledgeGraphExpander(self.db)
    
    def add_start_url(self, url):
        """Add a starting URL for crawling."""
        self.crawler.add_start_url(url)
    
    def add_site_specific_rules(self, domain, rules):
        """Add site-specific extraction rules."""
        self.content_extractor.add_site_rule(domain, rules)
    
    def run(self, max_pages=10):
        """Run the enhanced KnowledgeReduce process."""
        pages_processed = 0
        
        for url, soup in self.crawler.crawl():
            if pages_processed >= max_pages:
                break
                
            try:
                # Extract structured content
                content = self.content_extractor.extract_structured_content(soup, url)
                
                # Categorize and tag content
                content = self.content_categorizer.process_content(content)
                
                # Extract entities and relationships
                extraction_results = self.entity_extractor.process_content(content)
                
                # Save to database
                self.db.save_crawl_result(
                    url,
                    content,
                    extraction_results['entities'],
                    extraction_results['relationships']
                )
                
                pages_processed += 1
                print(f"Processed {url} ({pages_processed}/{max_pages})")
                
            except Exception as e:
                print(f"Error processing {url}: {e}")
                
        print(f"Crawling complete. Processed {pages_processed} pages.")
        
        # Expand the knowledge graph
        print("\nExpanding knowledge graph...")
        self.graph_expander.find_entity_connections()
        self.graph_expander.infer_new_relationships()
    
    def query_facts(self, keyword=None, category=None, limit=10):
        """Query facts from the knowledge graph."""
        cursor = self.db.conn.cursor()
        
        query = "SELECT id, fact_statement, category, source_url FROM knowledge_facts"
        params = []
        
        if keyword or category:
            query += " WHERE "
            conditions = []
            
            if keyword:
                conditions.append("fact_statement LIKE ?")
                params.append(f"%{keyword}%")
                
            if category:
                conditions.append("category = ?")
                params.append(category)
                
            query += " AND ".join(conditions)
            
        query += f" LIMIT {limit}"
        
        cursor.execute(query, params)
        return cursor.fetchall()
    
    def export_knowledge_graph(self, output_file="knowledge_reduce_test/knowledge_graph.json"):
        """Export the knowledge graph to a JSON file."""
        cursor = self.db.conn.cursor()
        
        # Get all facts
        cursor.execute("SELECT id, fact_statement, category FROM knowledge_facts")
        facts = cursor.fetchall()
        
        # Get all entities
        cursor.execute("SELECT id, text, entity_type FROM entities")
        entities = cursor.fetchall()
        
        # Get all relationships
        cursor.execute("SELECT id, subject, predicate, object FROM relationships")
        relationships = cursor.fetchall()
        
        # Create graph structure
        graph = {
            "nodes": [],
            "edges": []
        }
        
        # Add facts as nodes
        for fact_id, statement, category in facts:
            graph["nodes"].append({
                "id": f"fact_{fact_id}",
                "label": statement[:50] + "..." if len(statement) > 50 else statement,
                "type": "fact",
                "category": category
            })
        
        # Add entities as nodes
        for entity_id, text, entity_type in entities:
            graph["nodes"].append({
                "id": f"entity_{entity_id}",
                "label": text,
                "type": "entity",
                "category": entity_type
            })
        
        # Add relationships as edges
        for rel_id, subject, predicate, obj in relationships:
            # Find nodes for subject and object
            subject_nodes = [node["id"] for node in graph["nodes"] if subject in node["label"]]
            object_nodes = [node["id"] for node in graph["nodes"] if obj in node["label"]]
            
            for s_node in subject_nodes:
                for o_node in object_nodes:
                    if s_node != o_node:
                        graph["edges"].append({
                            "source": s_node,
                            "target": o_node,
                            "label": predicate
                        })
        
        # Write to file
        with open(output_file, 'w') as f:
            json.dump(graph, f, indent=2)
            
        print(f"Knowledge graph exported to {output_file}")
        print(f"Graph contains {len(graph['nodes'])} nodes and {len(graph['edges'])} edges")
        
        return output_file
    
    def generate_statistics(self):
        """Generate statistics about the knowledge graph."""
        cursor = self.db.conn.cursor()
        
        stats = {}
        
        # Count records in each table
        tables = ['crawled_urls', 'content_elements', 'entities', 'relationships', 'knowledge_facts']
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            stats[f"{table}_count"] = cursor.fetchone()[0]
        
        # Get entity type distribution
        cursor.execute('''
        SELECT entity_type, COUNT(*) as count
        FROM entities
        GROUP BY entity_type
        ORDER BY count DESC
        ''')
        
        stats['entity_distribution'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Get category distribution
        cursor.execute('''
        SELECT category, COUNT(*) as count
        FROM knowledge_facts
        GROUP BY category
        ORDER BY count DESC
        ''')
        
        stats['category_distribution'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Get domain distribution
        cursor.execute('''
        SELECT domain, COUNT(*) as count
        FROM crawled_urls
        GROUP BY domain
        ORDER BY count DESC
        ''')
        
        stats['domain_distribution'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        return stats

# Run the test
if __name__ == "__main__":
    # Initialize the enhanced KnowledgeReduce system
    kr = EnhancedKnowledgeReduce()
    
    # Add starting URLs
    kr.add_start_url("https://en.wikipedia.org/wiki/Knowledge_graph")
    kr.add_start_url("https://en.wikipedia.org/wiki/Web_crawler")
    
    # Add site-specific rules for Wikipedia
    kr.add_site_specific_rules("en.wikipedia.org", {
        'content': ['p', '.mw-parser-output > p', '.mw-parser-output > h2', '.mw-parser-output > h3', '.mw-parser-output > ul > li'],
        'title': ['h1#firstHeading'],
        'date': ['.lastmod'],
        'author': []  # Wikipedia doesn't have clear author information
    })
    
    print("\nStarting crawl process...")
    # Run the crawler (limit to 5 pages for testing)
    kr.run(max_pages=5)
    
    print("\nQuerying knowledge graph...")
    # Query facts about knowledge graphs
    knowledge_graph_facts = kr.query_facts(keyword="knowledge graph")
    print("\nFacts about knowledge graphs:")
    for fact in knowledge_graph_facts:
        print(f"- {fact[1][:100]}..." if len(fact[1]) > 100 else f"- {fact[1]}")
    
    # Query facts about web crawlers
    web_crawler_facts = kr.query_facts(keyword="crawler")
    print("\nFacts about web crawlers:")
    for fact in web_crawler_facts:
        print(f"- {fact[1][:100]}..." if len(fact[1]) > 100 else f"- {fact[1]}")
    
    print("\nGenerating statistics...")
    # Generate statistics
    stats = kr.generate_statistics()
    print("\nKnowledge Graph Statistics:")
    print(f"- Crawled URLs: {stats['crawled_urls_count']}")
    print(f"- Content Elements: {stats['content_elements_count']}")
    print(f"- Entities: {stats['entities_count']}")
    print(f"- Relationships: {stats['relationships_count']}")
    print(f"- Knowledge Facts: {stats['knowledge_facts_count']}")
    
    print("\nEntity Type Distribution:")
    for entity_type, count in stats.get('entity_distribution', {}).items():
        print(f"- {entity_type}: {count}")
    
    print("\nCategory Distribution:")
    for category, count in stats.get('category_distribution', {}).items():
        print(f"- {category}: {count}")
    
    print("\nExporting knowledge graph...")
    # Export the knowledge graph
    graph_file = kr.export_knowledge_graph()
    
    print("\nTest completed successfully!")
    print(f"Knowledge graph exported to: {graph_file}")
