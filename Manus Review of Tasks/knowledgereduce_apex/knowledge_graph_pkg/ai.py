"""
Advanced AI integration for knowledge graphs with LLM capabilities.

This module provides integration with large language models for
knowledge extraction, reasoning, and natural language interfaces.
"""

import json
import re
import time
from typing import Dict, List, Any, Union, Optional, Tuple, Set, Callable
from datetime import datetime
from .core import KnowledgeGraph, ReliabilityRating

class AIKnowledgeGraph:
    """
    Class for AI-enhanced knowledge graph operations.
    
    This class provides methods for integrating large language models
    with knowledge graphs for advanced capabilities.
    
    Attributes:
        kg: The knowledge graph to enhance with AI capabilities
        model_name: Name of the LLM model to use
        context_window: Maximum context window size for the model
    """
    
    def __init__(self, knowledge_graph: KnowledgeGraph, model_name: str = "gpt-4", context_window: int = 8192):
        """
        Initialize an AIKnowledgeGraph with a knowledge graph.
        
        Args:
            knowledge_graph: KnowledgeGraph instance to enhance
            model_name: Name of the LLM model to use
            context_window: Maximum context window size for the model
        """
        self.kg = knowledge_graph
        self.model_name = model_name
        self.context_window = context_window
        self.reasoning_cache = {}
        
    def extract_knowledge_from_text(self, text: str, source_id: str, reliability: ReliabilityRating = ReliabilityRating.POSSIBLY_TRUE) -> List[str]:
        """
        Extract knowledge from text using LLM capabilities.
        
        Args:
            text: Text to extract knowledge from
            source_id: Source identifier
            reliability: Reliability rating for extracted facts
            
        Returns:
            List of fact IDs created from the text
        """
        # In a real implementation, this would use an actual LLM API
        # This is a simplified mock implementation
        
        # Mock extraction of facts from text
        facts = self._mock_extract_facts(text)
        
        # Add facts to knowledge graph
        fact_ids = []
        
        for i, fact in enumerate(facts):
            fact_id = f"ai_fact_{int(time.time())}_{i}"
            
            # Add the fact to the knowledge graph
            try:
                self.kg.add_fact(
                    fact_id=fact_id,
                    fact_statement=fact['statement'],
                    category=fact['category'],
                    tags=fact['tags'],
                    date_recorded=datetime.now(),
                    last_updated=datetime.now(),
                    reliability_rating=reliability,
                    source_id=source_id,
                    source_title=fact.get('source_title', ''),
                    author_creator=fact.get('author_creator', 'AI Extraction'),
                    publication_date=datetime.now(),
                    url_reference=fact.get('url_reference', ''),
                    related_facts=[],
                    contextual_notes=f"Extracted from text using AI: {text[:100]}...",
                    access_level="public",
                    usage_count=0
                )
                fact_ids.append(fact_id)
            except Exception as e:
                print(f"Error adding extracted fact: {e}")
                
        return fact_ids
        
    def answer_question(self, question: str, max_facts: int = 10) -> Dict[str, Any]:
        """
        Answer a question using the knowledge graph and LLM reasoning.
        
        Args:
            question: Question to answer
            max_facts: Maximum number of facts to include in context
            
        Returns:
            Dictionary with answer and supporting facts
        """
        # Find relevant facts
        relevant_facts = self._find_relevant_facts(question, max_facts)
        
        # Format facts for context
        context = self._format_facts_for_context(relevant_facts)
        
        # Generate answer using LLM (mock implementation)
        answer = self._mock_generate_answer(question, context)
        
        return {
            'question': question,
            'answer': answer,
            'supporting_facts': [self.kg.get_fact(fact_id)['fact_statement'] for fact_id in relevant_facts],
            'fact_ids': relevant_facts
        }
        
    def generate_hypotheses(self, topic: str, num_hypotheses: int = 3) -> List[Dict[str, Any]]:
        """
        Generate hypotheses based on the knowledge graph.
        
        Args:
            topic: Topic to generate hypotheses about
            num_hypotheses: Number of hypotheses to generate
            
        Returns:
            List of generated hypotheses
        """
        # Find facts related to the topic
        related_facts = self._find_facts_by_topic(topic, max_facts=15)
        
        # Format facts for context
        context = self._format_facts_for_context(related_facts)
        
        # Generate hypotheses using LLM (mock implementation)
        hypotheses = self._mock_generate_hypotheses(topic, context, num_hypotheses)
        
        return hypotheses
        
    def explain_reasoning(self, fact_id: str) -> Dict[str, Any]:
        """
        Explain the reasoning behind a fact using LLM capabilities.
        
        Args:
            fact_id: ID of the fact to explain
            
        Returns:
            Dictionary with explanation and supporting information
        """
        # Check cache
        if fact_id in self.reasoning_cache:
            return self.reasoning_cache[fact_id]
            
        # Get the fact
        try:
            fact = self.kg.get_fact(fact_id)
        except Exception as e:
            return {
                'fact_id': fact_id,
                'error': f"Fact not found: {e}"
            }
            
        # Find related facts
        related_fact_ids = fact.get('related_facts', [])
        related_facts = []
        
        for related_id in related_fact_ids:
            try:
                related_facts.append(self.kg.get_fact(related_id))
            except Exception:
                pass
                
        # Generate explanation using LLM (mock implementation)
        explanation = self._mock_generate_explanation(fact, related_facts)
        
        # Create result
        result = {
            'fact_id': fact_id,
            'fact_statement': fact['fact_statement'],
            'explanation': explanation,
            'supporting_facts': [f['fact_statement'] for f in related_facts],
            'confidence': self._calculate_confidence(fact)
        }
        
        # Cache the result
        self.reasoning_cache[fact_id] = result
        
        return result
        
    def generate_natural_language_query(self, structured_query: Dict[str, Any]) -> str:
        """
        Generate a natural language query from a structured query.
        
        Args:
            structured_query: Structured query parameters
            
        Returns:
            Natural language query
        """
        # Mock implementation
        query_parts = []
        
        if 'category' in structured_query:
            query_parts.append(f"in the category of {structured_query['category']}")
            
        if 'tags' in structured_query:
            tags = structured_query['tags']
            if len(tags) == 1:
                query_parts.append(f"with the tag {tags[0]}")
            else:
                query_parts.append(f"with tags {', '.join(tags[:-1])} and {tags[-1]}")
                
        if 'min_reliability' in structured_query:
            reliability = structured_query['min_reliability']
            if isinstance(reliability, ReliabilityRating):
                reliability = reliability.name
            query_parts.append(f"that are at least {reliability.replace('_', ' ').lower()}")
            
        if 'keywords' in structured_query:
            query_parts.append(f"containing {structured_query['keywords']}")
            
        if query_parts:
            return f"Find facts {' '.join(query_parts)}"
        else:
            return "Find all facts in the knowledge graph"
            
    def parse_natural_language_query(self, nl_query: str) -> Dict[str, Any]:
        """
        Parse a natural language query into a structured query.
        
        Args:
            nl_query: Natural language query
            
        Returns:
            Structured query parameters
        """
        # In a real implementation, this would use an actual LLM API
        # This is a simplified mock implementation
        
        query = {}
        
        # Look for category
        category_match = re.search(r'category (?:of|is|in) (\w+)', nl_query, re.IGNORECASE)
        if category_match:
            query['category'] = category_match.group(1)
            
        # Look for tags
        tags_match = re.search(r'tags? (?:is|are|include|including) ([\w\s,]+)', nl_query, re.IGNORECASE)
        if tags_match:
            tags_str = tags_match.group(1)
            query['tags'] = [tag.strip() for tag in re.split(r',|\sand\s', tags_str)]
            
        # Look for reliability
        reliability_match = re.search(r'(verified|likely true|possibly true|unverified)', nl_query, re.IGNORECASE)
        if reliability_match:
            reliability_str = reliability_match.group(1).upper().replace(' ', '_')
            query['min_reliability'] = getattr(ReliabilityRating, reliability_str)
            
        # Extract keywords (simplified)
        keywords = []
        for word in re.findall(r'\b\w+\b', nl_query):
            if len(word) > 3 and word.lower() not in ['find', 'facts', 'with', 'that', 'are', 'category', 'tags', 'and', 'the']:
                keywords.append(word)
                
        if keywords:
            query['keywords'] = ' '.join(keywords)
            
        return query
        
    def _find_relevant_facts(self, question: str, max_facts: int) -> List[str]:
        """
        Find facts relevant to a question.
        
        Args:
            question: Question to find facts for
            max_facts: Maximum number of facts to return
            
        Returns:
            List of relevant fact IDs
        """
        # Extract keywords from the question
        keywords = self._extract_keywords(question)
        
        # Score facts based on relevance to keywords
        fact_scores = {}
        
        for node, data in self.kg.graph.nodes(data=True):
            if 'fact_statement' in data:
                score = 0
                
                # Score based on fact statement
                for keyword in keywords:
                    if keyword.lower() in data['fact_statement'].lower():
                        score += 1
                        
                # Score based on tags
                if 'tags' in data:
                    for tag in data['tags']:
                        if tag.lower() in keywords:
                            score += 0.5
                            
                # Score based on category
                if 'category' in data and data['category'].lower() in keywords:
                    score += 0.5
                    
                # Add reliability bonus
                if 'reliability_rating' in data:
                    reliability = data['reliability_rating']
                    if isinstance(reliability, str):
                        reliability = getattr(ReliabilityRating, reliability)
                    score += reliability.value * 0.1
                    
                if score > 0:
                    fact_scores[node] = score
                    
        # Sort facts by score
        sorted_facts = sorted(fact_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Return top facts
        return [fact_id for fact_id, _ in sorted_facts[:max_facts]]
        
    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract keywords from text.
        
        Args:
            text: Text to extract keywords from
            
        Returns:
            List of keywords
        """
        # Simple keyword extraction (in a real implementation, use NLP techniques)
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Filter out common stop words
        stop_words = {'the', 'a', 'an', 'in', 'on', 'at', 'is', 'are', 'was', 'were', 'be', 'to', 'of', 'and', 'or', 'for', 'with', 'by', 'about', 'like', 'that', 'this', 'these', 'those'}
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        return keywords
        
    def _format_facts_for_context(self, fact_ids: List[str]) -> str:
        """
        Format facts for use as context in LLM prompts.
        
        Args:
            fact_ids: List of fact IDs to format
            
        Returns:
            Formatted context string
        """
        context_parts = []
        
        for i, fact_id in enumerate(fact_ids):
            try:
                fact = self.kg.get_fact(fact_id)
                context_parts.append(f"Fact {i+1}: {fact['fact_statement']}")
                
                # Add reliability information
                reliability = fact.get('reliability_rating', ReliabilityRating.UNVERIFIED)
                if isinstance(reliability, str):
                    reliability_str = reliability
                else:
                    reliability_str = reliability.name
                context_parts.append(f"Reliability: {reliability_str.replace('_', ' ').title()}")
                
                # Add source information if available
                if 'source_title' in fact and fact['source_title']:
                    context_parts.append(f"Source: {fact['source_title']}")
                    
                # Add separator
                context_parts.append("")
            except Exception as e:
                print(f"Error formatting fact {fact_id}: {e}")
                
        return "\n".join(context_parts)
        
    def _find_facts_by_topic(self, topic: str, max_facts: int) -> List[str]:
        """
        Find facts related to a topic.
        
        Args:
            topic: Topic to find facts for
            max_facts: Maximum number of facts to return
            
        Returns:
            List of relevant fact IDs
        """
        # Similar to _find_relevant_facts but focused on a topic
        keywords = [topic] + self._extract_keywords(topic)
        
        # Score facts based on relevance to topic
        fact_scores = {}
        
        for node, data in self.kg.graph.nodes(data=True):
            if 'fact_statement' in data:
                score = 0
                
                # Score based on fact statement
                for keyword in keywords:
                    if keyword.lower() in data['fact_statement'].lower():
                        score += 1
                        
                # Score based on tags
                if 'tags' in data:
                    for tag in data['tags']:
                        if tag.lower() in keywords or topic.lower() in tag.lower():
                            score += 0.5
                            
                # Score based on category
                if 'category' in data and (data['category'].lower() in keywords or topic.lower() in data['category'].lower()):
                    score += 0.5
                    
                if score > 0:
                    fact_scores[node] = score
                    
        # Sort facts by score
        sorted_facts = sorted(fact_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Return top facts
        return [fact_id for fact_id, _ in sorted_facts[:max_facts]]
        
    def _calculate_confidence(self, fact: Dict[str, Any]) -> float:
        """
        Calculate confidence score for a fact.
        
        Args:
            fact: Fact to calculate confidence for
            
        Returns:
            Confidence score between 0 and 1
        """
        # Base confidence on reliability rating
        reliability = fact.get('reliability_rating', ReliabilityRating.UNVERIFIED)
        if isinstance(reliability, str):
            reliability = getattr(ReliabilityRating, reliability)
            
        base_confidence = reliability.value / 4.0  # Normalize to 0-1
        
        # Adjust based on other factors
        adjustments = 0
        
        # Source factors
        if fact.get('source_title'):
            adjustments += 0.05
        if fact.get('author_creator'):
            adjustments += 0.05
        if fact.get('url_reference'):
            adjustments += 0.05
            
        # Usage factors
        usage_count = fact.get('usage_count', 0)
        if usage_count > 0:
            adjustments += min(0.1, usage_count / 100)
            
        # Related facts
        related_facts = fact.get('related_facts', [])
        if related_facts:
            adjustments += min(0.1, len(related_facts) / 10)
            
        # Calculate final confidence
        confidence = base_confidence + adjustments
        
        # Ensure confidence is between 0 and 1
        return max(0, min(1, confidence))
        
    def _mock_extract_facts(self, text: str) -> List[Dict[str, Any]]:
        """
        Mock implementation of fact extraction from text.
        
        Args:
            text: Text to extract facts from
            
        Returns:
            List of extracted facts
        """
        # This is a simplified mock implementation
        # In a real implementation, this would use an actual LLM API
        
        # Simple pattern matching to extract potential facts
        facts = []
        
        # Look for sentences that might be facts
        sentences = re.split(r'[.!?]', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 10:  # Ignore very short sentences
                # Determine a category based on keywords
                category = "General"
                
                if any(word in sentence.lower() for word in ['planet', 'star', 'moon', 'orbit', 'galaxy', 'solar']):
                    category = "Astronomy"
                elif any(word in sentence.lower() for word in ['animal', 'species', 'plant', 'cell', 'organism']):
                    category = "Biology"
                elif any(word in sentence.lower() for word in ['country', 'city', 'capital', 'population', 'president']):
                    category = "Geography"
                elif any(word in sentence.lower() for word in ['history', 'war', 'century', 'ancient', 'king', 'queen']):
                    category = "History"
                    
                # Extract potential tags
                words = re.findall(r'\b\w+\b', sentence.lower())
                stop_words = {'the', 'a', 'an', 'in', 'on', 'at', 'is', 'are', 'was', 'were', 'be', 'to', 'of', 'and', 'or', 'for', 'with', 'by', 'about', 'like', 'that', 'this', 'these', 'those'}
                potential_tags = [word for word in words if word not in stop_words and len(word) > 3]
                
                # Select up to 5 tags
                tags = potential_tags[:5]
                
                facts.append({
                    'statement': sentence,
                    'category': category,
                    'tags': tags
                })
                
        return facts
        
    def _mock_generate_answer(self, question: str, context: str) -> str:
        """
        Mock implementation of answer generation.
        
        Args:
            question: Question to answer
            context: Context with relevant facts
            
        Returns:
            Generated answer
        """
        # This is a simplified mock implementation
        # In a real implementation, this would use an actual LLM API
        
        # Check if we have any context
        if not context:
            return "I don't have enough information to answer that question."
            
        # Extract fact statements from context
        fact_statements = re.findall(r'Fact \d+: (.*)', context)
        
        if not fact_statements:
            return "I don't have enough information to answer that question."
            
        # Simple answer generation based on available facts
        if "what" in question.lower():
            return f"Based on the available information, {fact_statements[0].lower()}"
        elif "how" in question.lower():
            return f"According to the facts, {fact_statements[0].lower()}"
        elif "why" in question.lower():
            if len(fact_statements) > 1:
                return f"This is because {fact_statements[1].lower()}"
            else:
                return f"Based on the available information, {fact_statements[0].lower()}"
        elif "when" in question.lower():
            time_related = next((fact for fact in fact_statements if any(word in fact.lower() for word in ['year', 'century', 'decade', 'date', 'time', 'period'])), None)
            if time_related:
                return f"It happened when {time_related.lower()}"
            else:
                return f"The timing is not specified in the available information, but {fact_statements[0].lower()}"
        else:
            return f"Based on the available facts, {fact_statements[0].lower()}"
            
    def _mock_generate_hypotheses(self, topic: str, context: str, num_hypotheses: int) -> List[Dict[str, Any]]:
        """
        Mock implementation of hypothesis generation.
        
        Args:
            topic: Topic to generate hypotheses about
            context: Context with relevant facts
            num_hypotheses: Number of hypotheses to generate
            
        Returns:
            List of generated hypotheses
        """
        # This is a simplified mock implementation
        # In a real implementation, this would use an actual LLM API
        
        # Extract fact statements from context
        fact_statements = re.findall(r'Fact \d+: (.*)', context)
        
        if not fact_statements:
            return [{
                'hypothesis': f"There might be a relationship between {topic} and other phenomena",
                'confidence': 0.3,
                'supporting_facts': [],
                'potential_tests': ["Gather more data about " + topic]
            }]
            
        hypotheses = []
        
        for i in range(min(num_hypotheses, len(fact_statements))):
            fact = fact_statements[i]
            
            # Generate a hypothesis based on the fact
            hypothesis = f"If {fact.lower()}, then it's possible that {topic} could be affected by or related to this phenomenon."
            
            # Generate potential tests
            tests = [
                f"Investigate the relationship between {topic} and {self._extract_keywords(fact)[0] if self._extract_keywords(fact) else 'related factors'}",
                f"Collect more data about how {topic} interacts with other elements in the system"
            ]
            
            hypotheses.append({
                'hypothesis': hypothesis,
                'confidence': 0.5 + (0.1 * i),  # Decreasing confidence for later hypotheses
                'supporting_facts': [fact],
                'potential_tests': tests
            })
            
        return hypotheses
        
    def _mock_generate_explanation(self, fact: Dict[str, Any], related_facts: List[Dict[str, Any]]) -> str:
        """
        Mock implementation of explanation generation.
        
        Args:
            fact: Fact to explain
            related_facts: Related facts for context
            
        Returns:
            Generated explanation
        """
        # This is a simplified mock implementation
        # In a real implementation, this would use an actual LLM API
        
        fact_statement = fact['fact_statement']
        
        # Basic explanation
        explanation = f"This fact states that {fact_statement.lower()}. "
        
        # Add reliability information
        reliability = fact.get('reliability_rating', ReliabilityRating.UNVERIFIED)
        if isinstance(reliability, str):
            reliability_str = reliability
        else:
            reliability_str = reliability.name
            
        explanation += f"It has been rated as {reliability_str.replace('_', ' ').lower()}. "
        
        # Add source information
        if fact.get('source_title'):
            explanation += f"The information comes from {fact.get('source_title')}. "
            
        if fact.get('author_creator'):
            explanation += f"It was provided by {fact.get('author_creator')}. "
            
        # Add related facts
        if related_facts:
            explanation += "This fact is related to other facts in the knowledge graph: "
            for i, related in enumerate(related_facts[:3]):  # Limit to 3 related facts
                explanation += f"{related['fact_statement']}. "
                
        return explanation
