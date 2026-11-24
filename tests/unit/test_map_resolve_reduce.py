"""Unit tests for Map, Resolve, Conflict Resolution, IntegrityValidator, and Reduce."""

from __future__ import annotations

import pytest

from knowledgereduce.map import (
    DeterministicNLPMapper,
    SpacyNLPMapper,
    StructuredMapper,
    split_sentences,
)
from knowledgereduce.models import (
    Claim,
    ConflictStrategy,
    Entity,
    Evidence,
    ExtractionError,
    IntegrityValidationError,
    KnowledgeLayer,
    LayerData,
    MappedBatch,
    Relation,
    ReliabilityRating,
    SourceDocument,
    SourceType,
)
from knowledgereduce.reduce import IntegrityValidator, KnowledgeReducer, resolve_claim_conflicts
from knowledgereduce.resolve import TfidfSVDProvider, cluster_claims, resolve_entities_and_remap


def test_split_sentences_preserves_abbreviations_and_initials() -> None:
    text = (
        "Dr. Nels Lindahl studied under Dr. H. George Frederickson in U.S. public administration. "
        "The class met in 2002 at the University of Kansas. Enjoy!"
    )
    sents = split_sentences(text)
    assert len(sents) == 3
    assert sents[0][0].startswith("Dr. Nels Lindahl")
    assert "H. George Frederickson" in sents[0][0]


def test_deterministic_nlp_mapper_extracts_connected_entities_claims_and_relations() -> None:
    doc = SourceDocument(
        source_id="src-1",
        uri="https://civichonors.com/",
        source_type=SourceType.WEB,
        title="Civic Honors",
        content=(
            "Civic Honors was published in 2006 in Denver, Colorado. "
            "Dr. Nels Lindahl studied at University of Kansas under Dr. H. George Frederickson."
        ),
        trust_weight=0.9,
    )
    mapper = DeterministicNLPMapper(min_sentence_length=20)
    batch = mapper.map_document(doc)

    names = {e.canonical_name for e in batch.entities}
    assert "Civic Honors" in names
    assert "Nels Lindahl" in names
    assert "University of Kansas" in names
    assert len(batch.claims) == 2
    assert any(c.predicate == "PUBLISHED_IN" and c.object_literal == "2006" for c in batch.claims)
    assert any(r.relation_type == "MENTIONS" for r in batch.relations)


def test_structured_mapper_and_spacy_missing_dependency() -> None:
    doc = SourceDocument(
        source_id="csv-1",
        uri="file:///facts.csv",
        source_type=SourceType.CSV,
        content=(
            "subject,subject_type,predicate,object,object_type,statement,category,tags,reliability\n"
            'Civic Honors,ORG,PUBLISHED_IN,2006,DATE,"Civic Honors was published in 2006.",Pub,"civic,ku",VERIFIED\n'
        ),
        trust_weight=0.9,
    )
    batch = StructuredMapper().map_document(doc)
    assert len(batch.entities) == 2
    assert len(batch.claims) == 1
    assert batch.claims[0].reliability == ReliabilityRating.VERIFIED
    assert batch.claims[0].tags == ["civic", "ku"]
    assert any(r.relation_type == "PUBLISHED_IN" for r in batch.relations)

    spacy_mapper = SpacyNLPMapper()
    with pytest.raises(ExtractionError, match="spaCy"):
        spacy_mapper.map_document(doc)


def test_structured_mapper_preserves_per_row_entity_types_and_predicates() -> None:
    doc = SourceDocument(
        source_id="csv-multi",
        uri="file:///multi.csv",
        source_type=SourceType.CSV,
        content=(
            "subject,subject_type,predicate,object,object_type,statement,category,tags,reliability,object_is_entity\n"
            'Civic Honors,ORG,PUBLISHED_IN,2006,DATE,"Civic Honors was published in 2006.",Publication,"civic,history",VERIFIED,true\n'
            'Nels Lindahl,PERSON,AFFILIATED_WITH,University of Kansas,ORG,"Nels Lindahl studied at the University of Kansas.",Biography,"ku,alumni",LIKELY_TRUE,true\n'
            'University of Kansas,ORG,LOCATED_IN,Lawrence,GPE,"The University of Kansas is located in Lawrence.",Geography,"kansas,education",VERIFIED,true\n'
            'Civic Honors,ORG,HAS_EDITION_COUNT,1,NUMBER,"Civic Honors had 1 initial edition.",Meta,"meta",VERIFIED,false\n'
        ),
        trust_weight=0.9,
    )
    batch = StructuredMapper().map_document(doc)

    by_name: dict[str, list[Entity]] = {}
    for ent in batch.entities:
        by_name.setdefault(ent.canonical_name, []).append(ent)

    assert len(by_name["Civic Honors"]) == 1
    assert by_name["Civic Honors"][0].entity_type == "ORG"
    assert len(by_name["2006"]) == 1
    assert by_name["2006"][0].entity_type == "DATE"
    assert len(by_name["Nels Lindahl"]) == 1
    assert by_name["Nels Lindahl"][0].entity_type == "PERSON"
    assert len(by_name["University of Kansas"]) == 1
    assert by_name["University of Kansas"][0].entity_type == "ORG"
    assert len(by_name["Lawrence"]) == 1
    assert by_name["Lawrence"][0].entity_type == "GPE"
    assert "1" not in by_name

    rel_types = {r.relation_type for r in batch.relations}
    assert {"PUBLISHED_IN", "AFFILIATED_WITH", "LOCATED_IN", "MENTIONS"}.issubset(rel_types)
    assert "HAS_EDITION_COUNT" not in rel_types
    assert len(batch.claims) == 4
    assert batch.claims[3].object_literal == "1"
    assert batch.claims[3].object_id is None


def test_structured_mapper_infers_sparse_json_schema_across_all_rows() -> None:
    import json

    sparse_rows = [
        {"subject": "Civic Honors", "predicate": "EXTENDS", "object": "Civic Engagement"},
        {
            "subject": "Nels Lindahl",
            "subject_type": "PERSON",
            "predicate": "STUDIED_AT",
            "object": "University of Kansas",
            "object_type": "ORG",
            "statement": "Nels Lindahl studied at the University of Kansas.",
            "category": "Biography",
            "tags": ["ku", "alumni"],
            "reliability": "VERIFIED",
        },
        {
            "subject": "Civic Honors",
            "subject_type": "ORG",
            "predicate": "HAS_CHAPTERS",
            "object": "12",
            "object_is_entity": False,
            "statement": "Civic Honors has 12 chapters.",
        },
    ]
    doc = SourceDocument(
        source_id="json-sparse",
        uri="file:///sparse.json",
        source_type=SourceType.JSON,
        content=json.dumps(sparse_rows),
        trust_weight=0.8,
    )
    batch = StructuredMapper().map_document(doc)
    assert len(batch.claims) == 3
    assert batch.claims[1].category == "Biography"
    assert batch.claims[1].tags == ["ku", "alumni"]
    assert batch.claims[1].reliability == ReliabilityRating.VERIFIED
    assert batch.claims[2].object_literal == "12"
    assert batch.claims[2].object_id is None

    by_name = {e.canonical_name: e for e in batch.entities}
    assert by_name["Nels Lindahl"].entity_type == "PERSON"
    assert by_name["University of Kansas"].entity_type == "ORG"
    assert "12" not in by_name


def test_resolve_entities_merges_variants_and_remaps_endpoints() -> None:
    b1 = MappedBatch(
        source_document=SourceDocument(
            source_id="s1", uri="https://a.example", content="x", trust_weight=0.9
        ),
        entities=[
            Entity(
                entity_id="e_nels_1",
                canonical_name="Dr. Nels Lindahl",
                entity_type="PERSON",
                evidence=[Evidence(source_id="s1", excerpt="Dr. Nels Lindahl")],
            ),
            Entity(
                entity_id="e_john_1",
                canonical_name="John Smith",
                entity_type="PERSON",
                evidence=[Evidence(source_id="s1", excerpt="John Smith")],
            ),
        ],
        claims=[
            Claim(
                claim_id="c1",
                statement="Dr. Nels Lindahl met John Smith in Denver.",
                subject_id="e_nels_1",
                predicate="MET",
                object_id="e_john_1",
                source_id="s1",
            )
        ],
        relations=[
            Relation(
                relation_id="r1",
                source_id="e_nels_1",
                target_id="e_john_1",
                relation_type="MET",
            )
        ],
    )
    b2 = MappedBatch(
        source_document=SourceDocument(
            source_id="s2", uri="https://b.example", content="y", trust_weight=0.7
        ),
        entities=[
            Entity(
                entity_id="e_nels_2",
                canonical_name="Nels Lindahl",
                entity_type="PERSON",
                evidence=[Evidence(source_id="s2", excerpt="Nels Lindahl")],
            ),
            Entity(
                entity_id="e_john_2",
                canonical_name="J. Smith",
                entity_type="PERSON",
                evidence=[Evidence(source_id="s2", excerpt="J. Smith")],
            ),
        ],
        relations=[
            Relation(
                relation_id="r2",
                source_id="e_nels_2",
                target_id="e_john_2",
                relation_type="KNOWS",
            )
        ],
    )

    entities, claims, relations, sources, id_map = resolve_entities_and_remap([b1, b2])
    assert len(sources) == 2
    assert len(entities) == 2
    assert id_map["e_nels_1"] == id_map["e_nels_2"]
    assert id_map["e_john_1"] == id_map["e_john_2"]
    assert claims[0].subject_id == id_map["e_nels_1"]
    assert claims[0].object_id == id_map["e_john_1"]
    assert all(r.source_id == id_map["e_nels_1"] for r in relations)
    assert all(r.target_id == id_map["e_john_1"] for r in relations)


def test_cluster_claims_preserves_canonical_representatives_on_near_duplicates() -> None:
    c1 = Claim(
        claim_id="c1",
        statement="Civic Honors was published in 2006 to promote community engagement.",
        reliability=ReliabilityRating.VERIFIED,
        evidence=[Evidence(source_id="s1", excerpt="c1")],
    )
    c2 = Claim(
        claim_id="c2",
        statement="Civic Honors was published in 2006 to promote community engagement!",
        reliability=ReliabilityRating.UNVERIFIED,
        evidence=[Evidence(source_id="s2", excerpt="c2")],
    )
    c3 = Claim(
        claim_id="c3",
        statement="Quantum entanglement enables non-classical correlations across qubits.",
        reliability=ReliabilityRating.LIKELY_TRUE,
        evidence=[Evidence(source_id="s3", excerpt="c3")],
    )
    short = Claim(claim_id="c_short", statement="Hi.")

    clusters, dropped = cluster_claims(
        [c1, c2, c3, short],
        embedding_provider=TfidfSVDProvider(),
        min_length=20,
    )
    # Critical regression check against v17-v18 symmetric deletion bug:
    # c1 & c2 merge into 1 cluster (keeping 1 representative), c3 stays separate -> 2 clusters!
    assert len(clusters) == 2
    assert [d.claim_id for d in dropped] == ["c_short"]


@pytest.mark.parametrize("strategy", list(ConflictStrategy))
def test_conflict_resolution_strategies(strategy: ConflictStrategy) -> None:
    c_2006 = Claim(
        claim_id="c_2006",
        statement="Civic Honors was published in 2006.",
        subject_id="ent_ch",
        predicate="PUBLISHED_IN",
        object_literal="2006",
        reliability=ReliabilityRating.VERIFIED,
        source_id="s_authoritative",
        confidence=0.95,
    )
    c_2020 = Claim(
        claim_id="c_2020",
        statement="Civic Honors was published in 2020.",
        subject_id="ent_ch",
        predicate="PUBLISHED_IN",
        object_literal="2020",
        reliability=ReliabilityRating.POSSIBLY_TRUE,
        source_id="s_blog",
        confidence=0.7,
    )
    trust = {"s_authoritative": 0.95, "s_blog": 0.5}
    resolved_claims, contra_rels, conflicts = resolve_claim_conflicts(
        [c_2006, c_2020],
        trust,
        strategy=strategy,
    )
    assert len(conflicts) == 1
    if strategy == ConflictStrategy.PRESERVE_DISPUTE:
        assert len(resolved_claims) == 2
        assert all(c.needs_review for c in resolved_claims)
        assert len(contra_rels) == 1
        assert contra_rels[0].relation_type == "CONTRADICTS"
        assert conflicts[0].needs_review is True
        assert conflicts[0].winning_value == "2006"
    else:
        assert len(resolved_claims) == 1
        assert resolved_claims[0].needs_review is False
        assert contra_rels == []
        assert conflicts[0].needs_review is False


def test_integrity_validator_catches_dangling_references_and_reducer_prevents_them() -> None:
    bad_layer = LayerData(
        layer=KnowledgeLayer(layer_id="bad", name="Bad"),
        entities=[Entity(entity_id="e1", canonical_name="A", entity_type="ORG")],
        relations=[
            Relation(relation_id="r1", source_id="e1", target_id="missing", relation_type="X")
        ],
    )
    validator = IntegrityValidator()
    with pytest.raises(IntegrityValidationError, match="Dangling relation"):
        validator.validate(bad_layer, strict=True)

    # Full reducer check
    reducer = KnowledgeReducer(conflict_strategy=ConflictStrategy.PRESERVE_DISPUTE)
    doc = SourceDocument(
        source_id="s1",
        uri="https://civichonors.com/",
        source_type=SourceType.WEB,
        content=(
            "Civic Honors was published in 2006 in Denver, Colorado. "
            "Civic Honors was published in 2020 in Denver, Colorado."
        ),
        trust_weight=0.8,
    )
    batch = DeterministicNLPMapper(min_sentence_length=15).map_document(doc)
    reduced = reducer.reduce_batches([batch], layer_id="reduced-1", layer_name="Reduced")
    report = validator.validate(reduced, strict=True)
    assert report.valid is True
    assert reduced.layer.stats["open_conflicts"] == 1
    assert any(r.relation_type == "CONTRADICTS" for r in reduced.relations)
