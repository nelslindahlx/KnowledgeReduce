from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="knowledgereduce",
    version="1.0.0",
    author="Nels Lindahl",
    author_email="nels.lindahl@example.com",
    description="A framework for building stackable knowledge graphs inspired by the MapReduce paradigm",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/nelslindahlx/KnowledgeReduce",
    project_urls={
        "Bug Tracker": "https://github.com/nelslindahlx/KnowledgeReduce/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "networkx>=2.6.0",
        "matplotlib>=3.4.0",
        "numpy>=1.20.0",
        "pandas>=1.3.0",
        "scikit-learn>=0.24.0",
        "nltk>=3.6.0",
        "beautifulsoup4>=4.9.0",
        "requests>=2.25.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0.0",
            "pytest-cov>=2.12.0",
            "black>=21.5b2",
            "isort>=5.9.0",
            "flake8>=3.9.0",
        ],
        "docs": [
            "sphinx>=4.0.0",
            "sphinx-rtd-theme>=0.5.0",
            "myst-parser>=0.15.0",
        ],
    },
    include_package_data=True,
)
