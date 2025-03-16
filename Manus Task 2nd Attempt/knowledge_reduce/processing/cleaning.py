"""
Data processing utilities for the KnowledgeReduce framework.

This module provides functions for cleaning, deduplicating, and refining
data in knowledge graphs.
"""

from difflib import SequenceMatcher
import spacy


def remove_duplicate_facts(knowledge_graph):
    """
    Remove duplicate facts from a knowledge graph based on exact statement matches.
    
    Args:
        knowledge_graph: KnowledgeGraph instance
        
    Returns:
        int: Number of duplicates removed
    """
    # Get all facts
    facts = knowledge_graph.get_all_facts()
    
    # Track unique statements and duplicates
    unique_statements = set()
    duplicates = []
    
    # Find duplicates
    for fact in facts:
        statement = fact['fact_statement']
        if statement in unique_statements:
            duplicates.append(fact['fact_id'])
        else:
            unique_statements.add(statement)
    
    # Remove duplicates
    for fact_id in duplicates:
        knowledge_graph.remove_fact(fact_id)
    
    return len(duplicates)


def advanced_cleaning(knowledge_graph, similarity_threshold=0.8, short_fact_threshold=50):
    """
    Perform advanced cleaning on a knowledge graph.
    
    This includes removing short facts and facts with high string similarity.
    
    Args:
        knowledge_graph: KnowledgeGraph instance
        similarity_threshold: Threshold for string similarity (0.0-1.0)
        short_fact_threshold: Minimum length for facts
        
    Returns:
        tuple: (removed_short, removed_similar) counts
    """
    # Get all facts
    facts = knowledge_graph.get_all_facts()
    
    # Remove short facts
    short_facts = [fact['fact_id'] for fact in facts 
                  if len(fact['fact_statement']) < short_fact_threshold]
    
    for fact_id in short_facts:
        knowledge_graph.remove_fact(fact_id)
    
    # Get updated facts after removing short ones
    facts = knowledge_graph.get_all_facts()
    
    # Find similar facts
    similar_facts = []
    for i, fact1 in enumerate(facts):
        for fact2 in facts[i+1:]:
            similarity = SequenceMatcher(
                None, 
                fact1['fact_statement'], 
                fact2['fact_statement']
            ).ratio()
            
            if similarity > similarity_threshold:
                # Keep the longer fact, remove the shorter one
                if len(fact1['fact_statement']) >= len(fact2['fact_statement']):
                    similar_facts.append(fact2['fact_id'])
                else:
                    similar_facts.append(fact1['fact_id'])
    
    # Remove similar facts
    for fact_id in set(similar_facts):  # Use set to avoid duplicates
        knowledge_graph.remove_fact(fact_id)
    
    return len(short_facts), len(similar_facts)


def semantic_cleaning(knowledge_graph, similarity_threshold=0.85, model_name="en_core_web_md"):
    """
    Perform semantic cleaning on a knowledge graph using spaCy.
    
    This removes facts that are semantically similar based on NLP embeddings.
    
    Args:
        knowledge_graph: KnowledgeGraph instance
        similarity_threshold: Threshold for semantic similarity (0.0-1.0)
        model_name: Name of the spaCy model to use
        
    Returns:
        int: Number of similar facts removed
    """
    try:
        # Load spaCy model
        nlp = spacy.load(model_name)
    except OSError:
        print(f"SpaCy model '{model_name}' not found. Please download it with:")
        print(f"python -m spacy download {model_name}")
        return 0
    
    # Get all facts
    facts = knowledge_graph.get_all_facts()
    
    # Process facts with spaCy
    processed_facts = []
    for fact in facts:
        doc = nlp(fact['fact_statement'])
        processed_facts.append((fact['fact_id'], doc))
    
    # Find semantically similar facts
    similar_facts = []
    for i, (fact1_id, doc1) in enumerate(processed_facts):
        for fact2_id, doc2 in processed_facts[i+1:]:
            # Calculate semantic similarity
            similarity = doc1.similarity(doc2)
            
            if similarity > similarity_threshold:
                # Find which fact to remove (shorter one)
                fact1 = knowledge_graph.get_fact(fact1_id)
                fact2 = knowledge_graph.get_fact(fact2_id)
                
                if len(fact1['fact_statement']) >= len(fact2['fact_statement']):
                    similar_facts.append(fact2_id)
                else:
                    similar_facts.append(fact1_id)
    
    # Remove similar facts
    for fact_id in set(similar_facts):  # Use set to avoid duplicates
        knowledge_graph.remove_fact(fact_id)
    
    return len(similar_facts)


def clean_knowledge_graph(knowledge_graph, basic=True, advanced=True, semantic=True,
                         similarity_threshold=0.8, semantic_threshold=0.85,
                         short_fact_threshold=50, model_name="en_core_web_md"):
    """
    Perform comprehensive cleaning on a knowledge graph.
    
    This applies multiple cleaning methods in sequence.
    
    Args:
        knowledge_graph: KnowledgeGraph instance
        basic: Whether to perform basic deduplication
        advanced: Whether to perform advanced cleaning
        semantic: Whether to perform semantic cleaning
        similarity_threshold: Threshold for string similarity
        semantic_threshold: Threshold for semantic similarity
        short_fact_threshold: Minimum length for facts
        model_name: Name of the spaCy model to use
        
    Returns:
        dict: Statistics about the cleaning process
    """
    stats = {
        'initial_count': len(knowledge_graph.get_all_facts()),
        'duplicates_removed': 0,
        'short_removed': 0,
        'similar_removed': 0,
        'semantic_removed': 0
    }
    
    # Basic deduplication
    if basic:
        stats['duplicates_removed'] = remove_duplicate_facts(knowledge_graph)
    
    # Advanced cleaning
    if advanced:
        short_removed, similar_removed = advanced_cleaning(
            knowledge_graph,
            similarity_threshold=similarity_threshold,
            short_fact_threshold=short_fact_threshold
        )
        stats['short_removed'] = short_removed
        stats['similar_removed'] = similar_removed
    
    # Semantic cleaning
    if semantic:
        stats['semantic_removed'] = semantic_cleaning(
            knowledge_graph,
            similarity_threshold=semantic_threshold,
            model_name=model_name
        )
    
    # Calculate final count
    stats['final_count'] = len(knowledge_graph.get_all_facts())
    stats['total_removed'] = stats['initial_count'] - stats['final_count']
    
    return stats
