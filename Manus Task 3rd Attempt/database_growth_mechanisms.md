# Database Growth Mechanisms for KnowledgeReduce

This document outlines the implementation of database growth mechanisms that build upon the enhanced crawling strategy to create a robust, scalable knowledge graph system.

## 1. Seed Management System

```python
class SeedManager:
    def __init__(self, db_connection):
        self.db = db_connection
        self.setup_tables()
        
    def setup_tables(self):
        """Create necessary tables for seed management."""
        cursor = self.db.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS seed_urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            domain TEXT,
            category TEXT,
            priority INTEGER DEFAULT 5,
            status TEXT DEFAULT 'pending',
            added_date TIMESTAMP,
            last_crawled TIMESTAMP NULL,
            crawl_frequency INTEGER DEFAULT 604800, -- Default: 7 days in seconds
            max_depth INTEGER DEFAULT 2
        )
        ''')
        self.db.commit()
        
    def add_seed(self, url, category="General", priority=5, max_depth=2, crawl_frequency=604800):
        """Add a new seed URL to the database."""
        domain = urlparse(url).netloc
        cursor = self.db.cursor()
        
        try:
            cursor.execute('''
            INSERT INTO seed_urls 
            (url, domain, category, priority, status, added_date, crawl_frequency, max_depth)
            VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)
            ''', (url, domain, category, priority, time.time(), crawl_frequency, max_depth))
            self.db.commit()
            return True
        except sqlite3.IntegrityError:
            # URL already exists
            return False
            
    def get_seeds_for_crawling(self, limit=10):
        """Get seed URLs that are due for crawling, ordered by priority."""
        current_time = time.time()
        cursor = self.db.cursor()
        
        cursor.execute('''
        SELECT id, url, domain, category, priority, max_depth
        FROM seed_urls
        WHERE status = 'pending' OR 
              (status = 'completed' AND last_crawled + crawl_frequency < ?)
        ORDER BY priority DESC, last_crawled ASC
        LIMIT ?
        ''', (current_time, limit))
        
        return cursor.fetchall()
        
    def update_seed_status(self, seed_id, status, crawl_time=None):
        """Update the status of a seed URL after crawling."""
        if crawl_time is None:
            crawl_time = time.time()
            
        cursor = self.db.cursor()
        cursor.execute('''
        UPDATE seed_urls
        SET status = ?, last_crawled = ?
        WHERE id = ?
        ''', (status, crawl_time, seed_id))
        self.db.commit()
        
    def discover_new_seeds(self, domain_limit=100):
        """Discover new seed URLs from the database of crawled pages."""
        cursor = self.db.cursor()
        
        # Get domains we already have as seeds
        cursor.execute('SELECT DISTINCT domain FROM seed_urls')
        existing_domains = set(row[0] for row in cursor.fetchall())
        
        # Find potential new seed domains from our crawled URLs
        cursor.execute('''
        SELECT domain, COUNT(*) as page_count
        FROM crawled_urls
        WHERE domain NOT IN ({})
        GROUP BY domain
        HAVING page_count >= 3
        ORDER BY page_count DESC
        LIMIT ?
        '''.format(','.join('?' * len(existing_domains))), 
        (*existing_domains, domain_limit))
        
        new_domains = cursor.fetchall()
        
        # For each new domain, find the most linked-to URL
        for domain, _ in new_domains:
            cursor.execute('''
            SELECT url, COUNT(*) as inlink_count
            FROM (
                SELECT DISTINCT source_url, target_url
                FROM page_links
                WHERE target_domain = ?
            ) AS distinct_links
            JOIN crawled_urls ON distinct_links.target_url = crawled_urls.url
            GROUP BY url
            ORDER BY inlink_count DESC
            LIMIT 1
            ''', (domain,))
            
            result = cursor.fetchone()
            if result:
                url, _ = result
                # Add this URL as a new seed
                self.add_seed(url, category="Auto-Discovered", priority=3)
                
        return len(new_domains)
```

## 2. Link Analysis and Prioritization

```python
class LinkAnalyzer:
    def __init__(self, db_connection):
        self.db = db_connection
        self.setup_tables()
        
    def setup_tables(self):
        """Create necessary tables for link analysis."""
        cursor = self.db.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS page_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT,
            source_domain TEXT,
            target_url TEXT,
            target_domain TEXT,
            anchor_text TEXT,
            discovered_date TIMESTAMP,
            UNIQUE(source_url, target_url)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS url_metrics (
            url TEXT PRIMARY KEY,
            domain TEXT,
            inlink_count INTEGER DEFAULT 0,
            outlink_count INTEGER DEFAULT 0,
            pagerank REAL DEFAULT 0.0,
            last_updated TIMESTAMP
        )
        ''')
        
        self.db.commit()
        
    def store_links(self, source_url, links):
        """Store links discovered during crawling."""
        source_domain = urlparse(source_url).netloc
        cursor = self.db.cursor()
        current_time = time.time()
        
        for link_data in links:
            target_url = link_data['url']
            target_domain = urlparse(target_url).netloc
            anchor_text = link_data.get('anchor_text', '')
            
            try:
                cursor.execute('''
                INSERT INTO page_links
                (source_url, source_domain, target_url, target_domain, anchor_text, discovered_date)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (source_url, source_domain, target_url, target_domain, anchor_text, current_time))
            except sqlite3.IntegrityError:
                # Link already exists
                pass
                
        # Update outlink count for source URL
        cursor.execute('''
        INSERT OR REPLACE INTO url_metrics
        (url, domain, outlink_count, last_updated)
        VALUES (
            ?,
            ?,
            (SELECT COUNT(DISTINCT target_url) FROM page_links WHERE source_url = ?),
            ?
        )
        ''', (source_url, source_domain, source_url, current_time))
        
        # Update inlink counts for target URLs
        for link_data in links:
            target_url = link_data['url']
            target_domain = urlparse(target_url).netloc
            
            cursor.execute('''
            INSERT OR REPLACE INTO url_metrics
            (url, domain, inlink_count, last_updated)
            VALUES (
                ?,
                ?,
                (SELECT COUNT(DISTINCT source_url) FROM page_links WHERE target_url = ?),
                ?
            )
            ''', (target_url, target_domain, target_url, current_time))
            
        self.db.commit()
        
    def calculate_pagerank(self, damping=0.85, iterations=10):
        """Calculate PageRank for all URLs in the database."""
        cursor = self.db.cursor()
        
        # Get all URLs
        cursor.execute('SELECT url FROM url_metrics')
        urls = [row[0] for row in cursor.fetchall()]
        
        if not urls:
            return
            
        # Initialize PageRank
        pagerank = {url: 1.0 / len(urls) for url in urls}
        
        # Build the link graph
        outlinks = {}
        for url in urls:
            cursor.execute('SELECT target_url FROM page_links WHERE source_url = ?', (url,))
            outlinks[url] = [row[0] for row in cursor.fetchall()]
            
        # Iterative PageRank calculation
        for _ in range(iterations):
            new_pagerank = {url: (1 - damping) / len(urls) for url in urls}
            
            for url in urls:
                for target in outlinks.get(url, []):
                    if target in new_pagerank and len(outlinks[url]) > 0:
                        new_pagerank[target] += damping * pagerank[url] / len(outlinks[url])
                        
            # Normalize
            total = sum(new_pagerank.values())
            if total > 0:
                pagerank = {url: value / total for url, value in new_pagerank.items()}
            else:
                pagerank = new_pagerank
                
        # Update database
        current_time = time.time()
        for url, rank in pagerank.items():
            cursor.execute('''
            UPDATE url_metrics
            SET pagerank = ?, last_updated = ?
            WHERE url = ?
            ''', (rank, current_time, url))
            
        self.db.commit()
        
    def get_high_value_urls(self, limit=100, min_inlinks=3):
        """Get high-value URLs for crawling based on metrics."""
        cursor = self.db.cursor()
        
        cursor.execute('''
        SELECT url, domain, inlink_count, pagerank
        FROM url_metrics
        WHERE inlink_count >= ?
        ORDER BY pagerank DESC
        LIMIT ?
        ''', (min_inlinks, limit))
        
        return cursor.fetchall()
```

## 3. Content Categorization and Tagging

```python
class ContentCategorizer:
    def __init__(self, nlp_model=None):
        # Load spaCy model if not provided
        self.nlp = nlp_model or spacy.load("en_core_web_lg")
        
        # Define category keywords
        self.categories = {
            "Technology": ["computer", "software", "hardware", "programming", "code", "algorithm", "data", "internet", "web", "digital", "tech", "AI", "artificial intelligence", "machine learning"],
            "Science": ["research", "experiment", "laboratory", "scientific", "physics", "chemistry", "biology", "astronomy", "mathematics", "science", "discovery", "hypothesis", "theory"],
            "Business": ["company", "corporation", "startup", "entrepreneur", "market", "finance", "investment", "stock", "economy", "business", "profit", "revenue", "CEO", "executive"],
            "Health": ["medical", "medicine", "doctor", "patient", "hospital", "health", "disease", "treatment", "therapy", "wellness", "healthcare", "diagnosis", "symptom"],
            "Politics": ["government", "policy", "election", "political", "politician", "democracy", "vote", "law", "legislation", "congress", "parliament", "president", "senator"],
            "Education": ["school", "university", "college", "student", "teacher", "professor", "education", "learning", "academic", "study", "course", "degree", "curriculum"],
            "Entertainment": ["movie", "film", "music", "artist", "actor", "actress", "celebrity", "entertainment", "game", "gaming", "television", "TV", "show", "series"],
            "Sports": ["athlete", "team", "game", "match", "tournament", "championship", "sports", "player", "coach", "competition", "league", "score", "win", "lose"]
        }
        
        # Create category vectors
        self.category_vectors = {}
        for category, keywords in self.categories.items():
            category_text = " ".join(keywords)
            self.category_vectors[category] = self.nlp(category_text)
            
    def categorize_text(self, text, threshold=0.3):
        """Categorize text into predefined categories."""
        doc = self.nlp(text)
        
        # Calculate similarity with each category
        similarities = {}
        for category, category_vector in self.category_vectors.items():
            similarity = doc.similarity(category_vector)
            similarities[category] = similarity
            
        # Get categories above threshold
        categories = [category for category, similarity in similarities.items() if similarity > threshold]
        
        # If no category is above threshold, use "General"
        if not categories:
            return ["General"]
            
        return categories
        
    def extract_tags(self, text, max_tags=5):
        """Extract relevant tags from text."""
        doc = self.nlp(text)
        
        # Extract named entities as potential tags
        entity_tags = [ent.text for ent in doc.ents]
        
        # Extract noun chunks as potential tags
        noun_chunk_tags = [chunk.text for chunk in doc.noun_chunks if len(chunk.text.split()) <= 3]
        
        # Combine and deduplicate
        all_tags = entity_tags + noun_chunk_tags
        unique_tags = list(set(all_tags))
        
        # Sort by frequency in the text
        tag_counts = {}
        for tag in unique_tags:
            tag_counts[tag] = text.lower().count(tag.lower())
            
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Return top tags
        return [tag for tag, _ in sorted_tags[:max_tags]]
        
    def process_content(self, content):
        """Process content to add categories and tags."""
        # Combine all text from content elements
        full_text = " ".join([element['text'] for element in content['content_elements']])
        
        # Categorize the content
        categories = self.categorize_text(full_text)
        
        # Extract tags
        tags = self.extract_tags(full_text)
        
        # Add to content
        content['categories'] = categories
        content['tags'] = tags
        
        return content
```

## 4. Knowledge Graph Expansion

```python
class KnowledgeGraphExpander:
    def __init__(self, db_connection):
        self.db = db_connection
        self.setup_tables()
        
    def setup_tables(self):
        """Create necessary tables for knowledge graph expansion."""
        cursor = self.db.cursor()
        
        # Table for entity relationships
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS entity_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity1_id INTEGER,
            entity2_id INTEGER,
            relationship_type TEXT,
            confidence REAL,
            source_fact_id INTEGER,
            FOREIGN KEY (entity1_id) REFERENCES entities (id),
            FOREIGN KEY (entity2_id) REFERENCES entities (id),
            FOREIGN KEY (source_fact_id) REFERENCES knowledge_facts (id),
            UNIQUE(entity1_id, entity2_id, relationship_type)
        )
        ''')
        
        # Table for entity clusters
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS entity_clusters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cluster_name TEXT,
            created_date TIMESTAMP
        )
        ''')
        
        # Table for entity-cluster membership
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS entity_cluster_members (
            cluster_id INTEGER,
            entity_id INTEGER,
            confidence REAL,
            FOREIGN KEY (cluster_id) REFERENCES entity_clusters (id),
            FOREIGN KEY (entity_id) REFERENCES entities (id),
            PRIMARY KEY (cluster_id, entity_id)
        )
        ''')
        
        self.db.commit()
        
    def find_entity_relationships(self):
        """Find relationships between entities based on co-occurrence."""
        cursor = self.db.cursor()
        
        # Find entities that co-occur in the same fact
        cursor.execute('''
        SELECT f.id, e1.id, e2.id, e1.text, e2.text
        FROM knowledge_facts f
        JOIN entities e1 ON f.fact_statement LIKE '%' || e1.text || '%'
        JOIN entities e2 ON f.fact_statement LIKE '%' || e2.text || '%'
        WHERE e1.id < e2.id  -- Avoid duplicates
        AND e1.text != e2.text  -- Avoid self-relationships
        ''')
        
        co_occurrences = cursor.fetchall()
        
        # Process co-occurrences to create relationships
        for fact_id, entity1_id, entity2_id, entity1_text, entity2_text in co_occurrences:
            # Get the fact statement
            cursor.execute('SELECT fact_statement FROM knowledge_facts WHERE id = ?', (fact_id,))
            fact_statement = cursor.fetchone()[0]
            
            # Simple relationship extraction based on position
            if entity1_text in fact_statement and entity2_text in fact_statement:
                pos1 = fact_statement.find(entity1_text)
                pos2 = fact_statement.find(entity2_text)
                
                # Determine relationship type based on order
                if pos1 < pos2:
                    relationship_type = "RELATED_TO"
                    confidence = 0.7
                else:
                    relationship_type = "RELATED_TO"
                    confidence = 0.7
                    
                # Store the relationship
                try:
                    cursor.execute('''
                    INSERT INTO entity_relationships
                    (entity1_id, entity2_id, relationship_type, confidence, source_fact_id)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (entity1_id, entity2_id, relationship_type, confidence, fact_id))
                except sqlite3.IntegrityError:
                    # Relationship already exists
                    pass
                    
        self.db.commit()
        
    def cluster_entities(self, similarity_threshold=0.7):
        """Cluster similar entities together."""
        cursor = self.db.cursor()
        
        # Get all entities
        cursor.execute('SELECT id, text, entity_type FROM entities')
        entities = cursor.fetchall()
        
        # Load spaCy model for similarity comparison
        nlp = spacy.load("en_core_web_md")
        
        # Process entities with spaCy
        entity_docs = {}
        for entity_id, text, _ in entities:
            entity_docs[entity_id] = nlp(text)
            
        # Cluster entities
        clusters = []
        assigned_entities = set()
        
        for entity_id, text, entity_type in entities:
            if entity_id in assigned_entities:
                continue
                
            # Start a new cluster
            cluster = {
                'name': text,
                'type': entity_type,
                'members': [(entity_id, 1.0)]  # The seed entity has confidence 1.0
            }
            assigned_entities.add(entity_id)
            
            # Find similar entities
            for other_id, other_text, other_type in entities:
                if other_id in assigned_entities or other_id == entity_id:
                    continue
                    
                # Check if entity types match
                if entity_type != other_type:
                    continue
                    
                # Calculate similarity
                similarity = entity_docs[entity_id].similarity(entity_docs[other_id])
                
                if similarity >= similarity_threshold:
                    cluster['members'].append((other_id, similarity))
                    assigned_entities.add(other_id)
                    
            clusters.append(cluster)
            
        # Store clusters in database
        current_time = time.time()
        for cluster in clusters:
            cursor.execute('''
            INSERT INTO entity_clusters (cluster_name, created_date)
            VALUES (?, ?)
            ''', (cluster['name'], current_time))
            
            cluster_id = cursor.lastrowid
            
            for entity_id, confidence in cluster['members']:
                cursor.execute('''
                INSERT INTO entity_cluster_members (cluster_id, entity_id, confidence)
                VALUES (?, ?, ?)
                ''', (cluster_id, entity_id, confidence))
                
        self.db.commit()
        
        return len(clusters)
        
    def infer_new_relationships(self):
        """Infer new relationships based on existing ones."""
        cursor = self.db.cursor()
        
        # Find transitive relationships (A->B, B->C => A->C)
        cursor.execute('''
        SELECT r1.entity1_id, r2.entity2_id, r1.relationship_type
        FROM entity_relationships r1
        JOIN entity_relationships r2 ON r1.entity2_id = r2.entity1_id
        WHERE r1.relationship_type = r2.relationship_type
        AND r1.entity1_id != r2.entity2_id
        AND NOT EXISTS (
            SELECT 1 FROM entity_relationships r3
            WHERE r3.entity1_id = r1.entity1_id
            AND r3.entity2_id = r2.entity2_id
            AND r3.relationship_type = r1.relationship_type
        )
        ''')
        
        inferred_relationships = cursor.fetchall()
        
        # Store inferred relationships
        for entity1_id, entity2_id, relationship_type in inferred_relationships:
            try:
                cursor.execute('''
                INSERT INTO entity_relationships
                (entity1_id, entity2_id, relationship_type, confidence, source_fact_id)
                VALUES (?, ?, ?, ?, NULL)
                ''', (entity1_id, entity2_id, relationship_type, 0.5))  # Lower confidence for inferred relationships
            except sqlite3.IntegrityError:
                # Relationship already exists
                pass
                
        self.db.commit()
        
        return len(inferred_relationships)
```

## 5. Fact Verification and Quality Scoring

```python
class FactVerifier:
    def __init__(self, db_connection):
        self.db = db_connection
        self.setup_tables()
        
    def setup_tables(self):
        """Create necessary tables for fact verification."""
        cursor = self.db.cursor()
        
        # Table for fact verification
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS fact_verification (
            fact_id INTEGER PRIMARY KEY,
            verification_score REAL DEFAULT 0.0,
            verification_method TEXT,
            verification_date TIMESTAMP,
            verification_sources TEXT,
            FOREIGN KEY (fact_id) REFERENCES knowledge_facts (id)
        )
        ''')
        
        self.db.commit()
        
    def verify_fact_by_frequency(self, fact_id):
        """Verify a fact based on its frequency across sources."""
        cursor = self.db.cursor()
        
        # Get the fact statement
        cursor.execute('SELECT fact_statement FROM knowledge_facts WHERE id = ?', (fact_id,))
        fact_statement = cursor.fetchone()[0]
        
        # Find similar facts
        cursor.execute('''
        SELECT id, fact_statement, source_url
        FROM knowledge_facts
        WHERE fact_statement LIKE ?
        ''', (f'%{fact_statement}%',))
        
        similar_facts = cursor.fetchall()
        
        # Count unique sources
        unique_sources = set()
        for _, _, source_url in similar_facts:
            unique_sources.add(source_url)
            
        # Calculate verification score based on number of sources
        source_count = len(unique_sources)
        verification_score = min(1.0, source_count / 5.0)  # Max score at 5+ sources
        
        # Store verification result
        cursor.execute('''
        INSERT OR REPLACE INTO fact_verification
        (fact_id, verification_score, verification_method, verification_date, verification_sources)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            fact_id,
            verification_score,
            "frequency_analysis",
            time.time(),
            ",".join(unique_sources)
        ))
        
        self.db.commit()
        
        return verification_score
        
    def verify_all_facts(self):
        """Verify all facts in the database."""
        cursor = self.db.cursor()
        
        # Get all facts
        cursor.execute('SELECT id FROM knowledge_facts')
        fact_ids = [row[0] for row in cursor.fetchall()]
        
        # Verify each fact
        for fact_id in fact_ids:
            self.verify_fact_by_frequency(fact_id)
            
        return len(fact_ids)
        
    def get_high_quality_facts(self, min_score=0.6, limit=100):
        """Get high-quality facts based on verification score."""
        cursor = self.db.cursor()
        
        cursor.execute('''
        SELECT f.id, f.fact_statement, f.category, v.verification_score
        FROM knowledge_facts f
        JOIN fact_verification v ON f.id = v.fact_id
        WHERE v.verification_score >= ?
        ORDER BY v.verification_score DESC
        LIMIT ?
        ''', (min_score, limit))
        
        return cursor.fetchall()
```

## 6. Database Sharding and Scaling

```python
class DatabaseSharding:
    def __init__(self, base_path, shard_size=10000):
        self.base_path = base_path
        self.shard_size = shard_size
        self.main_db = sqlite3.connect(os.path.join(base_path, "main.db"))
        self.setup_main_db()
        
    def setup_main_db(self):
        """Set up the main database with shard tracking."""
        cursor = self.main_db.cursor()
        
        # Table for tracking shards
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS shards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shard_name TEXT,
            start_date TIMESTAMP,
            end_date TIMESTAMP,
            fact_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active'
        )
        ''')
        
        # Table for mapping facts to shards
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS fact_shard_mapping (
            fact_id INTEGER PRIMARY KEY,
            shard_id INTEGER,
            FOREIGN KEY (shard_id) REFERENCES shards (id)
        )
        ''')
        
        self.main_db.commit()
        
    def create_new_shard(self):
        """Create a new shard database."""
        cursor = self.main_db.cursor()
        
        # Generate shard name
        current_time = time.time()
        shard_name = f"shard_{int(current_time)}.db"
        
        # Register shard in main database
        cursor.execute('''
        INSERT INTO shards (shard_name, start_date, status)
        VALUES (?, ?, 'active')
        ''', (shard_name, current_time))
        
        shard_id = cursor.lastrowid
        self.main_db.commit()
        
        # Create shard database
        shard_path = os.path.join(self.base_path, shard_name)
        shard_db = sqlite3.connect(shard_path)
        shard_cursor = shard_db.cursor()
        
        # Create tables in shard
        shard_cursor.execute('''
        CREATE TABLE knowledge_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            global_id INTEGER UNIQUE,
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
        
        shard_db.commit()
        shard_db.close()
        
        return shard_id
        
    def get_active_shard(self):
        """Get the currently active shard."""
        cursor = self.main_db.cursor()
        
        cursor.execute('''
        SELECT id, shard_name, fact_count
        FROM shards
        WHERE status = 'active'
        ORDER BY id DESC
        LIMIT 1
        ''')
        
        result = cursor.fetchone()
        
        if result:
            shard_id, shard_name, fact_count = result
            
            # Check if shard is full
            if fact_count >= self.shard_size:
                # Mark shard as full
                cursor.execute('''
                UPDATE shards
                SET status = 'full', end_date = ?
                WHERE id = ?
                ''', (time.time(), shard_id))
                self.main_db.commit()
                
                # Create new shard
                return self.create_new_shard()
            else:
                return shard_id
        else:
            # No active shard, create one
            return self.create_new_shard()
            
    def get_shard_path(self, shard_id):
        """Get the file path for a shard."""
        cursor = self.main_db.cursor()
        
        cursor.execute('SELECT shard_name FROM shards WHERE id = ?', (shard_id,))
        result = cursor.fetchone()
        
        if result:
            return os.path.join(self.base_path, result[0])
        else:
            return None
            
    def add_fact_to_shard(self, fact_data):
        """Add a fact to the active shard."""
        # Get active shard
        shard_id = self.get_active_shard()
        shard_path = self.get_shard_path(shard_id)
        
        if not shard_path:
            return None
            
        # Connect to shard database
        shard_db = sqlite3.connect(shard_path)
        shard_cursor = shard_db.cursor()
        
        # Insert fact into shard
        shard_cursor.execute('''
        INSERT INTO knowledge_facts
        (fact_statement, category, tags, date_recorded, last_updated, 
         reliability_rating, source_url, source_title)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            fact_data['fact_statement'],
            fact_data['category'],
            ','.join(fact_data['tags']),
            fact_data['date_recorded'],
            fact_data['last_updated'],
            fact_data['reliability_rating'],
            fact_data['source_url'],
            fact_data['source_title']
        ))
        
        fact_id = shard_cursor.lastrowid
        shard_db.commit()
        
        # Update fact count in main database
        cursor = self.main_db.cursor()
        cursor.execute('''
        UPDATE shards
        SET fact_count = fact_count + 1
        WHERE id = ?
        ''', (shard_id,))
        
        # Map fact to shard
        cursor.execute('''
        INSERT INTO fact_shard_mapping (fact_id, shard_id)
        VALUES (?, ?)
        ''', (fact_id, shard_id))
        
        self.main_db.commit()
        shard_db.close()
        
        return fact_id
        
    def search_facts(self, query, categories=None, limit=100):
        """Search for facts across all shards."""
        cursor = self.main_db.cursor()
        
        # Get all shards
        cursor.execute('SELECT id, shard_name FROM shards')
        shards = cursor.fetchall()
        
        results = []
        
        for shard_id, shard_name in shards:
            shard_path = os.path.join(self.base_path, shard_name)
            
            if not os.path.exists(shard_path):
                continue
                
            shard_db = sqlite3.connect(shard_path)
            shard_cursor = shard_db.cursor()
            
            # Build query
            sql = '''
            SELECT id, fact_statement, category, tags, source_url
            FROM knowledge_facts
            WHERE fact_statement LIKE ?
            '''
            
            params = [f'%{query}%']
            
            if categories:
                placeholders = ','.join(['?'] * len(categories))
                sql += f' AND category IN ({placeholders})'
                params.extend(categories)
                
            sql += f' LIMIT {limit}'
            
            shard_cursor.execute(sql, params)
            shard_results = shard_cursor.fetchall()
            
            for row in shard_results:
                fact_id, statement, category, tags, source_url = row
                results.append({
                    'shard_id': shard_id,
                    'fact_id': fact_id,
                    'statement': statement,
                    'category': category,
                    'tags': tags.split(','),
                    'source_url': source_url
                })
                
            shard_db.close()
            
            if len(results) >= limit:
                break
                
        return results[:limit]
```

## 7. Main Integration Class

```python
class EnhancedKnowledgeReduce:
    def __init__(self, db_path="knowledge_reduce_db"):
        """Initialize the enhanced KnowledgeReduce system with database growth mechanisms."""
        # Create database directory if it doesn't exist
        os.makedirs(db_path, exist_ok=True)
        
        # Initialize main database connection
        self.main_db_path = os.path.join(db_path, "main.db")
        self.db = sqlite3.connect(self.main_db_path)
        
        # Initialize components
        self.crawler = EnhancedCrawler()
        self.content_extractor = ContentExtractor()
        self.entity_extractor = EntityRelationshipExtractor()
        self.seed_manager = SeedManager(self.db)
        self.link_analyzer = LinkAnalyzer(self.db)
        self.content_categorizer = ContentCategorizer()
        self.graph_expander = KnowledgeGraphExpander(self.db)
        self.fact_verifier = FactVerifier(self.db)
        self.db_sharding = DatabaseSharding(db_path)
        
    def add_seed_url(self, url, category="General", priority=5, max_depth=2):
        """Add a seed URL to the system."""
        return self.seed_manager.add_seed(url, category, priority, max_depth)
        
    def add_site_specific_rules(self, domain, rules):
        """Add site-specific extraction rules."""
        self.content_extractor.add_site_rule(domain, rules)
        
    def run_crawl_cycle(self, max_seeds=5):
        """Run a crawl cycle with the specified number of seeds."""
        # Get seeds for crawling
        seeds = self.seed_manager.get_seeds_for_crawling(limit=max_seeds)
        
        if not seeds:
            print("No seeds available for crawling.")
            return 0
            
        pages_processed = 0
        
        for seed_id, url, domain, category, priority, max_depth in seeds:
            # Configure crawler for this seed
            self.crawler = EnhancedCrawler(start_urls=[url], max_depth=max_depth)
            
            try:
                # Mark seed as in progress
                self.seed_manager.update_seed_status(seed_id, "in_progress")
                
                # Crawl pages from this seed
                for page_url, soup in self.crawler.crawl():
                    try:
                        # Extract structured content
                        content = self.content_extractor.extract_structured_content(soup, page_url)
                        
                        # Categorize and tag content
                        content = self.content_categorizer.process_content(content)
                        
                        # Extract entities and relationships
                        extraction_results = self.entity_extractor.process_content(content)
                        
                        # Extract links for link analysis
                        links = self.crawler.extract_links(soup, page_url)
                        self.link_analyzer.store_links(page_url, [{'url': link, 'anchor_text': ''} for link in links])
                        
                        # Generate facts and store in sharded database
                        for relationship in extraction_results['relationships']:
                            fact_data = {
                                'fact_statement': f"{relationship['subject']} {relationship['predicate']} {relationship['object']}",
                                'category': content['categories'][0] if content['categories'] else "General",
                                'tags': content['tags'],
                                'date_recorded': time.time(),
                                'last_updated': time.time(),
                                'reliability_rating': "LIKELY_TRUE",
                                'source_url': page_url,
                                'source_title': content['title'] or page_url
                            }
                            
                            self.db_sharding.add_fact_to_shard(fact_data)
                            
                        pages_processed += 1
                        print(f"Processed {page_url}")
                        
                    except Exception as e:
                        print(f"Error processing {page_url}: {e}")
                        
                # Mark seed as completed
                self.seed_manager.update_seed_status(seed_id, "completed")
                
            except Exception as e:
                print(f"Error crawling seed {url}: {e}")
                # Mark seed as failed
                self.seed_manager.update_seed_status(seed_id, "failed")
                
        return pages_processed
        
    def run_maintenance_tasks(self):
        """Run maintenance tasks to improve the knowledge graph."""
        print("Running maintenance tasks...")
        
        # Calculate PageRank
        print("Calculating PageRank...")
        self.link_analyzer.calculate_pagerank()
        
        # Find entity relationships
        print("Finding entity relationships...")
        self.graph_expander.find_entity_relationships()
        
        # Cluster entities
        print("Clustering entities...")
        cluster_count = self.graph_expander.cluster_entities()
        print(f"Created {cluster_count} entity clusters")
        
        # Infer new relationships
        print("Inferring new relationships...")
        inferred_count = self.graph_expander.infer_new_relationships()
        print(f"Inferred {inferred_count} new relationships")
        
        # Verify facts
        print("Verifying facts...")
        verified_count = self.fact_verifier.verify_all_facts()
        print(f"Verified {verified_count} facts")
        
        # Discover new seeds
        print("Discovering new seeds...")
        new_seed_count = self.seed_manager.discover_new_seeds()
        print(f"Discovered {new_seed_count} new seed domains")
        
        print("Maintenance tasks completed.")
        
    def search_knowledge_graph(self, query, categories=None, limit=100):
        """Search the knowledge graph for facts matching the query."""
        return self.db_sharding.search_facts(query, categories, limit)
        
    def get_high_quality_facts(self, min_score=0.6, limit=100):
        """Get high-quality facts from the knowledge graph."""
        return self.fact_verifier.get_high_quality_facts(min_score, limit)
        
    def get_high_value_urls(self, limit=100):
        """Get high-value URLs for future crawling."""
        return self.link_analyzer.get_high_value_urls(limit)
        
    def export_knowledge_graph(self, output_file="knowledge_graph_export.json"):
        """Export the knowledge graph to a JSON file."""
        # This is a simplified export that only includes high-quality facts
        facts = self.get_high_quality_facts(min_score=0.5, limit=10000)
        
        graph = {
            "nodes": [],
            "edges": []
        }
        
        # Create nodes for facts
        for fact_id, statement, category, score in facts:
            graph["nodes"].append({
                "id": f"fact_{fact_id}",
                "label": statement,
                "type": "fact",
                "category": category,
                "quality": score
            })
            
        # Get relationships between facts
        cursor = self.db.cursor()
        cursor.execute('''
        SELECT e1.text, e2.text, r.relationship_type
        FROM entity_relationships r
        JOIN entities e1 ON r.entity1_id = e1.id
        JOIN entities e2 ON r.entity2_id = e2.id
        LIMIT 10000
        ''')
        
        relationships = cursor.fetchall()
        
        # Add edges for relationships
        for entity1, entity2, rel_type in relationships:
            # Find nodes containing these entities
            source_nodes = []
            target_nodes = []
            
            for node in graph["nodes"]:
                if entity1 in node["label"]:
                    source_nodes.append(node["id"])
                if entity2 in node["label"]:
                    target_nodes.append(node["id"])
                    
            # Create edges between matching nodes
            for source in source_nodes:
                for target in target_nodes:
                    if source != target:
                        graph["edges"].append({
                            "source": source,
                            "target": target,
                            "label": rel_type
                        })
                        
        # Write to file
        with open(output_file, 'w') as f:
            json.dump(graph, f, indent=2)
            
        return len(graph["nodes"]), len(graph["edges"])
```

## Implementation Notes

1. **Required Libraries**:
   - All libraries from the enhanced crawling strategy
   - os (for file path operations)
   - time (for timestamps)
   - hashlib (for content hashing)
   - sqlite3 (for database operations)

2. **Database Structure**:
   - Main database for metadata, URL tracking, and entity relationships
   - Sharded databases for storing facts, allowing horizontal scaling
   - Separate tables for different aspects of the knowledge graph

3. **Growth Mechanisms**:
   - Seed management for controlled crawling expansion
   - Link analysis to identify high-value URLs
   - Content categorization for better organization
   - Entity clustering to consolidate similar information
   - Relationship inference to expand the knowledge graph
   - Fact verification to ensure quality
   - Database sharding for scalability

4. **Usage Example**:
```python
# Initialize the enhanced KnowledgeReduce system
kr = EnhancedKnowledgeReduce("knowledge_db")

# Add seed URLs
kr.add_seed_url("https://en.wikipedia.org/wiki/Artificial_intelligence", category="Technology", priority=10)
kr.add_seed_url("https://en.wikipedia.org/wiki/Machine_learning", category="Technology", priority=9)
kr.add_seed_url("https://www.sciencedaily.com/news/computers_math/artificial_intelligence/", category="Science", priority=8)

# Add site-specific rules
kr.add_site_specific_rules("en.wikipedia.org", {
    'content': ['p', '.mw-parser-output > p', '.mw-parser-output > h2', '.mw-parser-output > h3', '.mw-parser-output > ul > li'],
    'title': ['h1#firstHeading'],
    'date': ['.lastmod'],
    'author': []
})

kr.add_site_specific_rules("www.sciencedaily.com", {
    'content': ['#story_text p', 'h1', 'h2', 'h3'],
    'title': ['h1'],
    'date': ['.date'],
    'author': ['.author']
})

# Run initial crawl cycle
print("Running initial crawl cycle...")
pages = kr.run_crawl_cycle(max_seeds=3)
print(f"Processed {pages} pages")

# Run maintenance tasks
print("Running maintenance tasks...")
kr.run_maintenance_tasks()

# Run additional crawl cycles
for i in range(3):
    print(f"Running crawl cycle {i+2}...")
    pages = kr.run_crawl_cycle(max_seeds=5)
    print(f"Processed {pages} pages")
    kr.run_maintenance_tasks()

# Export the knowledge graph
print("Exporting knowledge graph...")
nodes, edges = kr.export_knowledge_graph("ai_knowledge_graph.json")
print(f"Exported knowledge graph with {nodes} nodes and {edges} edges")

# Search the knowledge graph
print("Searching for 'neural networks'...")
results = kr.search_knowledge_graph("neural network", categories=["Technology"])
for result in results[:10]:
    print(f"- {result['statement']}")
```

This implementation provides a comprehensive solution for database growth mechanisms that build upon the enhanced crawling strategy, addressing all the limitations identified in the original KnowledgeReduce technique.
