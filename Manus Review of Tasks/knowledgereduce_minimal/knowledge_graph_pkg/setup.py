from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name='knowledge_graph_pkg',
    version='0.1.0',
    author='Nels Lindahl',
    author_email='nels@nelslindahl.com',
    description='A Python package for creating and managing portable knowledge graphs',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/nelslindahlx/KnowledgeReduce",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    install_requires=[
        'networkx>=2.5',
        'requests>=2.25.0',
        'beautifulsoup4>=4.9.0',
        'spacy>=3.0.0',
    ],
    python_requires='>=3.6',
)
