"""
Demonstration examples for the KnowledgeReduce framework.

This module provides examples of using the KnowledgeReduce framework
to build and manipulate stackable knowledge.
"""

import os
import json
import logging
import pandas as pd
from typing import Dict, List, Any

from knowledge_reduce import KnowledgeReduce
from knowledge_reduce.data_ingestion import FileConnector, APIConnector
from knowledge_reduce.mapping_engine.entity_extractors import SimpleEntityExtractor
from knowledge_reduce.mapping_engine.relationship_extractors import SimpleRelationshipExtractor
from knowledge_reduce.mapping_engine.disambiguation import SimpleDisambiguationEngine
from knowledge_reduce.reducing_engine.aggregators import SimpleAggregator
from knowledge_reduce.reducing_engine.conflict_resolvers import ConfidenceBasedResolver
from knowledge_reduce.knowledge_graph.stackable import StackableKnowledgeManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_sample_data():
    """
    Create sample data for demonstration.
    
    Returns:
        Dictionary containing sample data files.
    """
    logger.info("Creating sample data")
    
    # Create a directory for sample data
    os.makedirs("sample_data", exist_ok=True)
    
    # Sample data 1: Companies
    companies = [
        {"id": "comp1", "name": "TechCorp", "industry": "Technology", "founded": 1995},
        {"id": "comp2", "name": "FinBank", "industry": "Finance", "founded": 1980},
        {"id": "comp3", "name": "HealthCare Inc", "industry": "Healthcare", "founded": 2005},
        {"id": "comp4", "name": "EduLearn", "industry": "Education", "founded": 2010},
        {"id": "comp5", "name": "RetailMart", "industry": "Retail", "founded": 1970}
    ]
    
    with open("sample_data/companies.json", "w") as f:
        json.dump(companies, f, indent=2)
    
    # Sample data 2: People
    people = [
        {"id": "person1", "name": "John Smith", "age": 45, "company": "comp1", "position": "CEO"},
        {"id": "person2", "name": "Jane Doe", "age": 38, "company": "comp1", "position": "CTO"},
        {"id": "person3", "name": "Bob Johnson", "age": 52, "company": "comp2", "position": "CFO"},
        {"id": "person4", "name": "Alice Brown", "age": 35, "company": "comp3", "position": "Director"},
        {"id": "person5", "name": "Charlie Davis", "age": 41, "company": "comp4", "position": "Manager"},
        {"id": "person6", "name": "Eva Wilson", "age": 29, "company": "comp5", "position": "Analyst"}
    ]
    
    with open("sample_data/people.json", "w") as f:
        json.dump(people, f, indent=2)
    
    # Sample data 3: Products
    products = [
        {"id": "prod1", "name": "Smartphone X", "company": "comp1", "price": 999},
        {"id": "prod2", "name": "Laptop Pro", "company": "comp1", "price": 1499},
        {"id": "prod3", "name": "Credit Card Gold", "company": "comp2", "price": 0},
        {"id": "prod4", "name": "Health Monitor", "company": "comp3", "price": 299},
        {"id": "prod5", "name": "Online Course", "company": "comp4", "price": 99},
        {"id": "prod6", "name": "Retail Goods", "company": "comp5", "price": 49}
    ]
    
    with open("sample_data/products.json", "w") as f:
        json.dump(products, f, indent=2)
    
    # Sample data 4: Transactions
    transactions = [
        {"id": "trans1", "buyer": "person1", "product": "prod4", "date": "2023-01-15"},
        {"id": "trans2", "buyer": "person2", "product": "prod3", "date": "2023-02-20"},
        {"id": "trans3", "buyer": "person3", "product": "prod1", "date": "2023-03-10"},
        {"id": "trans4", "buyer": "person4", "product": "prod5", "date": "2023-04-05"},
        {"id": "trans5", "buyer": "person5", "product": "prod2", "date": "2023-05-12"},
        {"id": "trans6", "buyer": "person6", "product": "prod6", "date": "2023-06-18"}
    ]
    
    with open("sample_data/transactions.json", "w") as f:
        json.dump(transactions, f, indent=2)
    
    # Sample data 5: News articles
    news_articles = [
        {
            "id": "news1",
            "title": "TechCorp Launches New Smartphone",
            "content": "TechCorp has launched its latest Smartphone X, which is expected to compete with leading brands. CEO John Smith announced the product at their annual conference.",
            "date": "2023-01-10",
            "source": "Tech News"
        },
        {
            "id": "news2",
            "title": "FinBank Introduces New Credit Card",
            "content": "FinBank has introduced a new Credit Card Gold with attractive benefits. CFO Bob Johnson stated that this product aims to increase their market share.",
            "date": "2023-02-15",
            "source": "Finance Daily"
        },
        {
            "id": "news3",
            "title": "HealthCare Inc Partners with EduLearn",
            "content": "HealthCare Inc and EduLearn have announced a partnership to develop health education programs. Director Alice Brown from HealthCare and Manager Charlie Davis from EduLearn will lead the initiative.",
            "date": "2023-03-20",
            "source": "Health News"
        }
    ]
    
    with open("sample_data/news_articles.json", "w") as f:
        json.dump(news_articles, f, indent=2)
    
    logger.info("Sample data created")
    
    return {
        "companies": "sample_data/companies.json",
        "people": "sample_data/people.json",
        "products": "sample_data/products.json",
        "transactions": "sample_data/transactions.json",
        "news_articles": "sample_data/news_articles.json"
    }

def basic_knowledge_reduce_example(sample_data_files):
    """
    Basic example of using KnowledgeReduce.
    
    Args:
        sample_data_files: Dictionary containing sample data files.
    """
    logger.info("Running basic KnowledgeReduce example")
    
    # Initialize KnowledgeReduce
    kr = KnowledgeReduce()
    
    # Configure data ingestion
    companies_connector = FileConnector(sample_data_files["companies"], "json")
    people_connector = FileConnector(sample_data_files["people"], "json")
    
    kr.register_data_source("companies", companies_connector)
    kr.register_data_source("people", people_connector)
    
    # Configure mapping engine
    entity_extractor = SimpleEntityExtractor()
    relationship_extractor = SimpleRelationshipExtractor()
    disambiguation_engine = SimpleDisambiguationEngine()
    
    kr.register_entity_extractor(entity_extractor)
    kr.register_relationship_extractor(relationship_extractor)
    kr.set_disambiguation_engine(disambiguation_engine)
    
    # Configure reducing engine
    aggregator = SimpleAggregator()
    conflict_resolver = ConfidenceBasedResolver()
    
    kr.register_aggregator(aggregator)
    kr.register_conflict_resolver(conflict_resolver)
    
    # Process data
    kr.ingest_data()
    mapped_data = kr.map_data()
    reduced_data = kr.reduce_data(mapped_data)
    
    # Build knowledge graph
    kr.build_knowledge_graph(reduced_data)
    
    # Export knowledge graph
    kr.export_knowledge_graph("output/basic_example_graph.json", "json")
    
    logger.info("Basic KnowledgeReduce example completed")

def stackable_knowledge_example(sample_data_files):
    """
    Example of using stackable knowledge in KnowledgeReduce.
    
    Args:
        sample_data_files: Dictionary containing sample data files.
    """
    logger.info("Running stackable knowledge example")
    
    # Initialize KnowledgeReduce
    kr = KnowledgeReduce()
    
    # Configure data ingestion
    companies_connector = FileConnector(sample_data_files["companies"], "json")
    people_connector = FileConnector(sample_data_files["people"], "json")
    products_connector = FileConnector(sample_data_files["products"], "json")
    transactions_connector = FileConnector(sample_data_files["transactions"], "json")
    news_connector = FileConnector(sample_data_files["news_articles"], "json")
    
    kr.register_data_source("companies", companies_connector)
    kr.register_data_source("people", people_connector)
    kr.register_data_source("products", products_connector)
    kr.register_data_source("transactions", transactions_connector)
    kr.register_data_source("news", news_connector)
    
    # Configure mapping engine
    entity_extractor = SimpleEntityExtractor()
    relationship_extractor = SimpleRelationshipExtractor()
    disambiguation_engine = SimpleDisambiguationEngine()
    
    kr.register_entity_extractor(entity_extractor)
    kr.register_relationship_extractor(relationship_extractor)
    kr.set_disambiguation_engine(disambiguation_engine)
    
    # Configure reducing engine
    aggregator = SimpleAggregator()
    conflict_resolver = ConfidenceBasedResolver()
    
    kr.register_aggregator(aggregator)
    kr.register_conflict_resolver(conflict_resolver)
    
    # Initialize stackable knowledge manager
    stack_manager = StackableKnowledgeManager()
    
    # Create knowledge stacks
    stack_manager.create_stack("companies_stack", "Stack for company data")
    stack_manager.create_stack("people_stack", "Stack for people data")
    stack_manager.create_stack("products_stack", "Stack for product data")
    stack_manager.create_stack("transactions_stack", "Stack for transaction data")
    stack_manager.create_stack("news_stack", "Stack for news data")
    
    # Process company data
    stack_manager.set_current_stack("companies_stack")
    kr.ingest_data(["companies"])
    mapped_data = kr.map_data()
    reduced_data = kr.reduce_data(mapped_data)
    kr.build_knowledge_graph(reduced_data)
    stack_manager.add_to_current_stack(reduced_data["entities"], reduced_data["relationships"])
    
    # Process people data
    stack_manager.set_current_stack("people_stack")
    kr.ingest_data(["people"])
    mapped_data = kr.map_data()
    reduced_data = kr.reduce_data(mapped_data)
    kr.build_knowledge_graph(reduced_data)
    stack_manager.add_to_current_stack(reduced_data["entities"], reduced_data["relationships"])
    
    # Process product data
    stack_manager.set_current_stack("products_stack")
    kr.ingest_data(["products"])
    mapped_data = kr.map_data()
    reduced_data = kr.reduce_data(mapped_data)
    kr.build_knowledge_graph(reduced_data)
    stack_manager.add_to_current_stack(reduced_data["entities"], reduced_data["relationships"])
    
    # Process transaction data
    stack_manager.set_current_stack("transactions_stack")
    kr.ingest_data(["transactions"])
    mapped_data = kr.map_data()
    reduced_data = kr.reduce_data(mapped_data)
    kr.build_knowledge_graph(reduced_data)
    stack_manager.add_to_current_stack(reduced_data["entities"], reduced_data["relationships"])
    
    # Process news data
    stack_manager.set_current_stack("news_stack")
    kr.ingest_data(["news"])
    mapped_data = kr.map_data()
    reduced_data = kr.reduce_data(mapped_data)
    kr.build_knowledge_graph(reduced_data)
    stack_manager.add_to_current_stack(reduced_data["entities"], reduced_data["relationships"])
    
    # Create stack hierarchies
    stack_manager.create_stack_hierarchy("companies_stack", "products_stack")
    stack_manager.create_stack_hierarchy("people_stack", "transactions_stack")
    
    # Merge stacks
    stack_manager.merge_stacks(["companies_stack", "people_stack"], "organization_stack", "union")
    stack_manager.merge_stacks(["products_stack", "transactions_stack"], "commerce_stack", "union")
    
    # Create a comprehensive stack
    stack_manager.merge_stacks(["organization_stack", "commerce_stack", "news_stack"], "comprehensive_stack", "union")
    
    # Visualize stack hierarchy
    os.makedirs("output", exist_ok=True)
    stack_manager.visualize_stack_hierarchy("output/stack_hierarchy.png")
    
    # Save stack manager state
    stack_manager.save_state("output/stack_manager_state")
    
    logger.info("Stackable knowledge example completed")

def incremental_knowledge_building_example(sample_data_files):
    """
    Example of incremental knowledge building in KnowledgeReduce.
    
    Args:
        sample_data_files: Dictionary containing sample data files.
    """
    logger.info("Running incremental knowledge building example")
    
    # Initialize KnowledgeReduce
    kr = KnowledgeReduce()
    
    # Configure data ingestion
    companies_connector = FileConnector(sample_data_files["companies"], "json")
    people_connector = FileConnector(sample_data_files["people"], "json")
    products_connector = FileConnector(sample_data_files["products"], "json")
    
    kr.register_data_source("companies", companies_connector)
    kr.register_data_source("people", people_connector)
    kr.register_data_source("products", products_connector)
    
    # Configure mapping engine
    entity_extractor = SimpleEntityExtractor()
    relationship_extractor = SimpleRelationshipExtractor()
    disambiguation_engine = SimpleDisambiguationEngine()
    
    kr.register_entity_extractor(entity_extractor)
    kr.register_relationship_extractor(relationship_extractor)
    kr.set_disambiguation_engine(disambiguation_engine)
    
    # Configure reducing engine
    aggregator = SimpleAggregator()
    conflict_resolver = ConfidenceBasedResolver()
    
    kr.register_aggregator(aggregator)
    kr.register_conflict_resolver(conflict_resolver)
    
    # Initialize stackable knowledge manager
    stack_manager = StackableKnowledgeManager()
    
    # Phase 1: Process company data
    logger.info("Phase 1: Processing company data")
    stack_manager.create_stack("phase1_stack", "Initial knowledge about companies")
    stack_manager.set_current_stack("phase1_stack")
    
    kr.ingest_data(["companies"])
    mapped_data = kr.map_data()
    reduced_data = kr.reduce_data(mapped_data)
    kr.build_knowledge_graph(reduced_data)
    
    stack_manager.add_to_current_stack(reduced_data["entities"], reduced_data["relationships"])
    
    # Export phase 1 knowledge graph
    kr.export_knowledge_graph("output/phase1_graph.json", "json")
    
    # Phase 2: Add people data
    logger.info("Phase 2: Adding people data")
    stack_manager.create_stack("phase2_stack", "Knowledge with people added")
    stack_manager.set_current_stack("phase2_stack")
    
    kr.ingest_data(["people"])
    mapped_data = kr.map_data()
    reduced_data = kr.reduce_data(mapped_data)
    kr.build_knowledge_graph(reduced_data)
    
    stack_manager.add_to_current_stack(reduced_data["entities"], reduced_data["relationships"])
    
    # Create hierarchy between phases
    stack_manager.create_stack_hierarchy("phase1_stack", "phase2_stack")
    
    # Export phase 2 knowledge graph
    kr.export_knowledge_graph("output/phase2_graph.json", "json")
    
    # Phase 3: Add product data
    logger.info("Phase 3: Adding product data")
    stack_manager.create_stack("phase3_stack", "Knowledge with products added")
    stack_manager.set_current_stack("phase3_stack")
    
    kr.ingest_data(["products"])
    mapped_data = kr.map_data()
    reduced_data = kr.reduce_data(mapped_data)
    kr.build_knowledge_graph(reduced_data)
    
    stack_manager.add_to_current_stack(reduced_data["entities"], reduced_data["relationships"])
    
    # Create hierarchy between phases
    stack_manager.create_stack_hierarchy("phase2_stack", "phase3_stack")
    
    # Export phase 3 knowledge graph
    kr.export_knowledge_graph("output/phase3_graph.json", "json")
    
    # Get combined knowledge from all phases
    combined_stack = stack_manager.get_combined_stack("phase3_stack", include_ancestors=True)
    
    # Visualize stack hierarchy
    stack_manager.visualize_stack_hierarchy("output/incremental_stack_hierarchy.png")
    
    logger.info("Incremental knowledge building example completed")

def knowledge_integration_example(sample_data_files):
    """
    Example of knowledge integration in KnowledgeReduce.
    
    Args:
        sample_data_files: Dictionary containing sample data files.
    """
    logger.info("Running knowledge integration example")
    
    # Initialize KnowledgeReduce
    kr = KnowledgeReduce()
    
    # Configure data ingestion
    companies_connector = FileConnector(sample_data_files["companies"], "json")
    news_connector = FileConnector(sample_data_files["news_articles"], "json")
    
    kr.register_data_source("companies", companies_connector)
    kr.register_data_source("news", news_connector)
    
    # Configure mapping engine
    entity_extractor = SimpleEntityExtractor()
    relationship_extractor = SimpleRelationshipExtractor()
    disambiguation_engine = SimpleDisambiguationEngine()
    
    kr.register_entity_extractor(entity_extractor)
    kr.register_relationship_extractor(relationship_extractor)
    kr.set_disambiguation_engine(disambiguation_engine)
    
    # Configure reducing engine
    aggregator = SimpleAggregator()
    conflict_resolver = ConfidenceBasedResolver()
    
    kr.register_aggregator(aggregator)
    kr.register_conflict_resolver(conflict_resolver)
    
    # Initialize stackable knowledge manager
    stack_manager = StackableKnowledgeManager()
    
    # Create knowledge stacks
    stack_manager.create_stack("factual_stack", "Stack for factual company data")
    stack_manager.create_stack("news_stack", "Stack for news data")
    
    # Process factual data
    stack_manager.set_current_stack("factual_stack")
    kr.ingest_data(["companies"])
    mapped_data = kr.map_data()
    reduced_data = kr.reduce_data(mapped_data)
    kr.build_knowledge_graph(reduced_data)
    stack_manager.add_to_current_stack(reduced_data["entities"], reduced_data["relationships"])
    
    # Process news data
    stack_manager.set_current_stack("news_stack")
    kr.ingest_data(["news"])
    mapped_data = kr.map_data()
    reduced_data = kr.reduce_data(mapped_data)
    kr.build_knowledge_graph(reduced_data)
    stack_manager.add_to_current_stack(reduced_data["entities"], reduced_data["relationships"])
    
    # Integrate knowledge
    stack_manager.merge_stacks(["factual_stack", "news_stack"], "integrated_stack", "union")
    
    # Export integrated knowledge graph
    kr.export_knowledge_graph("output/integrated_graph.json", "json")
    
    # Visualize stack hierarchy
    stack_manager.visualize_stack_hierarchy("output/integration_stack_hierarchy.png")
    
    logger.info("Knowledge integration example completed")

def run_all_examples():
    """
    Run all demonstration examples.
    """
    logger.info("Running all demonstration examples")
    
    # Create output directory
    os.makedirs("output", exist_ok=True)
    
    # Create sample data
    sample_data_files = create_sample_data()
    
    # Run examples
    basic_knowledge_reduce_example(sample_data_files)
    stackable_knowledge_example(sample_data_files)
    incremental_knowledge_building_example(sample_data_files)
    knowledge_integration_example(sample_data_files)
    
    logger.info("All demonstration examples completed")

if __name__ == "__main__":
    run_all_examples()
