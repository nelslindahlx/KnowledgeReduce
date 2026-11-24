# Enhanced Web Crawler Design

## Current Limitations
The current implementation in CivicHonorsKGv18.ipynb has several limitations:
1. Only scrapes two specific websites
2. Uses basic requests.get without recursive crawling
3. Lacks robots.txt handling and rate limiting
4. Has no URL frontier management
5. Cannot follow links to discover new content

## Enhanced Design

### 1. Recursive Crawler Class
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

### 2. Robots.txt Handling
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

### 3. Rate Limiting
```python
def _respect_rate_limits(self, domain):
    """Respect rate limits for a domain by sleeping if necessary."""
    current_time = time.time()
    
    if domain in self.domain_last_access:
        elapsed = current_time - self.domain_last_access[domain]
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
    
    self.domain_last_access[domain] = time.time()
```

### 4. URL Frontier Management
```python
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

### 5. Link Extraction
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
```

### 6. Main Crawling Method
```python
def crawl(self):
    """Start the crawling process."""
    # Initialize frontier with start URLs
    for url in self.start_urls:
        self._add_to_frontier(url, 0)
    
    # Process frontier until empty or max pages reached
    while self.url_frontier and len(self.visited_urls) < self.max_pages_per_domain * len(set(urlparse(u).netloc for u, _ in self.url_frontier)):
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

### 7. Text Extraction Method
```python
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

## Integration with Knowledge Graph

The enhanced crawler will be integrated with the existing KnowledgeGraph class:

```python
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
```

This enhanced design will significantly improve the notebook's ability to crawl and process multiple webpages while respecting web etiquette standards.
