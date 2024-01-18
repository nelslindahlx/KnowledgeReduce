from setuptools import setup, find_packages

setup(
    name='knowledge_graph_pkg',
    version='0.1',
    author='Nels Lindahl',
    author_email='nels@nelslindahl.com',
    description='A Python package for creating and managing portable knowledge graphs',
    packages=find_packages(),
    install_requires=['requests', 'beautifulsoup4', 'networkx', 'spacy'],
    python_requires='>=3.6',
)
