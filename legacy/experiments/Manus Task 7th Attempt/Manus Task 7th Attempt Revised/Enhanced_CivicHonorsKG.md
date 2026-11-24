---
jupyter:
  jupytext:
    text_representation:
      extension: .md
      format_name: markdown
      format_version: '1.3'
      jupytext_version: 1.16.7
  kernelspec:
    display_name: Python 3
    language: python
    name: python3
---

<a href="https://colab.research.google.com/github/nelslindahlx/KnowledgeReduce/blob/main/Enhanced_CivicHonorsKG.ipynb" target="_parent"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>

# Code Summary

This notebook encapsulates an end-to-end pipeline designed for the meticulous extraction, processing, and systematic organization of data from specified web sources into a well-structured knowledge graph, with significant enhancements to the web crawling and knowledge reduction capabilities. The workflow is outlined in detailed steps, each contributing to the creation of a refined and informative dataset:

### Step 1: Install Necessary Libraries
- Installation of pivotal Python libraries such as `requests` for web scraping, `beautifulsoup4` for HTML parsing, `networkx` for graph-based operations, `spacy` for advanced natural language processing tasks, `scikit-learn` for machine learning algorithms, and `sentence-transformers` for state-of-the-art text embeddings.
- Code to restart the runtime

### Step 2: Import Libraries and Define Classes
- Incorporation of essential Python modules and the establishment of foundational classes:
  - `ReliabilityRating`: An enumeration (Enum) for classifying the reliability of the extracted information.
  - `KnowledgeGraph`: A versatile class for constructing and managing a knowledge graph, encompassing functionalities for adding facts, computing and updating quality scores, and fact retrieval.

### Step 3: Define RecursiveCrawler Class
- Implementation of a sophisticated `RecursiveCrawler` class that can follow links across multiple pages.
- Respect for robots.txt rules and implementation of rate limiting to avoid overloading servers.
- URL frontier management for efficient crawling across multiple domains.
- Proper link extraction and text processing capabilities.

### Step 4: Define EnhancedKnowledgeReduction Class
- Implementation of multiple similarity calculation methods (spaCy, TF-IDF, transformers).
- Hierarchical clustering for better fact grouping.
- Entity-based knowledge reduction to eliminate redundant information.
- Multi-stage reduction pipeline for more effective deduplication.

### Step 5: Define Helper Functions
- Creation of utility functions for processing text into facts.
- Functions for populating the knowledge graph from crawler results.
- Implementation of knowledge reduction application to the knowledge graph.

### Step 6: Advanced Web Crawling
- Initialization of the crawler with multiple start URLs.
- Configuration of crawling parameters such as depth, page limits, and rate limiting.
- Execution of the crawling process with detailed statistics collection.

### Step 7: Populate the KnowledgeGraph
- Initialization and population of the `KnowledgeGraph` instance from crawled content.
- Systematic incorporation of each fact into the graph, complete with comprehensive attributes.
- Analysis of fact distribution across different crawl depths.

### Step 8: Apply Advanced Knowledge Reduction
- Application of the multi-stage knowledge reduction pipeline.
- Comparison of original and reduced knowledge graph sizes.
- Presentation of representative facts after reduction.

### Step 9: Serialize the KnowledgeGraph for Portability
- A crucial step focusing on rendering the Knowledge Graph portable via serialization into JSON format, facilitating easy storage, transfer, and reconstruction across different environments.
- Implementation of sharding for efficient handling of large datasets.

This enhanced pipeline significantly improves the ability to crawl and process multiple webpages while respecting web etiquette standards, and provides more sophisticated knowledge reduction capabilities for higher quality insights. It is particularly suited for scenarios demanding high data quality and structure, enriched with advanced NLP techniques to ensure a dataset devoid of redundancies and abundant in diverse, valuable insights.

# Step 1: Install Necessary Libraries & restart the runtime

```python
!pip install requests beautifulsoup4 networkx spacy scikit-learn sentence-transformers
!python -m spacy download en_core_web_md
```

# Step 2: Import Libraries and Define Classes

```python
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
import time
import enum
import json
import os
import numpy as np
from difflib import SequenceMatcher
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import AgglomerativeClustering
from sentence_transformers import SentenceTransformer
```

## Define ReliabilityRating Enum

```python
class ReliabilityRating(enum.Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
```

## Define KnowledgeGraph Class

```python
class KnowledgeGraph:
    def __init__(self):
        self.data = []
        self.fact_count = 0
    
    def add_fact(self, fact_statement, source_id, source_name, reliability=ReliabilityRating.MEDIUM, 
                 category="General", tags=None, quality_score=None):
        """Add a fact to the knowledge graph."""
        if tags is None:
            tags = []
        
        # Calculate quality score if not provided
        if quality_score is None:
            quality_score = self._compute_quality_score(fact_statement, reliability)
        
        fact = {
            'fact_id': self.fact_count,
            'fact_statement': fact_statement,
            'source_id': source_id,
            'source_name': source_name,
            'reliability': reliability,
            'category': category,
            'tags': tags,
            'quality_score': quality_score
        }
        
        self.data.append(fact)
        self.fact_count += 1
        return fact['fact_id']
    
    def _compute_quality_score(self, fact_statement, reliability):
        """Compute quality score based on fact length and reliability."""
        # Length component: longer facts (up to a point) are considered higher quality
        length = len(fact_statement)
        length_score = min(length / 200, 1.0)  # Cap at 1.0 for facts longer than 200 chars
        
        # Reliability component: convert enum to numerical value
        reliability_value = reliability.value / 3.0  # Normalize to [0.33, 1.0]
        
        # Combine scores (equal weight)
        return (length_score + reliability_value) / 2.0
    
    def update_quality_scores(self):
        """Update quality scores for all facts."""
        for fact in self.data:
            fact['quality_score'] = self._compute_quality_score(
                fact['fact_statement'], fact['reliability'])
    
    def get_facts_by_quality(self, min_score=0.0, max_facts=None):
        """Get facts filtered by minimum quality score, sorted by quality."""
        filtered_facts = [f for f in self.data if f['quality_score'] >= min_score]
        sorted_facts = sorted(filtered_facts, key=lambda x: x['quality_score'], reverse=True)
        
        if max_facts is not None:
            return sorted_facts[:max_facts]
        return sorted_facts
    
    def get_facts_by_source(self, source_id):
        """Get facts from a specific source."""
        return [f for f in self.data if f['source_id'] == source_id]
    
    def get_facts_by_category(self, category):
        """Get facts from a specific category."""
        return [f for f in self.data if f['category'] == category]
    
    def get_facts_by_tag(self, tag):
        """Get facts with a specific tag."""
        return [f for f in self.data if tag in f['tags']]
```

# Step 3: Define RecursiveCrawler Class

The `RecursiveCrawler` class is a significant enhancement over the original implementation, providing advanced web crawling capabilities:

1. **Recursive Link Following**: Ability to follow links across multiple pages up to a specified depth
2. **Robots.txt Compliance**: Respects website crawling policies defined in robots.txt
3. **Rate Limiting**: Implements delays between requests to avoid overloading servers
4. **URL Frontier Management**: Efficiently manages the list of URLs to visit
5. **Domain-specific Limits**: Controls the number of pages crawled per domain

This implementation follows web etiquette standards while providing comprehensive crawling capabilities.

```python
class RecursiveCrawler:
    def __init__(self, start_urls, max_depth=2, max_pages_per_domain=20, respect_robots=True, 
                 rate_limit=1.0, user_agent="KnowledgeReduceCrawler/1.0"):
        """
        Initialize the recursive crawler.
        
        Args:
            start_urls (list): List of URLs to start crawling from
            max_depth (int): Maximum depth to crawl
            max_pages_per_domain (int): Maximum pages to crawl per domain
            respect_robots (bool): Whether to respect robots.txt
            rate_limit (float): Minimum time between requests to the same domain in seconds
            user_agent (str): User agent string to use for requests
        """
        self.start_urls = start_urls
        self.max_depth = max_depth
        self.max_pages_per_domain = max_pages_per_domain
        self.respect_robots = respect_robots
        self.rate_limit = rate_limit
        self.user_agent = user_agent
        
        # Data structures for crawler management
        self.visited_urls = set()
        self.url_frontier = []  # URLs to visit
        self.domain_last_access = {}  # Domain -> timestamp of last access
        self.robots_parsers = {}  # Domain -> robots parser
        self.results = []  # Crawled pages content
```

## Robots.txt Handling Methods

```python
    def _get_robots_parser(self, url):
        """Get robots.txt parser for a domain."""
        parsed_url = urlparse(url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        if domain in self.robots_parsers:
            return self.robots_parsers[domain]
        
        # Create new parser
        robots_parser = RobotFileParser()
        robots_parser.set_url(f"{domain}/robots.txt")
        
        try:
            robots_parser.read()
            self.robots_parsers[domain] = robots_parser
        except Exception as e:
            print(f"Error reading robots.txt for {domain}: {e}")
            # If we can't read robots.txt, create an empty parser that allows everything
            robots_parser = RobotFileParser()
            self.robots_parsers[domain] = robots_parser
        
        return robots_parser
    
    def _can_fetch(self, url):
        """Check if we can fetch a URL according to robots.txt."""
        if not self.respect_robots:
            return True
        
        robots_parser = self._get_robots_parser(url)
        return robots_parser.can_fetch(self.user_agent, url)
```

## Rate Limiting and URL Management Methods

```python
    def _respect_rate_limits(self, domain):
        """Respect rate limits for a domain by sleeping if necessary."""
        current_time = time.time()
        
        if domain in self.domain_last_access:
            elapsed = current_time - self.domain_last_access[domain]
            if elapsed < self.rate_limit:
                time.sleep(self.rate_limit - elapsed)
        
        self.domain_last_access[domain] = time.time()
    
    def _add_to_frontier(self, url, depth):
        """Add URL to frontier if it meets criteria."""
        if url in self.visited_urls:
            return
        
        parsed_url = urlparse(url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        # Check domain page count
        domain_count = sum(1 for visited_url in self.visited_urls 
                          if urlparse(visited_url).netloc == parsed_url.netloc)
        
        if domain_count >= self.max_pages_per_domain:
            return
        
        # Check robots.txt
        if not self._can_fetch(url):
            return
        
        # Add to frontier
        self.url_frontier.append((url, depth))
```

## Content Extraction Methods

```python
    def _extract_links(self, soup, base_url):
        """Extract links from a BeautifulSoup object."""
        links = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            # Convert relative URLs to absolute
            absolute_url = urljoin(base_url, href)
            # Filter out non-HTTP/HTTPS URLs and fragments
            parsed = urlparse(absolute_url)
            if parsed.scheme in ('http', 'https') and not parsed.fragment:
                links.append(absolute_url)
        return links
    
    def _extract_text(self, soup):
        """Extract text content from a BeautifulSoup object."""
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.extract()
        
        # Get text
        text = soup.get_text()
        
        # Break into lines and remove leading and trailing space on each
        lines = (line.strip() for line in text.splitlines())
        
        # Break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        
        # Drop blank lines
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text
```

## Main Crawling Method

```python
    def crawl(self):
        """Start the crawling process."""
        # Initialize frontier with start URLs
        for url in self.start_urls:
            self._add_to_frontier(url, 0)
        
        # Process frontier until empty or max pages reached
        while self.url_frontier and len(self.visited_urls) < self.max_pages_per_domain * len(set(urlparse(u).netloc for u, _ in self.url_frontier if u not in self.visited_urls)):
            # Get next URL from frontier
            url, depth = self.url_frontier.pop(0)
            
            if url in self.visited_urls:
                continue
            
            # Mark as visited
            self.visited_urls.add(url)
            
            # Respect rate limits
            domain = urlparse(url).netloc
            self._respect_rate_limits(domain)
            
            # Fetch page
            try:
                headers = {'User-Agent': self.user_agent}
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                
                # Parse content
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Store result
                self.results.append({
                    'url': url,
                    'depth': depth,
                    'soup': soup,
                    'text_content': self._extract_text(soup),
                    'title': soup.title.text if soup.title else url
                })
                
                # If not at max depth, extract and add links to frontier
                if depth < self.max_depth:
                    links = self._extract_links(soup, url)
                    for link in links:
                        self._add_to_frontier(link, depth + 1)
                        
            except Exception as e:
                print(f"Error crawling {url}: {e}")
        
        return self.results
```

# Step 4: Define EnhancedKnowledgeReduction Class

The `EnhancedKnowledgeReduction` class provides sophisticated knowledge reduction capabilities:

1. **Multiple Similarity Methods**:
   - spaCy-based semantic similarity
   - TF-IDF vectorization with cosine similarity
   - Transformer-based embeddings using sentence-transformers
   - Hybrid approach combining all methods with configurable weights

2. **Advanced Clustering**:
   - Hierarchical clustering for better fact grouping
   - Central fact selection from clusters

3. **Entity-Based Reduction**:
   - Reduction based on entity overlap
   - Jaccard similarity for entity sets

4. **Multi-Stage Pipeline**:
   - Configurable reduction stages
   - Progressive filtering for optimal results

This implementation significantly improves the knowledge reduction capabilities compared to the original notebook.

```python
class EnhancedKnowledgeReduction:
    def __init__(self, use_transformer=True, transformer_model="sentence-transformers/all-MiniLM-L6-v2"):
        """
        Initialize the knowledge reduction system.
        
        Args:
            use_transformer (bool): Whether to use transformer models for embeddings
            transformer_model (str): Transformer model to use for embeddings
        """
        # Load spaCy model
        self.nlp = spacy.load("en_core_web_md")
        
        # Set up transformer model if requested
        self.use_transformer = use_transformer
        if use_transformer:
            self.transformer = SentenceTransformer(transformer_model)
        
        # Similarity calculation methods
        self.similarity_methods = {
            "spacy": self._spacy_similarity,
            "tfidf": self._tfidf_similarity,
            "transformer": self._transformer_similarity,
            "hybrid": self._hybrid_similarity
        }
```

## Similarity Calculation Methods

```python
    def _spacy_similarity(self, text1, text2):
        """Calculate similarity using spaCy."""
        doc1 = self.nlp(text1)
        doc2 = self.nlp(text2)
        return doc1.similarity(doc2)
    
    def _tfidf_similarity(self, texts):
        """Calculate TF-IDF similarity matrix for a list of texts."""
        # Create TF-IDF vectorizer
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(texts)
        
        # Calculate cosine similarity
        return cosine_similarity(tfidf_matrix)
    
    def _transformer_similarity(self, texts):
        """Calculate similarity using transformer embeddings."""
        if not self.use_transformer:
            raise ValueError("Transformer model not initialized")
        
        # Generate embeddings
        embeddings = self.transformer.encode(texts)
        
        # Calculate cosine similarity
        return cosine_similarity(embeddings)
    
    def _hybrid_similarity(self, texts, weights={"spacy": 0.3, "tfidf": 0.3, "transformer": 0.4}):
        """Calculate similarity using a weighted combination of methods."""
        similarity_matrices = {}
        
        # Calculate similarity using each method
        if "spacy" in weights:
            spacy_sim = np.zeros((len(texts), len(texts)))
            for i in range(len(texts)):
                for j in range(i, len(texts)):
                    sim = self._spacy_similarity(texts[i], texts[j])
                    spacy_sim[i, j] = sim
                    spacy_sim[j, i] = sim
            similarity_matrices["spacy"] = spacy_sim
        
        if "tfidf" in weights:
            similarity_matrices["tfidf"] = self._tfidf_similarity(texts)
        
        if "transformer" in weights and self.use_transformer:
            similarity_matrices["transformer"] = self._transformer_similarity(texts)
        
        # Combine similarity matrices using weights
        combined_sim = np.zeros((len(texts), len(texts)))
        weight_sum = sum(weights.values())
        
        for method, weight in weights.items():
            if method in similarity_matrices:
                combined_sim += (weight / weight_sum) * similarity_matrices[method]
        
        return combined_sim
```

## Clustering and Knowledge Reduction Methods

```python
    def _find_central_fact(self, indices, similarity_matrix):
        """Find the most central fact in a cluster."""
        # Calculate centrality as the sum of similarities to other facts in the cluster
        centrality = {}
        for i in indices:
            centrality[i] = sum(similarity_matrix[i, j] for j in indices if i != j)
        
        # Return the fact with highest centrality
        return max(centrality.items(), key=lambda x: x[1])[0]
    
    def reduce_knowledge(self, facts, method="hybrid", threshold=0.85, min_cluster_size=2):
        """
        Reduce knowledge by clustering similar facts.
        
        Args:
            facts (list): List of fact statements
            method (str): Similarity method to use
            threshold (float): Similarity threshold for clustering
            min_cluster_size (int): Minimum cluster size to consider
            
        Returns:
            list: List of representative facts after reduction
        """
        if len(facts) <= 1:
            return facts
        
        # Calculate similarity matrix
        if method == "hybrid":
            similarity_matrix = self._hybrid_similarity(facts)
        elif method in self.similarity_methods:
            similarity_matrix = self.similarity_methods[method](facts)
        else:
            raise ValueError(f"Unknown similarity method: {method}")
        
        # Apply hierarchical clustering
        # Convert similarity to distance
        distance_matrix = 1 - similarity_matrix
        
        # Apply clustering
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=1 - threshold,
            affinity='precomputed',
            linkage='average'
        ).fit(distance_matrix)
        
        # Get cluster labels
        labels = clustering.labels_
        
        # Group facts by cluster
        clusters = {}
        for i, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(i)
        
        # Select representative fact from each cluster
        representative_facts = []
        for label, indices in clusters.items():
            if len(indices) < min_cluster_size:
                # Keep all facts from small clusters
                for idx in indices:
                    representative_facts.append(facts[idx])
            else:
                # Select the most central fact as representative
                central_idx = self._find_central_fact(indices, similarity_matrix)
                representative_facts.append(facts[central_idx])
        
        return representative_facts
```

## Entity-Based Reduction Method

```python
    def entity_based_reduction(self, facts, threshold=0.85):
        """
        Reduce knowledge based on entity overlap.
        
        Args:
            facts (list): List of fact statements
            threshold (float): Similarity threshold for entity overlap
            
        Returns:
            list: List of facts after entity-based reduction
        """
        # Process facts with spaCy to extract entities
        docs = list(self.nlp.pipe(facts))
        
        # Create entity sets for each fact
        entity_sets = []
        for doc in docs:
            entities = set()
            for ent in doc.ents:
                entities.add((ent.text, ent.label_))
            entity_sets.append(entities)
        
        # Calculate entity overlap
        unique_facts = []
        unique_indices = []
        
        for i, (fact, entities) in enumerate(zip(facts, entity_sets)):
            # Skip if no entities
            if not entities:
                unique_facts.append(fact)
                unique_indices.append(i)
                continue
            
            # Check if similar to any existing unique fact
            is_unique = True
            for j in unique_indices:
                # Calculate Jaccard similarity of entity sets
                overlap = len(entities.intersection(entity_sets[j]))
                union = len(entities.union(entity_sets[j]))
                
                if union > 0 and overlap / union > threshold:
                    is_unique = False
                    break
            
            if is_unique:
                unique_facts.append(fact)
                unique_indices.append(i)
        
        return unique_facts
```

## Multi-Stage Reduction Pipeline

```python
    def multi_stage_reduction(self, facts, stages=None):
        """
        Apply multi-stage knowledge reduction.
        
        Args:
            facts (list): List of fact statements
            stages (list): List of reduction stages to apply
            
        Returns:
            list: List of facts after multi-stage reduction
        """
        if stages is None:
            stages = [
                {"method": "length_filter", "min_length": 50},
                {"method": "entity_based", "threshold": 0.8},
                {"method": "hybrid", "threshold": 0.85}
            ]
        
        reduced_facts = facts
        
        for stage in stages:
            method = stage["method"]
            
            if method == "length_filter":
                min_length = stage.get("min_length", 50)
                reduced_facts = [f for f in reduced_facts if len(f) >= min_length]
            
            elif method == "entity_based":
                threshold = stage.get("threshold", 0.8)
                reduced_facts = self.entity_based_reduction(reduced_facts, threshold)
            
            elif method in self.similarity_methods or method == "hybrid":
                threshold = stage.get("threshold", 0.85)
                min_cluster_size = stage.get("min_cluster_size", 2)
                reduced_facts = self.reduce_knowledge(
                    reduced_facts, method=method, 
                    threshold=threshold, min_cluster_size=min_cluster_size
                )
            
            print(f"After {method} reduction: {len(reduced_facts)} facts remaining")
        
        return reduced_facts
```

# Step 5: Helper Functions

These helper functions provide essential utilities for:

1. **Processing Text into Facts**: Converting raw text content into structured facts
2. **Populating Knowledge Graph**: Adding facts from crawler results to the knowledge graph
3. **Applying Knowledge Reduction**: Using the enhanced reduction algorithms on the knowledge graph

These functions bridge the gap between the crawler and knowledge graph components.

```python
def process_text_into_facts(text, min_length=30):
    """
    Process text content into facts.
    
    Args:
        text (str): Text content to process
        min_length (int): Minimum length for a fact
        
    Returns:
        list: List of facts
    """
    # Split text into sentences (simple approach)
    sentences = [s.strip() for s in text.replace('\n', ' ').split('.') if s.strip()]
    
    # Combine short sentences
    facts = []
    current_fact = ""
    
    for sentence in sentences:
        if len(current_fact) + len(sentence) <= min_length:
            current_fact += " " + sentence if current_fact else sentence
        else:
            if current_fact:
                facts.append(current_fact + ".")
            current_fact = sentence
    
    # Add the last fact if not empty
    if current_fact:
        facts.append(current_fact + ".")
    
    return facts

def populate_knowledge_graph_from_crawler(kg, crawler_results):
    """
    Populate knowledge graph from crawler results.
    
    Args:
        kg: KnowledgeGraph instance
        crawler_results: Results from the RecursiveCrawler
    """
    for result in crawler_results:
        url = result['url']
        title = result['title']
        text_content = result['text_content']
        
        # Process text content into facts
        facts = process_text_into_facts(text_content)
        
        # Add facts to knowledge graph
        for fact in facts:
            kg.add_fact(
                fact_statement=fact,
                source_id=url,
                source_name=title,
                reliability=ReliabilityRating.MEDIUM,  # Default rating
                category="Web Content",
                tags=["crawled", f"depth_{result['depth']}"]
            )

def apply_knowledge_reduction(kg, reducer=None):
    """
    Apply knowledge reduction to a knowledge graph.
    
    Args:
        kg: KnowledgeGraph instance
        reducer: EnhancedKnowledgeReduction instance (created if None)
    
    Returns:
        KnowledgeGraph: New knowledge graph with reduced facts
    """
    if reducer is None:
        reducer = EnhancedKnowledgeReduction()
    
    # Extract facts from knowledge graph
    facts = [fact['fact_statement'] for fact in kg.data]
    
    # Apply multi-stage reduction
    reduced_facts = reducer.multi_stage_reduction(facts)
    
    # Create new knowledge graph with reduced facts
    reduced_kg = KnowledgeGraph()
    
    # Add reduced facts to new knowledge graph
    for fact_statement in reduced_facts:
        # Find original fact in knowledge graph
        for fact in kg.data:
            if fact['fact_statement'] == fact_statement:
                # Copy fact to new knowledge graph
                reduced_kg.add_fact(
                    fact_statement=fact['fact_statement'],
                    source_id=fact['source_id'],
                    source_name=fact['source_name'],
                    reliability=fact['reliability'],
                    category=fact['category'],
                    tags=fact['tags']
                )
                break
    
    return reduced_kg
```

# Step 6: Advanced Web Crawling

This section demonstrates the enhanced web crawling capabilities:

1. **Multiple Start URLs**: Crawling begins from multiple seed URLs
2. **Configurable Parameters**: Depth, page limits, and rate limiting are all configurable
3. **Statistics Collection**: Detailed information about the crawling process is collected

The crawler respects web etiquette standards while efficiently gathering content from multiple sources.

```python
# Initialize the crawler with multiple start URLs
start_urls = [
    "https://civichonors.com/",
    "https://www.nelslindahl.com/",
    "https://en.wikipedia.org/wiki/Knowledge_graph",
    "https://en.wikipedia.org/wiki/Web_crawler"
]

# Create the crawler with custom settings
crawler = RecursiveCrawler(
    start_urls=start_urls,
    max_depth=2,  # Follow links up to 2 levels deep
    max_pages_per_domain=5,  # Limit to 5 pages per domain
    respect_robots=True,  # Respect robots.txt
    rate_limit=1.0,  # Wait at least 1 second between requests to the same domain
    user_agent="KnowledgeReduceCrawler/1.0"
)

# Start crawling
print("Starting crawling process...")
results = crawler.crawl()
print(f"Crawling complete. Visited {len(crawler.visited_urls)} URLs, collected {len(results)} pages.")

# Print statistics about the crawled pages
domains = {}
depths = {}

for result in results:
    domain = urlparse(result['url']).netloc
    depth = result['depth']
    
    if domain not in domains:
        domains[domain] = 0
    domains[domain] += 1
    
    if depth not in depths:
        depths[depth] = 0
    depths[depth] += 1

print("\nPages per domain:")
for domain, count in domains.items():
    print(f"  {domain}: {count} pages")

print("\nPages per depth level:")
for depth, count in sorted(depths.items()):
    print(f"  Depth {depth}: {count} pages")
```

# Step 7: Populate the KnowledgeGraph

This section demonstrates how the knowledge graph is populated from the crawler results:

1. **Fact Extraction**: Text content is processed into structured facts
2. **Metadata Enrichment**: Facts are enriched with source information and crawl depth
3. **Statistics Analysis**: Detailed information about the facts is collected and analyzed

The knowledge graph provides a structured representation of the information gathered during crawling.

```python
# Initialize the KnowledgeGraph
kg = KnowledgeGraph()

# Populate the knowledge graph from crawler results
populate_knowledge_graph_from_crawler(kg, results)

# Print statistics
print(f"Knowledge graph populated with {len(kg.data)} facts from {len(results)} pages.")

# Display a sample of facts
print("\nSample facts:")
for fact in kg.data[:5]:
    print(f"Fact {fact['fact_id']}: {fact['fact_statement'][:100]}... (Source: {fact['source_name']})")

# Count facts by depth
facts_by_depth = {}
for fact in kg.data:
    depth_tags = [tag for tag in fact['tags'] if tag.startswith('depth_')]
    if depth_tags:
        depth = int(depth_tags[0].split('_')[1])
        if depth not in facts_by_depth:
            facts_by_depth[depth] = 0
        facts_by_depth[depth] += 1

print("\nFacts by crawl depth:")
for depth, count in sorted(facts_by_depth.items()):
    print(f"  Depth {depth}: {count} facts")
```

# Step 8: Apply Advanced Knowledge Reduction

This section demonstrates the enhanced knowledge reduction capabilities:

1. **Multi-Stage Reduction**: Facts are processed through multiple reduction stages
2. **Comparison Analysis**: Original and reduced knowledge graph sizes are compared
3. **Representative Facts**: The most central and informative facts are retained

The knowledge reduction process significantly improves the quality and conciseness of the knowledge graph.

```python
# Initialize the knowledge reducer
reducer = EnhancedKnowledgeReduction(use_transformer=True)

# Apply multi-stage knowledge reduction
print("Applying multi-stage knowledge reduction...")
reduced_kg = apply_knowledge_reduction(kg, reducer)

print(f"\nOriginal knowledge graph: {len(kg.data)} facts")
print(f"Reduced knowledge graph: {len(reduced_kg.data)} facts")
print(f"Reduction ratio: {len(reduced_kg.data) / len(kg.data):.2f}")

# Display sample of reduced facts
print("\nSample reduced facts:")
for fact in reduced_kg.data[:10]:
    print(f"Fact {fact['fact_id']}: {fact['fact_statement'][:100]}... (Source: {fact['source_name']})")
```

# Step 9: Serialize the KnowledgeGraph for Portability

This section demonstrates how the knowledge graph is serialized for portability:

1. **JSON Serialization**: The knowledge graph is converted to JSON format
2. **Sharding Implementation**: Large datasets are split into manageable shards
3. **Deserialization Support**: The serialized data can be reconstructed into a knowledge graph

The serialization process facilitates easy storage, transfer, and reconstruction of the knowledge graph.

```python
class KnowledgeGraphPortable:
    def __init__(self, knowledge_graph=None):
        """
        Initialize the portable knowledge graph.
        
        Args:
            knowledge_graph: KnowledgeGraph instance to serialize
        """
        self.data = []
        if knowledge_graph:
            self.serialize(knowledge_graph)
    
    def serialize(self, knowledge_graph):
        """
        Serialize a knowledge graph to JSON.
        
        Args:
            knowledge_graph: KnowledgeGraph instance to serialize
        """
        self.data = []
        for fact in knowledge_graph.data:
            # Convert enum to string for JSON serialization
            fact_copy = fact.copy()
            if isinstance(fact_copy['reliability'], ReliabilityRating):
                fact_copy['reliability'] = fact_copy['reliability'].name
            self.data.append(fact_copy)
    
    def save_to_json(self, filename, shard_size=100):
        """
        Save the serialized knowledge graph to JSON files with sharding.
        
        Args:
            filename (str): Base filename to save to
            shard_size (int): Number of facts per shard
        """
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)
        
        # Shard the data
        for i in range(0, len(self.data), shard_size):
            shard = self.data[i:i+shard_size]
            shard_filename = f"{os.path.splitext(filename)[0]}_shard_{i//shard_size}{os.path.splitext(filename)[1]}"
            with open(shard_filename, 'w') as f:
                json.dump(shard, f, indent=2)
    
    def load_from_json(self, filename_pattern):
        """
        Load the serialized knowledge graph from JSON files.
        
        Args:
            filename_pattern (str): Pattern to match JSON files
        """
        self.data = []
        
        # Find all matching files
        import glob
        files = glob.glob(filename_pattern)
        
        for file in sorted(files):
            with open(file, 'r') as f:
                shard_data = json.load(f)
                self.data.extend(shard_data)
    
    def deserialize(self):
        """
        Deserialize the JSON data to a KnowledgeGraph instance.
        
        Returns:
            KnowledgeGraph: Deserialized knowledge graph
        """
        kg = KnowledgeGraph()
        
        for fact in self.data:
            # Convert string back to enum
            if isinstance(fact['reliability'], str):
                fact['reliability'] = ReliabilityRating[fact['reliability']]
            
            # Add fact to knowledge graph
            kg.add_fact(
                fact_statement=fact['fact_statement'],
                source_id=fact['source_id'],
                source_name=fact['source_name'],
                reliability=fact['reliability'],
                category=fact['category'],
                tags=fact['tags'],
                quality_score=fact['quality_score']
            )
        
        return kg

# Create a portable version of the reduced knowledge graph
kg_portable = KnowledgeGraphPortable(reduced_kg)

# Save to JSON files with sharding
kg_portable.save_to_json("reduced_knowledge_graph.json", shard_size=100)

# List the created JSON files
import glob
json_files = glob.glob("reduced_knowledge_graph*.json")
print(f"Created {len(json_files)} JSON files:")
for file in sorted(json_files):
    print(f"  {file}")
```
