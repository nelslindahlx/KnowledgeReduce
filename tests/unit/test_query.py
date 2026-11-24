"""Unit tests for QueryBuilder, network analytics, and Hybrid GraphRAG retriever."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from knowledgereduce.models import (
    Claim,
    ConflictRecord,
    ConflictStrategy,
    Entity,
    Evidence,
    KnowledgeLayer,
    KnowledgeReduceError,
    LayerData,
    Relation,
    ReliabilityRating,
)
from knowledgereduce.query import (
    HybridGraphRAGRetriever,
    QueryBuilder,
    bounded_shortest_path,
    central_nodes,
    detect_communities,
    k_hop_neighborhood,
)
from knowledgereduce.resolve import TfidfSVDProvider
from knowledgereduce.storage import DuckDBParquetStore, MemoryGraphStore
from knowledgereduce.storage.base import tokenize_search_query


def _seed_query_store() -> MemoryGraphStore:
    now = datetime(2025, 6, 1, tzinfo=UTC)
    store = MemoryGraphStore()
    data = LayerData(
        layer=KnowledgeLayer(layer_id="q1", name="Query Layer"),
        entities=[
            Entity(entity_id="e1", canonical_name="Civic Honors", entity_type="ORG"),
            Entity(entity_id="e2", canonical_name="Nels Lindahl", entity_type="PERSON"),
            Entity(entity_id="e3", canonical_name="University of Kansas", entity_type="ORG"),
            Entity(entity_id="e4", canonical_name="Isolated Entity", entity_type="CONCEPT"),
        ],
        claims=[
            Claim(
                claim_id="c1",
                statement="Nels Lindahl founded Civic Honors in 2006 to empower community engagement.",
                category="History",
                tags=["civic", "founding"],
                reliability=ReliabilityRating.VERIFIED,
                recorded_at=now - timedelta(days=5),
                confidence=0.95,
                evidence=[Evidence(source_id="s1", excerpt="founded Civic Honors")],
            ),
            Claim(
                claim_id="c2",
                statement="Nels Lindahl studied public administration at the University of Kansas.",
                category="Education",
                tags=["ku", "academic"],
                reliability=ReliabilityRating.LIKELY_TRUE,
                recorded_at=now,
                needs_review=True,
                evidence=[Evidence(source_id="s1", excerpt="University of Kansas")],
            ),
        ],
        relations=[
            Relation(relation_id="r1", source_id="c1", target_id="e1", relation_type="MENTIONS"),
            Relation(relation_id="r2", source_id="c1", target_id="e2", relation_type="MENTIONS"),
            Relation(relation_id="r3", source_id="c2", target_id="e2", relation_type="MENTIONS"),
            Relation(relation_id="r4", source_id="c2", target_id="e3", relation_type="MENTIONS"),
        ],
        conflicts=[
            ConflictRecord(
                conflict_id="cf1",
                target_type="claim",
                target_key="e1::PUBLISHED_IN",
                candidates=[
                    {"value": "2006", "claim_ids": ["c1"]},
                    {"value": "2020", "claim_ids": ["c2"]},
                ],
                resolution_strategy=ConflictStrategy.PRESERVE_DISPUTE,
                winning_value="2006",
            )
        ],
    )
    store.save_layer(data)
    return store


def test_query_builder_chaining_and_filters() -> None:
    store = _seed_query_store()
    base_qb = QueryBuilder(store, "q1")

    verified = base_qb.filter_min_reliability(ReliabilityRating.VERIFIED).execute_claims()
    assert [c.claim_id for c in verified] == ["c1"]

    # Base builder remained immutable after chained call
    assert len(base_qb.execute_claims()) == 2

    tagged = base_qb.filter_tags_any(["academic", "other"]).execute_claims()
    assert [c.claim_id for c in tagged] == ["c2"]

    by_date = (
        base_qb.filter_date_range(after=datetime(2025, 5, 30, tzinfo=UTC))
        .sort_claims(by="reliability")
        .execute_claims()
    )
    assert [c.claim_id for c in by_date] == ["c2"]

    orgs = base_qb.filter_entity_type("ORG").execute_entities()
    assert {e.entity_id for e in orgs} == {"e1", "e3"}


def test_analytics_helpers_and_edgeless_safety() -> None:
    store = _seed_query_store()
    graph = store.to_networkx("q1")

    sub1 = k_hop_neighborhood(graph, "e2", k=1)
    assert set(sub1.nodes()) == {"e2", "c1", "c2"}

    path = bounded_shortest_path(graph, "e1", "e3", max_hops=4)
    assert path == ["e1", "c1", "e2", "c2", "e3"]
    assert bounded_shortest_path(graph, "e1", "e3", max_hops=2) is None
    assert bounded_shortest_path(graph, "e1", "e4", max_hops=6) is None

    with pytest.raises(KnowledgeReduceError):
        k_hop_neighborhood(graph, "missing")

    top_pr = central_nodes(graph, metric="pagerank", top_k=2)
    assert len(top_pr) == 2
    assert len(central_nodes(graph, metric="degree", top_k=3)) == 3
    assert len(central_nodes(graph, metric="betweenness", top_k=3)) == 3

    communities = detect_communities(graph)
    assert sum(len(c) for c in communities) == graph.number_of_nodes()

    # Empty & 0-edge graph safety
    empty_store = MemoryGraphStore()
    empty_store.save_layer(LayerData(layer=KnowledgeLayer(layer_id="empty", name="Empty")))
    empty_g = empty_store.to_networkx("empty")
    assert central_nodes(empty_g) == []
    assert detect_communities(empty_g) == []


def test_hybrid_graphrag_retriever_returns_neighbors_and_conflicts() -> None:
    store = _seed_query_store()
    retriever = HybridGraphRAGRetriever(store)
    ctx = retriever.retrieve("q1", "Civic Honors founded 2006", top_k=1, hops=1)

    assert len(ctx.results) == 1
    assert ctx.results[0].claim.claim_id == "c1"
    assert len(ctx.results[0].graph_neighbors) == 2
    assert {e.entity_id for e in ctx.related_entities} == {"e1", "e2"}
    assert [cf.conflict_id for cf in ctx.conflicts] == ["cf1"]


def test_hybrid_graphrag_induced_entity_edge_attribution() -> None:
    store = MemoryGraphStore()
    data = LayerData(
        layer=KnowledgeLayer(layer_id="q_edge", name="Induced Edge Layer"),
        entities=[
            Entity(entity_id="e_ku", canonical_name="University of Kansas", entity_type="ORG"),
            Entity(entity_id="e_law", canonical_name="Lawrence", entity_type="GPE"),
        ],
        claims=[
            Claim(
                claim_id="c_ku",
                statement="The University of Kansas is located in Lawrence.",
                reliability=ReliabilityRating.VERIFIED,
                confidence=0.95,
                evidence=[Evidence(source_id="s1", excerpt="located in Lawrence")],
            )
        ],
        relations=[
            Relation(
                relation_id="r_m1", source_id="c_ku", target_id="e_ku", relation_type="MENTIONS"
            ),
            Relation(
                relation_id="r_m2", source_id="c_ku", target_id="e_law", relation_type="MENTIONS"
            ),
            Relation(
                relation_id="r_loc", source_id="e_ku", target_id="e_law", relation_type="LOCATED_IN"
            ),
        ],
    )
    store.save_layer(data)
    ctx = HybridGraphRAGRetriever(store).retrieve(
        "q_edge", "University of Kansas Lawrence", top_k=1, hops=1
    )
    assert len(ctx.results) == 1
    neighbors = ctx.results[0].graph_neighbors
    assert len(neighbors) == 3
    loc_edges = [n for n in neighbors if n["relation_type"] == "LOCATED_IN"]
    assert loc_edges == [
        {
            "node_id": "e_law",
            "relation_type": "LOCATED_IN",
            "label": "University of Kansas -> Lawrence",
            "source_id": "e_ku",
            "target_id": "e_law",
        }
    ]


def test_hybrid_graphrag_persists_index_in_duckdb_and_supports_tfidf_fallback(
    tmp_path: Path,
) -> None:
    seed_mem = _seed_query_store()
    data = seed_mem.load_layer("q1")
    duck = DuckDBParquetStore(tmp_path)
    duck.save_layer(data)

    retriever = HybridGraphRAGRetriever(duck)
    assert retriever.build_index("q1") == 2
    emb_path = tmp_path / "layers" / "q1" / "claim_embeddings.parquet"
    assert emb_path.is_file()

    # Warm query uses cached index + DuckDB subgraph extraction without loading full layer.
    ctx = retriever.retrieve("q1", "Civic Honors community", top_k=1, hops=1)
    assert [r.claim.claim_id for r in ctx.results] == ["c1"]
    assert {e.entity_id for e in ctx.related_entities} == {"e1", "e2"}
    assert [cf.conflict_id for cf in ctx.conflicts] == ["cf1"]

    # Stateful TfidfSVDProvider still works transparently without writing index files.
    tfidf_retriever = HybridGraphRAGRetriever(duck, embedding_provider=TfidfSVDProvider())
    assert tfidf_retriever.build_index("q1") == 0
    ctx_tfidf = tfidf_retriever.retrieve("q1", "University of Kansas", top_k=1, hops=1)
    assert [r.claim.claim_id for r in ctx_tfidf.results] == ["c2"]


def test_tokenize_search_query_filters_stop_words_with_fallback() -> None:
    assert tokenize_search_query("When was the Civic Honors book published?") == [
        "civic",
        "honors",
        "book",
        "published",
    ]
    assert tokenize_search_query("to be or") == ["to", "be", "or"]
    assert tokenize_search_query("to be or", max_tokens=2) == ["to", "be"]
    assert tokenize_search_query("when is it", max_tokens=0) == []


def test_hybrid_graphrag_idf_and_provenance_context_ranks_rare_factual_claims_first(
    tmp_path: Path,
) -> None:
    duck = DuckDBParquetStore(tmp_path)
    claims = [
        Claim(
            claim_id=f"clm_boiler_{idx}",
            statement="The Civic Honors program supports community leadership every semester.",
            source_id="src_book",
            source_title="The Book - Civic Honors",
            author_creator="Dr. Nels Lindahl",
            reliability=ReliabilityRating.LIKELY_TRUE,
            confidence=0.75,
            evidence=[Evidence(source_id="src_book", excerpt="Civic Honors program")],
        )
        for idx in range(12)
    ]
    claims.extend(
        [
            Claim(
                claim_id="clm_heading",
                statement="Civic Honors Book Overview",
                source_id="src_book",
                source_title="The Book - Civic Honors",
                author_creator="Dr. Nels Lindahl",
                reliability=ReliabilityRating.LIKELY_TRUE,
                confidence=0.75,
                evidence=[Evidence(source_id="src_book", excerpt="Civic Honors Book Overview")],
            ),
            Claim(
                claim_id="clm_unrelated_same_title",
                statement="Unrelated administrative notes without matching terms.",
                source_id="src_book",
                source_title="The Book - Civic Honors",
                author_creator="Dr. Nels Lindahl",
                reliability=ReliabilityRating.VERIFIED,
                confidence=0.95,
                evidence=[Evidence(source_id="src_book", excerpt="Unrelated notes")],
            ),
            Claim(
                claim_id="clm_pub_2006",
                statement="This book was published in 2006.",
                source_id="src_book",
                source_title="The Book - Civic Honors",
                author_creator="Dr. Nels Lindahl",
                reliability=ReliabilityRating.LIKELY_TRUE,
                confidence=0.80,
                evidence=[
                    Evidence(source_id="src_book", excerpt="This book was published in 2006.")
                ],
            ),
        ]
    )
    duck.save_layer(
        LayerData(
            layer=KnowledgeLayer(layer_id="book-idf", name="Book IDF"),
            claims=claims,
        )
    )

    retriever = HybridGraphRAGRetriever(duck)
    ctx = retriever.retrieve(
        "book-idf", "When was the Civic Honors book published?", top_k=3, hops=0
    )
    assert len(ctx.results) == 3
    assert ctx.results[0].claim.claim_id == "clm_pub_2006"
    assert "clm_unrelated_same_title" not in {r.claim.claim_id for r in ctx.results}


def test_hybrid_graphrag_debias_structural_heading_against_factual_answer(
    tmp_path: Path,
) -> None:
    duck = DuckDBParquetStore(tmp_path)
    claims = [
        Claim(
            claim_id="clm_heading_story",
            statement="The Story Behind Graduation With Civic Honors",
            reliability=ReliabilityRating.LIKELY_TRUE,
            confidence=0.80,
            evidence=[
                Evidence(
                    source_id="src_book",
                    excerpt="The Story Behind Graduation With Civic Honors",
                )
            ],
        ),
        Claim(
            claim_id="clm_fact_ku",
            statement=(
                "The story behind graduation with civic honors began in an academic setting "
                "during the spring semester of 2002 at the University of Kansas."
            ),
            reliability=ReliabilityRating.LIKELY_TRUE,
            confidence=0.80,
            evidence=[
                Evidence(
                    source_id="src_book",
                    excerpt="began in an academic setting during the spring semester of 2002",
                )
            ],
        ),
    ]
    duck.save_layer(
        LayerData(
            layer=KnowledgeLayer(layer_id="book-heading", name="Heading De-bias"),
            claims=claims,
        )
    )
    ctx = HybridGraphRAGRetriever(duck).retrieve(
        "book-heading",
        "When and where did the story behind graduation with civic honors begin?",
        top_k=2,
        hops=0,
    )
    assert [r.claim.claim_id for r in ctx.results] == ["clm_fact_ku", "clm_heading_story"]
