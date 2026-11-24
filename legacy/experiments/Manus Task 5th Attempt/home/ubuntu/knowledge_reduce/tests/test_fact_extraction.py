#!/usr/bin/env python3
"""
Test script for the fact extraction module of KnowledgeReduce
"""

import os
import json
import sys
from knowledge_reduce.fact_extraction import FactExtractor

def main():
    """
    Main function to test the fact extraction module
    """
    # Create fact extractor
    fact_extractor = FactExtractor()
    
    # Define input and output paths
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output')
    
    # Process tech companies data
    tech_companies_file = os.path.join(data_dir, 'tech_companies.txt')
    output_file = os.path.join(output_dir, 'tech_companies_facts.json')
    
    print(f"Extracting facts from {tech_companies_file}...")
    facts = fact_extractor.extract_facts_from_file(tech_companies_file)
    
    # Save extracted facts
    fact_extractor.save_facts(facts, output_file)
    print(f"Facts saved to {output_file}")
    
    # Print summary
    print(f"\nExtracted {len(facts['nodes'])} entities and {len(facts['edges'])} relationships")
    
    # Print sample of entities
    print("\nSample entities:")
    for i, node in enumerate(facts['nodes'][:5]):
        print(f"  {i+1}. {node['text']} ({node['type']})")
    
    # Print sample of relationships
    print("\nSample relationships:")
    for i, edge in enumerate(facts['edges'][:5]):
        print(f"  {i+1}. {edge['source']} --[{edge['type']}]--> {edge['target']}")

if __name__ == "__main__":
    main()
