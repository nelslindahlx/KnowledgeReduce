# Enhanced Crawling Strategy for KnowledgeReduce

This document outlines an enhanced crawling strategy to address the limitations identified in the original KnowledgeReduce technique. The strategy focuses on improving web crawling capabilities and database growth mechanisms.

## 1. Recursive Crawling with Depth Control

```python
class EnhancedCrawler:
    def __init__(self, start_urls=None, max_depth=2, max_pages_per_domain=100):
        self.start_urls = start_urls or []
        self.max_depth = max_depth
        self.max_pages_per_domain = max_pages_per_domain
        self.visited_urls = set()
        self.url_queue = deque()
        self.domain_page_counts = defaultdict(int)
        self.user_agent = 'KnowledgeReduce Crawler/1.0'
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
        
    def respect_robots_txt(self, url):
        """Check if crawling is allowed by robots.txt."""
        domain = self.extract_domain(url)
        robots_parser = RobotFileParser()
        robots_parser.set_url(f"https://{domain}/robots.txt")
        try:
            robots_parser.read()
            return robots_parser.can_fetch(self.user_agent, url)
        except:
            # If robots.txt cannot be read, assume crawling is allowed
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
                
            if not self.respect_robots_txt(url):
                continue
                
            domain = self.extract_domain(url)
            self.rate_limit(domain)
            
            try:
                response = requests.get(url, headers={'User-Agent': self.user_agent})
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
```

## 2. Enhanced HTML Element Extraction

```python
class ContentExtractor:
    def __init__(self, site_specific_rules=None):
        self.site_specific_rules = site_specific_rules or {}
        
    def add_site_rule(self, domain, selectors):
        """Add site-specific CSS selectors for content extraction."""
        self.site_specific_rules[domain] = selectors
        
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
                    
        # Build hierarchical content structure
        current_section = None
        for elem in result['content_elements']:
            if elem['type'].startswith('h'):
                level = int(elem['type'][1])
                if current_section is None or current_section['level'] >= level:
                    # Start a new top-level section
                    current_section = {
                        'title': elem['text'],
                        'level': level,
                        'content': [],
                        'subsections': []
                    }
                    result['hierarchical_content'][elem['text']] = current_section
                else:
                    # Add as subsection to current section
                    subsection = {
                        'title': elem['text'],
                        'level': level,
                        'content': [],
                        'subsections': []
                    }
                    current_section['subsections'].append(subsection)
                    current_section = subsection
            elif current_section is not None:
                # Add content to current section
                current_section['content'].append(elem['text'])
                
        return result
```

## 3. Incremental Updates and Change Detection

```python
class IncrementalCrawler:
    def __init__(self, db_connection):
        self.db = db_connection
        self.crawler = EnhancedCrawler()
        self.extractor = ContentExtractor()
        
    def get_last_crawl_info(self, url):
        """Get information about the last crawl of a URL."""
        # Implementation depends on database schema
        # Return None if URL was never crawled
        # Otherwise return timestamp and content hash
        pass
        
    def compute_content_hash(self, content):
        """Compute a hash of the content for change detection."""
        return hashlib.md5(str(content).encode()).hexdigest()
        
    def save_crawl_info(self, url, content_hash, timestamp):
        """Save information about a crawl."""
        # Implementation depends on database schema
        pass
        
    def process_url(self, url, force_update=False):
        """Process a URL with change detection."""
        last_crawl = self.get_last_crawl_info(url)
        
        if not force_update and last_crawl:
            # Check if enough time has passed since last crawl
            last_timestamp = last_crawl['timestamp']
            current_time = time.time()
            
            # Skip if crawled recently (e.g., within last day)
            if current_time - last_timestamp < 86400:  # 24 hours
                return None
                
        # Crawl the URL
        response = requests.get(url, headers={'User-Agent': self.crawler.user_agent})
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract content
        content = self.extractor.extract_structured_content(soup, url)
        content_hash = self.compute_content_hash(content)
        
        # Check if content has changed
        if not force_update and last_crawl and content_hash == last_crawl['content_hash']:
            # Content hasn't changed, just update timestamp
            self.save_crawl_info(url, content_hash, time.time())
            return None
            
        # Content is new or has changed
        self.save_crawl_info(url, content_hash, time.time())
        return content
```

## 4. Advanced Entity Recognition and Relationship Extraction

```python
class EntityRelationshipExtractor:
    def __init__(self):
        # Load spaCy model with NER capabilities
        self.nlp = spacy.load("en_core_web_lg")
        
    def extract_entities(self, text):
        """Extract named entities from text."""
        doc = self.nlp(text)
        entities = []
        
        for ent in doc.ents:
            entities.append({
                'text': ent.text,
                'label': ent.label_,
                'start': ent.start_char,
                'end': ent.end_char
            })
            
        return entities
        
    def extract_relationships(self, text):
        """Extract relationships between entities."""
        doc = self.nlp(text)
        relationships = []
        
        # Extract subject-verb-object triples
        for sent in doc.sents:
            triples = []
            
            # Find the root verb
            root = None
            for token in sent:
                if token.dep_ == "ROOT" and token.pos_ == "VERB":
                    root = token
                    break
                    
            if root:
                # Find subject
                subject = None
                for child in root.children:
                    if child.dep_ in ("nsubj", "nsubjpass"):
                        subject = child
                        # Expand to include the full noun phrase
                        subject_phrase = ' '.join([w.text for w in subject.subtree])
                        break
                        
                # Find object
                obj = None
                for child in root.children:
                    if child.dep_ in ("dobj", "pobj"):
                        obj = child
                        # Expand to include the full noun phrase
                        object_phrase = ' '.join([w.text for w in obj.subtree])
                        break
                        
                if subject and obj:
                    relationships.append({
                        'subject': subject_phrase,
                        'predicate': root.text,
                        'object': object_phrase
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
```

## 5. Database Integration for Scalability

```python
class KnowledgeDatabase:
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
            source_title TEXT,
            FOREIGN KEY (source_url) REFERENCES crawled_urls (url)
        )
        ''')
        
        self.conn.commit()
        
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
                "LIKELY_TRUE",
                url,
                content['title']
            ))
            
    def query_facts(self, category=None, keywords=None, limit=100):
        """Query knowledge facts from database."""
        cursor = self.conn.cursor()
        
        query = "SELECT * FROM knowledge_facts"
        params = []
        
        if category or keywords:
            query += " WHERE "
            conditions = []
            
            if category:
                conditions.append("category = ?")
                params.append(category)
                
            if keywords:
                keyword_conditions = []
                for keyword in keywords:
                    keyword_conditions.append("fact_statement LIKE ?")
                    params.append(f"%{keyword}%")
                conditions.append("(" + " OR ".join(keyword_conditions) + ")")
                
            query += " AND ".join(conditions)
            
        query += f" LIMIT {limit}"
        
        cursor.execute(query, params)
        return cursor.fetchall()
        
    def export_knowledge_graph(self, output_file):
        """Export knowledge graph to JSON file."""
        cursor = self.conn.cursor()
        
        # Get all facts
        cursor.execute("SELECT * FROM knowledge_facts")
        facts = cursor.fetchall()
        
        # Get all relationships
        cursor.execute("SELECT * FROM relationships")
        relationships = cursor.fetchall()
        
        # Create graph structure
        graph = {
            "nodes": [],
            "edges": []
        }
        
        # Add facts as nodes
        for fact in facts:
            graph["nodes"].append({
                "id": fact[0],
                "label": fact[1],
                "category": fact[2],
                "type": "fact"
            })
            
        # Add relationships as edges
        for rel in relationships:
            # Find nodes for subject and object
            subject_node = None
            object_node = None
            
            for node in graph["nodes"]:
                if rel[1] in node["label"]:
                    subject_node = node["id"]
                if rel[3] in node["label"]:
                    object_node = node["id"]
                    
            if subject_node and object_node:
                graph["edges"].append({
                    "source": subject_node,
                    "target": object_node,
                    "label": rel[2]
                })
                
        # Write to file
        with open(output_file, 'w') as f:
            json.dump(graph, f, indent=2)
```

## 6. Main Orchestration Class

```python
class KnowledgeReduceEnhanced:
    def __init__(self, db_path="knowledge_reduce.db"):
        """Initialize the enhanced KnowledgeReduce system."""
        self.db = KnowledgeDatabase(db_path)
        self.crawler = EnhancedCrawler()
        self.content_extractor = ContentExtractor()
        self.entity_extractor = EntityRelationshipExtractor()
        
    def add_start_url(self, url):
        """Add a starting URL for crawling."""
        self.crawler.add_start_url(url)
        
    def add_site_specific_rules(self, domain, rules):
        """Add site-specific extraction rules."""
        self.content_extractor.add_site_rule(domain, rules)
        
    def run(self, max_pages=100):
        """Run the enhanced KnowledgeReduce process."""
        pages_processed = 0
        
        for url, soup in self.crawler.crawl():
            if pages_processed >= max_pages:
                break
                
            try:
                # Extract structured content
                content = self.content_extractor.extract_structured_content(soup, url)
                
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
        
    def export_knowledge_graph(self, output_file="knowledge_graph.json"):
        """Export the knowledge graph to a file."""
        self.db.export_knowledge_graph(output_file)
        
    def query_facts(self, category=None, keywords=None, limit=100):
        """Query facts from the knowledge graph."""
        return self.db.query_facts(category, keywords, limit)
```

## Implementation Notes

1. **Required Libraries**:
   - requests
   - beautifulsoup4
   - spacy (with en_core_web_lg model)
   - sqlite3
   - urllib.parse
   - hashlib
   - time
   - collections (deque, defaultdict)

2. **Installation**:
```python
# Install required packages
!pip install requests beautifulsoup4 spacy networkx
# Download spaCy model
!python -m spacy download en_core_web_lg
```

3. **Usage Example**:
```python
# Initialize the enhanced KnowledgeReduce system
kr = KnowledgeReduceEnhanced()

# Add starting URLs
kr.add_start_url("https://en.wikipedia.org/wiki/Artificial_intelligence")
kr.add_start_url("https://en.wikipedia.org/wiki/Machine_learning")

# Add site-specific rules for Wikipedia
kr.add_site_specific_rules("en.wikipedia.org", {
    'content': ['p', '.mw-parser-output > p', '.mw-parser-output > h2', '.mw-parser-output > h3', '.mw-parser-output > ul > li'],
    'title': ['h1#firstHeading'],
    'date': ['.lastmod'],
    'author': []  # Wikipedia doesn't have clear author information
})

# Run the crawler (limit to 20 pages for testing)
kr.run(max_pages=20)

# Export the knowledge graph
kr.export_knowledge_graph("wikipedia_ai_knowledge.json")

# Query facts about neural networks
neural_network_facts = kr.query_facts(keywords=["neural network"])
for fact in neural_network_facts:
    print(fact)
```

This enhanced crawling strategy addresses all the limitations identified in the original KnowledgeReduce technique, providing a more robust, scalable, and feature-rich solution for web crawling and knowledge graph construction.
