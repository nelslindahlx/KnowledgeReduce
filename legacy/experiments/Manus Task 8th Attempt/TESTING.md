# KnowledgeReduce Testing Documentation

This document provides an overview of the testing approach for the KnowledgeReduce project, including test organization, coverage goals, and how to run tests.

## Testing Philosophy

The KnowledgeReduce project follows a test-driven development approach with these key principles:

1. **Comprehensive Coverage**: Aim for at least 80% code coverage across all modules
2. **Test Pyramid**: Focus on unit tests as the foundation, with integration tests for component interactions
3. **Property-Based Testing**: Use parameterized tests to verify behavior across different inputs
4. **Continuous Integration**: Automatically run tests on all code changes via GitHub Actions

## Test Organization

Tests are organized into the following structure:

```
knowledge_graph_pkg/
└── tests/
    ├── unit/             # Unit tests for individual components
    │   ├── test_core.py  # Tests for core.py functionality
    │   └── ...
    ├── integration/      # Tests for component interactions
    │   └── ...
    └── __init__.py       # Test package initialization
```

## Running Tests

### Prerequisites

- Python 3.8+
- pytest
- pytest-cov

### Basic Test Execution

To run all tests:

```bash
cd KnowledgeReduce
pytest knowledge_graph_pkg/tests/
```

### Running with Coverage

To run tests with coverage reporting:

```bash
pytest knowledge_graph_pkg/tests/ --cov=knowledge_graph_pkg --cov-report=term --cov-report=html
```

This will generate a terminal report and an HTML report in the `htmlcov` directory.

## Test Types

### Unit Tests

Unit tests focus on testing individual components in isolation. Each class and function should have corresponding unit tests that verify:

- Normal operation with valid inputs
- Error handling with invalid inputs
- Edge cases and boundary conditions

### Property-Based Tests

Property-based tests verify that certain properties hold true across a range of inputs. For example:

- Quality score increases with higher reliability ratings
- Quality score increases with higher usage counts

### Integration Tests

Integration tests verify that components work together correctly. These tests focus on:

- Data flow between components
- End-to-end functionality
- API contracts

## Continuous Integration

The project uses GitHub Actions for continuous integration. The CI pipeline:

1. Runs on all pushes to the main branch and pull requests
2. Tests against multiple Python versions (3.8, 3.9, 3.10)
3. Generates coverage reports
4. Performs code quality checks (linting, formatting, type checking)

## Coverage Goals

The project aims for at least 80% code coverage, with higher coverage for critical components:

- Core knowledge graph functionality: 90%+
- API and public interfaces: 100%
- Utility functions: 80%+

## Writing New Tests

When adding new functionality, follow these guidelines:

1. Write tests before or alongside the implementation
2. Ensure tests are independent and don't rely on global state
3. Use fixtures for common setup and teardown
4. Add appropriate assertions to verify behavior
5. Include tests for error conditions and edge cases

## Test Naming Conventions

Tests follow this naming convention:

- Test files: `test_<module_name>.py`
- Test classes: `Test<ComponentName>`
- Test methods: `test_<functionality>_<scenario>`

For example: `test_add_fact_with_valid_inputs`
