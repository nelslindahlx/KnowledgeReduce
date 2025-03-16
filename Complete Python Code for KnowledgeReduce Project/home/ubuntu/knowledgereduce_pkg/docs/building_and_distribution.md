# Building and Distribution Guide

This document provides instructions for building and distributing the KnowledgeReduce package.

## Prerequisites

- Python 3.8 or higher
- pip
- setuptools
- wheel
- twine (for PyPI distribution)

## Building the Package

To build the package, follow these steps:

1. Clone the repository:
   ```bash
   git clone https://github.com/nelslindahlx/KnowledgeReduce.git
   cd KnowledgeReduce
   ```

2. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

3. Build the package:
   ```bash
   python setup.py sdist bdist_wheel
   ```

This will create a source distribution and a wheel distribution in the `dist` directory.

## Local Installation

To install the package locally for testing:

```bash
pip install -e .
```

This will install the package in development mode, allowing you to make changes to the code without reinstalling.

## Running Tests

To run the tests:

```bash
pytest tests/
```

To run tests with coverage:

```bash
pytest --cov=knowledgereduce tests/
```

## Distribution to PyPI

To distribute the package to PyPI:

1. Make sure you have the latest version of twine:
   ```bash
   pip install --upgrade twine
   ```

2. Upload the package to PyPI:
   ```bash
   twine upload dist/*
   ```

You will need to provide your PyPI username and password.

## Distribution to TestPyPI

To test the distribution process without affecting the main PyPI repository:

```bash
twine upload --repository-url https://test.pypi.org/legacy/ dist/*
```

Then you can install from TestPyPI:

```bash
pip install --index-url https://test.pypi.org/simple/ knowledgereduce
```

## Creating a New Release

1. Update the version number in `knowledgereduce/__init__.py`
2. Update the CHANGELOG.md file
3. Commit the changes:
   ```bash
   git add knowledgereduce/__init__.py CHANGELOG.md
   git commit -m "Bump version to X.Y.Z"
   ```
4. Create a new tag:
   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
5. Build and upload the new release:
   ```bash
   python setup.py sdist bdist_wheel
   twine upload dist/*
   ```

## Troubleshooting

- If you encounter issues with dependencies, try updating setuptools and pip:
  ```bash
  pip install --upgrade setuptools pip
  ```

- If you get errors during the build process, check that all required files are included in MANIFEST.in

- If tests fail, check that all dependencies are installed:
  ```bash
  pip install -e ".[dev]"
  ```

## Additional Resources

- [Python Packaging User Guide](https://packaging.python.org/)
- [Setuptools Documentation](https://setuptools.readthedocs.io/)
- [Twine Documentation](https://twine.readthedocs.io/)
- [PyPI](https://pypi.org/)
