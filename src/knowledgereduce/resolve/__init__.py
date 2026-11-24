"""Entity disambiguation, blocking, and semantic clustering utilities."""

from knowledgereduce.resolve.blocking import DisjointSet, cluster_claims, normalize_text
from knowledgereduce.resolve.disambiguator import resolve_entities_and_remap
from knowledgereduce.resolve.embeddings import (
    EmbeddingProvider,
    HashingEmbeddingProvider,
    SentenceTransformerProvider,
    TfidfSVDProvider,
)

__all__ = [
    "DisjointSet",
    "EmbeddingProvider",
    "HashingEmbeddingProvider",
    "SentenceTransformerProvider",
    "TfidfSVDProvider",
    "cluster_claims",
    "normalize_text",
    "resolve_entities_and_remap",
]
