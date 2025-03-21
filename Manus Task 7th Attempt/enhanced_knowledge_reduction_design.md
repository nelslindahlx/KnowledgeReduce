# Enhanced Knowledge Reduction Design

## Current Limitations
The current implementation in CivicHonorsKGv18.ipynb has several limitations in knowledge reduction:
1. Uses basic string comparison with SequenceMatcher for similarity detection
2. Limited NLP capabilities with basic spaCy model
3. Simple thresholding approach for deduplication
4. No contextual understanding of content
5. Limited ability to handle large volumes of crawled data

## Enhanced Design

### 1. Advanced Text Similarity Methods

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
            from sentence_transformers import SentenceTransformer
            self.transformer = SentenceTransformer(transformer_model)
        
        # Similarity calculation methods
        self.similarity_methods = {
            "spacy": self._spacy_similarity,
            "tfidf": self._tfidf_similarity,
            "transformer": self._transformer_similarity,
            "hybrid": self._hybrid_similarity
        }
```

### 2. Multiple Similarity Calculation Methods

```python
def _spacy_similarity(self, text1, text2):
    """Calculate similarity using spaCy."""
    doc1 = self.nlp(text1)
    doc2 = self.nlp(text2)
    return doc1.similarity(doc2)

def _tfidf_similarity(self, texts):
    """Calculate TF-IDF similarity matrix for a list of texts."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    
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
    from sklearn.metrics.pairwise import cosine_similarity
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

### 3. Advanced Clustering for Knowledge Reduction

```python
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
    from sklearn.cluster import AgglomerativeClustering
    
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

### 4. Finding Central/Representative Facts

```python
def _find_central_fact(self, indices, similarity_matrix):
    """Find the most central fact in a cluster."""
    # Calculate centrality as the sum of similarities to other facts in the cluster
    centrality = {}
    for i in indices:
        centrality[i] = sum(similarity_matrix[i, j] for j in indices if i != j)
    
    # Return the fact with highest centrality
    return max(centrality.items(), key=lambda x: x[1])[0]
```

### 5. Entity-Based Knowledge Reduction

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

### 6. Multi-stage Knowledge Reduction Pipeline

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

## Integration with Knowledge Graph

The enhanced knowledge reduction will be integrated with the existing KnowledgeGraph class:

```python
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

This enhanced knowledge reduction design will significantly improve the notebook's ability to process and reduce knowledge from multiple webpages, resulting in higher quality and more diverse insights.
