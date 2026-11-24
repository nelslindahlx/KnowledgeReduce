"""
Improved Page Search Module for CivicHonorsKG

This module enhances the original notebook with advanced page searching capabilities:
- Keyword-based search
- Content relevance scoring
- Semantic search
- Structured data extraction
- CSS selector support
- Regular expression search
- Entity recognition
- Context preservation
- Metadata extraction
- Content classification
- Search result ranking
- Cross-page information linking
"""

import re
import spacy
from bs4 import BeautifulSoup
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Set, Tuple, Optional, Union, Callable
import logging
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('page_searcher')

class PageSearcher:
    """Class for searching and extracting information from web pages with advanced features."""
    
    def __init__(self, 
                 spacy_model: str = 'en_core_web_md',
                 transformer_model: str = 'all-MiniLM-L6-v2',
                 min_content_length: int = 20,
                 relevance_threshold: float = 0.5,
                 context_window: int = 2):
        """
        Initialize the PageSearcher.
        
        Args:
            spacy_model: Name of spaCy model to use
            transformer_model: Name of sentence transformer model to use
            min_content_length: Minimum length of content to consider
            relevance_threshold: Minimum relevance score for content to be included
            context_window: Number of surrounding elements to include as context
        """
        self.min_content_length = min_content_length
        self.relevance_threshold = relevance_threshold
        self.context_window = context_window
        
        # Load NLP models
        logger.info(f"Loading spaCy model: {spacy_model}")
        self.nlp = spacy.load(spacy_model)
        
        logger.info(f"Loading sentence transformer model: {transformer_model}")
        self.transformer = SentenceTransformer(transformer_model)
        
        # Initialize storage for extracted information
        self.extracted_facts = []
        self.entity_index = defaultdict(list)  # Maps entity -> list of fact indices
        self.keyword_index = defaultdict(list)  # Maps keyword -> list of fact indices
        self.url_to_facts = defaultdict(list)  # Maps URL -> list of fact indices
        
    def extract_text_with_context(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Extract text from HTML elements with surrounding context.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            List of dictionaries with text and context
        """
        elements = []
        
        # Get all elements that might contain content
        content_elements = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'div', 'span', 'article', 'section'])
        
        for i, element in enumerate(content_elements):
            text = element.get_text().strip()
            
            # Skip empty or very short elements
            if not text or len(text) < self.min_content_length:
                continue
            
            # Get context (surrounding elements)
            start_idx = max(0, i - self.context_window)
            end_idx = min(len(content_elements), i + self.context_window + 1)
            
            context_elements = content_elements[start_idx:i] + content_elements[i+1:end_idx]
            context = [elem.get_text().strip() for elem in context_elements if elem.get_text().strip()]
            
            elements.append({
                'text': text,
                'element_type': element.name,
                'context': context,
                'html': str(element)
            })
        
        return elements
    
    def extract_structured_data(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Extract structured data like tables and lists.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            List of dictionaries with structured data
        """
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
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract named entities from text using spaCy.
        
        Args:
            text: Text to extract entities from
            
        Returns:
            Dictionary mapping entity types to lists of entities
        """
        doc = self.nlp(text)
        entities = defaultdict(list)
        
        for ent in doc.ents:
            entities[ent.label_].append(ent.text)
        
        return dict(entities)
    
    def calculate_relevance_score(self, text: str, query_embedding: np.ndarray) -> float:
        """
        Calculate relevance score of text to a query.
        
        Args:
            text: Text to score
            query_embedding: Embedding of the query
            
        Returns:
            Relevance score between 0 and 1
        """
        text_embedding = self.transformer.encode([text])[0]
        similarity = cosine_similarity([query_embedding], [text_embedding])[0][0]
        return float(similarity)
    
    def search_by_keywords(self, pages: Dict[str, Dict], keywords: List[str]) -> List[Dict]:
        """
        Search pages for specific keywords.
        
        Args:
            pages: Dictionary of pages from LinkCollector
            keywords: List of keywords to search for
            
        Returns:
            List of dictionaries with search results
        """
        results = []
        
        for url, page_data in pages.items():
            soup = page_data['soup']
            
            # Get all text elements
            elements = self.extract_text_with_context(soup)
            
            for element in elements:
                text = element['text'].lower()
                
                # Check if any keyword is in the text
                matches = [keyword for keyword in keywords if keyword.lower() in text]
                
                if matches:
                    results.append({
                        'url': url,
                        'text': element['text'],
                        'element_type': element['element_type'],
                        'context': element['context'],
                        'matched_keywords': matches,
                        'html': element['html']
                    })
        
        return results
    
    def search_by_regex(self, pages: Dict[str, Dict], pattern: str) -> List[Dict]:
        """
        Search pages using regular expression pattern.
        
        Args:
            pages: Dictionary of pages from LinkCollector
            pattern: Regular expression pattern
            
        Returns:
            List of dictionaries with search results
        """
        results = []
        regex = re.compile(pattern)
        
        for url, page_data in pages.items():
            soup = page_data['soup']
            
            # Get all text elements
            elements = self.extract_text_with_context(soup)
            
            for element in elements:
                text = element['text']
                
                # Find all matches
                matches = regex.findall(text)
                
                if matches:
                    results.append({
                        'url': url,
                        'text': element['text'],
                        'element_type': element['element_type'],
                        'context': element['context'],
                        'regex_matches': matches,
                        'html': element['html']
                    })
        
        return results
    
    def search_by_css_selector(self, pages: Dict[str, Dict], css_selector: str) -> List[Dict]:
        """
        Search pages using CSS selector.
        
        Args:
            pages: Dictionary of pages from LinkCollector
            css_selector: CSS selector string
            
        Returns:
            List of dictionaries with search results
        """
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
    
    def semantic_search(self, pages: Dict[str, Dict], query: str, top_k: int = 10) -> List[Dict]:
        """
        Perform semantic search on pages using sentence transformers.
        
        Args:
            pages: Dictionary of pages from LinkCollector
            query: Search query
            top_k: Number of top results to return
            
        Returns:
            List of dictionaries with search results, sorted by relevance
        """
        # Encode the query
        query_embedding = self.transformer.encode([query])[0]
        
        all_elements = []
        
        # Extract text elements from all pages
        for url, page_data in pages.items():
            soup = page_data['soup']
            elements = self.extract_text_with_context(soup)
            
            for element in elements:
                all_elements.append({
                    'url': url,
                    'text': element['text'],
                    'element_type': element['element_type'],
                    'context': element['context'],
                    'html': element['html']
                })
        
        # Calculate relevance scores
        for element in all_elements:
            element['relevance_score'] = self.calculate_relevance_score(element['text'], query_embedding)
        
        # Sort by relevance score and take top_k
        results = sorted(all_elements, key=lambda x: x['relevance_score'], reverse=True)[:top_k]
        
        return results
    
    def extract_facts_from_pages(self, pages: Dict[str, Dict], topics: List[str] = None) -> List[Dict]:
        """
        Extract facts from pages with optional topic filtering.
        
        Args:
            pages: Dictionary of pages from LinkCollector
            topics: Optional list of topics to filter by
            
        Returns:
            List of dictionaries with extracted facts
        """
        # Reset storage
        self.extracted_facts = []
        self.entity_index = defaultdict(list)
        self.keyword_index = defaultdict(list)
        self.url_to_facts = defaultdict(list)
        
        # Encode topics if provided
        topic_embeddings = None
        if topics:
            topic_embeddings = self.transformer.encode(topics)
        
        for url, page_data in pages.items():
            soup = page_data['soup']
            metadata = page_data['metadata']
            
            # Extract text elements
            elements = self.extract_text_with_context(soup)
            
            # Extract structured data
            structured_data = self.extract_structured_data(soup)
            
            # Process text elements
            for element in elements:
                text = element['text']
                
                # Skip if too short
                if len(text) < self.min_content_length:
                    continue
                
                # Check relevance to topics if provided
                if topic_embeddings is not None:
                    text_embedding = self.transformer.encode([text])[0]
                    similarities = cosine_similarity([text_embedding], topic_embeddings)[0]
                    max_similarity = max(similarities)
                    
                    if max_similarity < self.relevance_threshold:
                        continue
                    
                    topic_relevance = {topics[i]: float(similarities[i]) for i in range(len(topics))}
                else:
                    topic_relevance = {}
                    max_similarity = 1.0
                
                # Extract entities
                entities = self.extract_entities(text)
                
                # Create fact
                fact = {
                    'text': text,
                    'url': url,
                    'element_type': element['element_type'],
                    'context': element['context'],
                    'entities': entities,
                    'topic_relevance': topic_relevance,
                    'relevance_score': max_similarity,
                    'metadata': metadata,
                    'html': element['html']
                }
                
                # Add to storage
                fact_idx = len(self.extracted_facts)
                self.extracted_facts.append(fact)
                self.url_to_facts[url].append(fact_idx)
                
                # Index entities
                for entity_type, entity_list in entities.items():
                    for entity in entity_list:
                        self.entity_index[entity].append(fact_idx)
                
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
                        
                        # Extract entities
                        entities = self.extract_entities(row_text)
                        
                        # Create fact
                        fact = {
                            'text': row_text,
                            'url': url,
                            'element_type': 'table_row',
                            'context': [],
                            'entities': entities,
                            'topic_relevance': {},
                            'relevance_score': 1.0,
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
                        
                        # Index entities
                        for entity_type, entity_list in entities.items():
                            for entity in entity_list:
                                self.entity_index[entity].append(fact_idx)
                
                elif data['type'] == 'list':
                    # For lists, create a fact for the entire list
                    list_text = '. '.join(data['items'])
                    
                    # Skip if too short
                    if len(list_text) < self.min_content_length:
                        continue
                    
                    # Extract entities
                    entities = self.extract_entities(list_text)
                    
                    # Create fact
                    fact = {
                        'text': list_text,
                        'url': url,
                        'element_type': f"{data['list_type']}_list",
                        'context': [],
                        'entities': entities,
                        'topic_relevance': {},
                        'relevance_score': 1.0,
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
                    
                    # Index entities
                    for entity_type, entity_list in entities.items():
                        for entity in entity_list:
                            self.entity_index[entity].append(fact_idx)
        
        return self.extracted_facts
    
    def search_facts_by_entity(self, entity: str) -> List[Dict]:
        """
        Search extracted facts by entity.
        
        Args:
            entity: Entity to search for
            
        Returns:
            List of facts containing the entity
        """
        fact_indices = self.entity_index.get(entity, [])
        return [self.extracted_facts[idx] for idx in fact_indices]
    
    def search_facts_by_keyword(self, keyword: str) -> List[Dict]:
        """
        Search extracted facts by keyword.
        
        Args:
            keyword: Keyword to search for
            
        Returns:
            List of facts containing the keyword
        """
        keyword = keyword.lower()
        fact_indices = self.keyword_index.get(keyword, [])
        return [self.extracted_facts[idx] for idx in fact_indices]
    
    def get_facts_by_url(self, url: str) -> List[Dict]:
        """
        Get all facts extracted from a specific URL.
        
        Args:
            url: URL to get facts for
            
        Returns:
            List of facts from the URL
        """
        fact_indices = self.url_to_facts.get(url, [])
        return [self.extracted_facts[idx] for idx in fact_indices]
    
    def find_related_facts(self, fact_idx: int, threshold: float = 0.7) -> List[Tuple[int, float]]:
        """
        Find facts related to a given fact based on semantic similarity.
        
        Args:
            fact_idx: Index of the fact to find related facts for
            threshold: Minimum similarity threshold
            
        Returns:
            List of tuples (fact_idx, similarity_score)
        """
        if fact_idx >= len(self.extracted_facts):
            return []
        
        fact = self.extracted_facts[fact_idx]
        fact_embedding = self.transformer.encode([fact['text']])[0]
        
        related = []
        
        # Encode all other facts
        for i, other_fact in enumerate(self.extracted_facts):
            if i == fact_idx:
                continue
            
            other_embedding = self.transformer.encode([other_fact['text']])[0]
            similarity = cosine_similarity([fact_embedding], [other_embedding])[0][0]
            
            if similarity >= threshold:
                related.append((i, float(similarity)))
        
        # Sort by similarity
        related.sort(key=lambda x: x[1], reverse=True)
        
        return related
    
    def classify_content(self, text: str, categories: List[str]) -> Dict[str, float]:
        """
        Classify content into predefined categories using semantic similarity.
        
        Args:
            text: Text to classify
            categories: List of category names
            
        Returns:
            Dictionary mapping categories to confidence scores
        """
        # Encode text and categories
        text_embedding = self.transformer.encode([text])[0]
        category_embeddings = self.transformer.encode(categories)
        
        # Calculate similarities
        similarities = cosine_similarity([text_embedding], category_embeddings)[0]
        
        # Create result dictionary
        result = {categories[i]: float(similarities[i]) for i in range(len(categories))}
        
        return result


# Example usage functions
def extract_civic_honors_facts(pages: Dict[str, Dict]) -> List[Dict]:
    """Extract facts specifically related to Civic Honors."""
    searcher = PageSearcher()
    return searcher.extract_facts_from_pages(pages, topics=['civic honors', 'community service', 'volunteering'])

def find_contact_information(pages: Dict[str, Dict]) -> List[Dict]:
    """Find contact information in pages."""
    searcher = PageSearcher()
    
    # Use regex to find email addresses and phone numbers
    email_results = searcher.search_by_regex(pages, r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    phone_results = searcher.search_by_regex(pages, r'\b(\+\d{1,2}\s)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b')
    
    # Use CSS selectors to find contact forms
    form_results = searcher.search_by_css_selector(pages, 'form')
    
    return email_results + phone_results + form_results
