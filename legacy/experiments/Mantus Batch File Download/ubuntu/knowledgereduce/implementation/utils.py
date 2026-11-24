"""
Utility functions for knowledge graph operations.
This module provides helper functions for working with knowledge graphs.
"""
import re
import requests
from bs4 import BeautifulSoup
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.tag import pos_tag

# Download required NLTK resources if not already present
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

try:
    nltk.data.find('taggers/averaged_perceptron_tagger')
except LookupError:
    nltk.download('averaged_perceptron_tagger')

def scrape_webpage(url):
    """
    Scrape text content from a webpage.
    
    Args:
        url (str): URL of the webpage to scrape
        
    Returns:
        str: Extracted text content from the webpage
        
    Raises:
        Exception: If there's an error fetching or parsing the webpage
    """
    try:
        # Send HTTP request to the webpage
        response = requests.get(url)
        response.raise_for_status()  # Raise exception for HTTP errors
        
        # Parse HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract text from paragraph tags
        paragraphs = soup.find_all('p')
        text_content = ' '.join([p.get_text() for p in paragraphs])
        
        return text_content
    except Exception as e:
        raise Exception(f"Error scraping webpage: {e}")

def extract_entities_from_text(text):
    """
    Extract entities (proper nouns) from text.
    
    Args:
        text (str): Text to extract entities from
        
    Returns:
        list: List of extracted entities
    """
    # Tokenize text into sentences
    sentences = sent_tokenize(text)
    
    entities = []
    
    # Process each sentence
    for sentence in sentences:
        # Tokenize sentence into words and tag parts of speech
        words = word_tokenize(sentence)
        tagged_words = pos_tag(words)
        
        # Extract proper nouns (NNP)
        sentence_entities = [word for word, tag in tagged_words if tag == 'NNP']
        entities.extend(sentence_entities)
    
    return entities

def create_knowledge_graph_from_text(text, knowledge_graph=None):
    """
    Create a knowledge graph from text content.
    
    Args:
        text (str): Text content to process
        knowledge_graph (KnowledgeGraph, optional): Existing knowledge graph to add to. 
                                                   If None, creates a new one.
        
    Returns:
        KnowledgeGraph: The created or updated knowledge graph
    """
    # Import here to avoid circular imports
    from .core import KnowledgeGraph, ReliabilityRating
    
    # Create new knowledge graph if none provided
    if knowledge_graph is None:
        knowledge_graph = KnowledgeGraph()
    
    # Tokenize text into sentences
    sentences = sent_tokenize(text)
    
    # Process each sentence
    for i, sentence in enumerate(sentences):
        # Tokenize sentence into words and tag parts of speech
        words = word_tokenize(sentence)
        tagged_words = pos_tag(words)
        
        # Extract proper nouns (NNP) as entities
        entities = [word for word, tag in tagged_words if tag == 'NNP']
        
        # Skip if no entities found
        if len(entities) < 1:
            continue
        
        # Add each entity as a fact
        for j, entity in enumerate(entities):
            fact_id = f"fact_{i}_{j}"
            
            # Add fact to knowledge graph
            knowledge_graph.add_fact(
                fact_id=fact_id,
                fact_statement=entity,
                category="Entity",
                tags=["extracted", "entity"],
                date_recorded="auto",
                last_updated="auto",
                reliability_rating=ReliabilityRating.UNVERIFIED,
                source_id="text_extraction",
                source_title="Extracted from text",
                author_creator="auto",
                publication_date="auto",
                url_reference="",
                related_facts=[],
                contextual_notes=sentence,
                access_level="public",
                usage_count=1
            )
            
            # Add relationships between consecutive entities in the same sentence
            if j > 0:
                prev_fact_id = f"fact_{i}_{j-1}"
                knowledge_graph.add_relationship(
                    prev_fact_id,
                    fact_id,
                    "appears_with",
                    weight=1.0,
                    attributes={"sentence": sentence}
                )
    
    return knowledge_graph

def create_knowledge_graph_from_url(url, knowledge_graph=None):
    """
    Create a knowledge graph from a webpage.
    
    Args:
        url (str): URL of the webpage to process
        knowledge_graph (KnowledgeGraph, optional): Existing knowledge graph to add to.
                                                   If None, creates a new one.
        
    Returns:
        KnowledgeGraph: The created or updated knowledge graph
    """
    # Scrape webpage content
    text_content = scrape_webpage(url)
    
    # Create knowledge graph from text
    return create_knowledge_graph_from_text(text_content, knowledge_graph)

def merge_knowledge_graphs(kg1, kg2):
    """
    Merge two knowledge graphs.
    
    Args:
        kg1 (KnowledgeGraph): First knowledge graph
        kg2 (KnowledgeGraph): Second knowledge graph
        
    Returns:
        KnowledgeGraph: Merged knowledge graph
    """
    # Import here to avoid circular imports
    from .core import KnowledgeGraph
    
    # Create a new knowledge graph for the merged result
    merged_kg = KnowledgeGraph()
    
    # Copy nodes and edges from kg1
    merged_kg.graph = kg1.graph.copy()
    
    # Add nodes from kg2 that don't exist in kg1
    for node, data in kg2.graph.nodes(data=True):
        if node not in merged_kg.graph:
            merged_kg.graph.add_node(node, **data)
    
    # Add edges from kg2
    for u, v, data in kg2.graph.edges(data=True):
        if not merged_kg.graph.has_edge(u, v):
            merged_kg.graph.add_edge(u, v, **data)
    
    return merged_kg
