#!/usr/bin/env python3
"""
KnowledgeReduce package initialization
"""

from .fact_extraction import (
    EntityRecognizer,
    RelationshipExtractor,
    IntermediateRepresentationGenerator,
    FactExtractor
)

__all__ = [
    'EntityRecognizer',
    'RelationshipExtractor',
    'IntermediateRepresentationGenerator',
    'FactExtractor'
]
