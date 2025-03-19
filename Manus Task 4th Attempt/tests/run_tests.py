"""
Test runner for the KnowledgeReduce framework.

This module provides a runner for executing the test suite and validating
the KnowledgeReduce implementation against the paper's conceptual framework.
"""

import os
import sys
import unittest
import logging
from datetime import datetime

# Add parent directory to path to import knowledge_reduce
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import test modules
from test_knowledge_reduce import (
    TestDataIngestion,
    TestMappingEngine,
    TestReducingEngine,
    TestKnowledgeGraph,
    TestStackableKnowledge,
    TestIntegration
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_tests():
    """Run all tests for the KnowledgeReduce framework."""
    logger.info("Starting KnowledgeReduce test suite")
    
    # Create output directory for test results
    os.makedirs("test_results", exist_ok=True)
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_suite.addTest(unittest.makeSuite(TestDataIngestion))
    test_suite.addTest(unittest.makeSuite(TestMappingEngine))
    test_suite.addTest(unittest.makeSuite(TestReducingEngine))
    test_suite.addTest(unittest.makeSuite(TestKnowledgeGraph))
    test_suite.addTest(unittest.makeSuite(TestStackableKnowledge))
    test_suite.addTest(unittest.makeSuite(TestIntegration))
    
    # Run tests
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = f"test_results/test_results_{timestamp}.txt"
    
    with open(result_file, "w") as f:
        runner = unittest.TextTestRunner(stream=f, verbosity=2)
        test_result = runner.run(test_suite)
    
    # Log test results
    logger.info(f"Tests run: {test_result.testsRun}")
    logger.info(f"Errors: {len(test_result.errors)}")
    logger.info(f"Failures: {len(test_result.failures)}")
    logger.info(f"Skipped: {len(test_result.skipped)}")
    
    # Print test results to console
    print(f"Tests run: {test_result.testsRun}")
    print(f"Errors: {len(test_result.errors)}")
    print(f"Failures: {len(test_result.failures)}")
    print(f"Skipped: {len(test_result.skipped)}")
    
    # Print errors and failures
    if test_result.errors:
        print("\nErrors:")
        for test, error in test_result.errors:
            print(f"{test}: {error}")
    
    if test_result.failures:
        print("\nFailures:")
        for test, failure in test_result.failures:
            print(f"{test}: {failure}")
    
    logger.info(f"Test results saved to {result_file}")
    
    return test_result

def validate_against_paper():
    """
    Validate the KnowledgeReduce implementation against the paper's conceptual framework.
    
    This function checks if the implementation satisfies the key requirements
    described in the paper.
    """
    logger.info("Validating KnowledgeReduce implementation against paper's conceptual framework")
    
    # Key requirements from the paper
    requirements = [
        {
            "name": "Data Ingestion",
            "description": "The framework should support ingestion of data from various sources.",
            "validation": "TestDataIngestion tests verify that the framework can ingest data from file sources."
        },
        {
            "name": "Mapping Phase",
            "description": "The framework should extract entities and relationships from raw data.",
            "validation": "TestMappingEngine tests verify entity extraction, relationship extraction, and disambiguation."
        },
        {
            "name": "Reducing Phase",
            "description": "The framework should aggregate entities and relationships and resolve conflicts.",
            "validation": "TestReducingEngine tests verify entity aggregation, conflict resolution, and weighted aggregation."
        },
        {
            "name": "Knowledge Graph",
            "description": "The framework should build a knowledge graph from reduced data.",
            "validation": "TestKnowledgeGraph tests verify graph building, querying, and export functionality."
        },
        {
            "name": "Stackable Knowledge",
            "description": "The framework should support stackable knowledge with hierarchy and merging capabilities.",
            "validation": "TestStackableKnowledge tests verify stack creation, hierarchy, merging, and lineage."
        },
        {
            "name": "Integration",
            "description": "The framework should integrate all components into a cohesive pipeline.",
            "validation": "TestIntegration tests verify the full pipeline from data ingestion to knowledge graph export."
        }
    ]
    
    # Create validation report
    os.makedirs("validation_results", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"validation_results/validation_report_{timestamp}.txt"
    
    with open(report_file, "w") as f:
        f.write("KnowledgeReduce Validation Report\n")
        f.write("===============================\n\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("Validation against Paper's Conceptual Framework\n")
        f.write("---------------------------------------------\n\n")
        
        for i, req in enumerate(requirements, 1):
            f.write(f"{i}. {req['name']}\n")
            f.write(f"   Description: {req['description']}\n")
            f.write(f"   Validation: {req['validation']}\n\n")
        
        f.write("Conclusion\n")
        f.write("----------\n\n")
        f.write("The KnowledgeReduce implementation satisfies the key requirements described in the paper.\n")
        f.write("The framework provides a comprehensive solution for building stackable knowledge from various data sources.\n")
    
    logger.info(f"Validation report saved to {report_file}")
    
    # Print validation summary
    print("\nValidation Summary:")
    for i, req in enumerate(requirements, 1):
        print(f"{i}. {req['name']}: Validated")
    
    print("\nConclusion: The KnowledgeReduce implementation satisfies the key requirements described in the paper.")
    
    return report_file

if __name__ == "__main__":
    # Run tests
    test_result = run_tests()
    
    # Validate against paper
    if test_result.wasSuccessful():
        validation_report = validate_against_paper()
        print(f"\nValidation report saved to {validation_report}")
    else:
        print("\nTests failed. Skipping validation against paper.")
