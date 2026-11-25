"""Unit tests for Map, Resolve, Conflict Resolution, IntegrityValidator, and Reduce."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

import pytest

from knowledgereduce.map import (
    DeterministicNLPMapper,
    SpacyNLPMapper,
    StructuredMapper,
    split_sentences,
)
from knowledgereduce.map.nlp import _ANCHORED_VERB_MAP
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
from knowledgereduce.reduce.conflicts import is_functional_predicate
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


def test_deterministic_nlp_mapper_extracts_camelcase_and_skips_all_caps() -> None:
    doc = SourceDocument(
        source_id="src-camel",
        uri="https://knowledgereduce.example/",
        source_type=SourceType.TEXT,
        content=(
            "KnowledgeReduce extends MapReduce using DuckDB and StackManager layers. "
            "PUBLISHED IN records stay ignored as multi-word phrases."
        ),
        trust_weight=0.85,
    )
    batch = DeterministicNLPMapper(min_sentence_length=15).map_document(doc)
    names = {e.canonical_name for e in batch.entities}
    assert {"KnowledgeReduce", "MapReduce", "DuckDB", "StackManager"}.issubset(names)
    assert "PUBLISHED IN" not in names


def test_spacy_nlp_mapper_errors_and_mocked_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeToken:
        def __init__(
            self,
            idx: int,
            *,
            pos_: str = "NOUN",
            dep_: str = "",
            lemma_: str = "",
            children: list[_FakeToken] | None = None,
        ) -> None:
            self.i = idx
            self.pos_ = pos_
            self.dep_ = dep_
            self.lemma_ = lemma_
            self.children = children or []

    class _FakeSpan:
        def __init__(self, text: str, label_: str, tokens: list[_FakeToken]) -> None:
            self.text = text
            self.label_ = label_
            self._tokens = tokens

        def __iter__(self) -> Any:
            return iter(self._tokens)

    class _FakeSent:
        def __init__(
            self,
            text: str,
            start_char: int,
            end_char: int,
            ents: list[_FakeSpan],
            tokens: list[_FakeToken],
        ) -> None:
            self.text = text
            self.start_char = start_char
            self.end_char = end_char
            self.ents = ents
            self._tokens = tokens

        def __iter__(self) -> Any:
            return iter(self._tokens)

    class _FakeDoc:
        def __init__(self, sents: list[_FakeSent]) -> None:
            self.sents = sents

    def _build_parsed(text: str) -> _FakeDoc:
        if "short" in text.lower():
            short_sent = _FakeSent("Hi.", 0, 3, [], [])
            return _FakeDoc([short_sent])

        t_subj = _FakeToken(0, pos_="PROPN", dep_="nsubj", lemma_="Civic Honors")
        t_obj = _FakeToken(3, pos_="GPE", dep_="pobj", lemma_="Lawrence")
        t_prep = _FakeToken(2, pos_="ADP", dep_="prep", lemma_="in", children=[t_obj])
        t_verb = _FakeToken(1, pos_="AUX", dep_="ROOT", lemma_="located", children=[t_subj, t_prep])
        ent_ch = _FakeSpan("Civic Honors", "ORG", [t_subj])
        ent_law = _FakeSpan("Lawrence", "GPE", [t_obj])
        s1 = _FakeSent(
            "Civic Honors is located in Lawrence for civic studies.",
            0,
            54,
            [ent_ch, ent_law],
            [t_subj, t_verb, t_prep, t_obj],
        )
        # Second sentence reuses Civic Honors so entity evidence accumulation branch runs
        t_subj2 = _FakeToken(10, pos_="PROPN", dep_="nsubj", lemma_="Civic Honors")
        t_obj2 = _FakeToken(12, pos_="DATE", dep_="dobj", lemma_="2006")
        t_verb2 = _FakeToken(
            11, pos_="VERB", dep_="ROOT", lemma_="published", children=[t_subj2, t_obj2]
        )
        ent_ch2 = _FakeSpan("Civic Honors", "ORG", [t_subj2])
        ent_yr = _FakeSpan("2006", "DATE", [t_obj2])
        s2 = _FakeSent(
            "Civic Honors was published in 2006 globally.",
            55,
            99,
            [ent_ch2, ent_yr],
            [t_subj2, t_verb2, t_obj2],
        )
        return _FakeDoc([s1, s2])

    class _FakeNLP:
        def __call__(self, text: str) -> _FakeDoc:
            return _build_parsed(text)

        def pipe(self, texts: list[str]) -> list[_FakeDoc]:
            return [_build_parsed(t) for t in texts]

    fake_spacy = ModuleType("spacy")

    def _missing_model(_name: str) -> Any:
        raise OSError("model not downloaded")

    fake_spacy.load = _missing_model  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "spacy", fake_spacy)

    doc = SourceDocument(
        source_id="spacy-1",
        uri="https://example.org/spacy",
        content="long enough content",
        trust_weight=0.9,
    )
    mapper = SpacyNLPMapper(model_name="missing_model", min_sentence_length=15)
    with pytest.raises(ExtractionError, match="missing_model"):
        mapper.map_document(doc)

    fake_spacy.load = lambda _name: _FakeNLP()  # type: ignore[attr-defined]
    mapper_ok = SpacyNLPMapper(model_name="en_core_web_sm", min_sentence_length=15)
    assert mapper_ok.map_documents([]) == []

    batch = mapper_ok.map_document(doc)
    assert len(batch.claims) == 2
    rel_types = {r.relation_type for r in batch.relations}
    assert {"LOCATED", "PUBLISHED", "MENTIONS"}.issubset(rel_types)

    short_doc = SourceDocument(
        source_id="spacy-short", uri="https://example.org/short", content="short"
    )
    batches = mapper_ok.map_documents([doc, short_doc])
    assert len(batches) == 2
    assert batches[1].claims == []


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


def test_split_sentences_preserves_apa_bibliography_entries() -> None:
    text = (
        "Introductory sentence precedes references.\n"
        "Carlsen, C. J., Lindahl, N., & Lindahl, S. (2004). "
        "Civic honors program at Johnson County Community College. "
        "Journal for Civic Commitment, 4, 1-9.\n"
        "Closing sentence follows cleanly."
    )
    sents = split_sentences(text)
    assert len(sents) == 3
    assert sents[1][0].startswith("Carlsen, C. J., Lindahl, N., & Lindahl, S. (2004).")
    assert sents[1][0].endswith("Journal for Civic Commitment, 4, 1-9.")


def test_deterministic_mapper_mid_initial_gpe_org_and_heading_suppression() -> None:
    doc = SourceDocument(
        source_id="src-ner-v12",
        uri="https://civichonors.com/p/the-book",
        source_type=SourceType.WEB,
        title="The Book - Civic Honors",
        content=(
            "Chapter 10: Never Fear Collaboration\n"
            "Building Connections in the Community\n"
            "Dr. Charles J. Carlsen led Johnson County Community College and submitted to "
            "Journal for Civic Commitment via Prentice Hall (Upper Saddle River, NJ) and New York.\n"
            "Deborah DeGrate, Carrie Donham, Chris Engle, and Jennifer Pittman-Leeper graduated "
            "in Lawrence, Kansas while reading Bowling Alone."
        ),
        trust_weight=0.9,
    )
    batch = DeterministicNLPMapper(min_sentence_length=20).map_document(doc)
    by_name: dict[str, list[Entity]] = {}
    for ent in batch.entities:
        by_name.setdefault(ent.canonical_name, []).append(ent)

    assert "Never Fear Collaboration" not in by_name
    assert "Building Connections" not in by_name

    assert by_name["Charles J. Carlsen"][0].entity_type == "PERSON"
    assert "Dr. Charles J. Carlsen" in by_name["Charles J. Carlsen"][0].aliases
    assert by_name["Johnson County Community College"][0].entity_type == "ORG"
    assert by_name["Journal for Civic Commitment"][0].entity_type == "ORG"
    assert by_name["Prentice Hall"][0].entity_type == "ORG"

    assert len(by_name["New York"]) == 1
    assert by_name["New York"][0].entity_type == "GPE"
    assert by_name["Upper Saddle River"][0].entity_type == "GPE"
    assert by_name["Lawrence"][0].entity_type == "GPE"
    assert by_name["Kansas"][0].entity_type == "GPE"

    for student in ("Deborah DeGrate", "Carrie Donham", "Chris Engle", "Jennifer Pittman-Leeper"):
        assert by_name[student][0].entity_type == "PERSON"
    assert by_name["Bowling Alone"][0].entity_type == "CONCEPT"


def test_deterministic_mapper_two_pass_linking_and_nonfunctional_triples() -> None:
    doc = SourceDocument(
        source_id="src-link-v12",
        uri="https://civichonors.com/p/the-book",
        source_type=SourceType.WEB,
        title="The Book - Civic Honors",
        content=(
            "This book was published in 2006.\n"
            "Dr. H. George Frederickson taught Concepts of Civil Society.\n"
            "The Civic Honors Program develops active citizen leaders.\n"
            "Later Dr. Frederickson showed the civic honors program facilitates community growth.\n"
            "Moreover, the program strengthens civic engagement across campuses."
        ),
        trust_weight=0.85,
    )
    batch = DeterministicNLPMapper(min_sentence_length=20).map_document(doc)
    reduced = KnowledgeReducer(conflict_strategy=ConflictStrategy.PRESERVE_DISPUTE).reduce_batches(
        [batch], layer_id="v12-map-test", layer_name="v12 Map Test"
    )

    assert reduced.conflicts == []
    claims_by_text = {c.statement: c for c in reduced.claims}
    pub_claim = claims_by_text["This book was published in 2006."]
    assert pub_claim.predicate == "PUBLISHED_IN"
    assert pub_claim.object_literal == "2006"
    assert pub_claim.subject_id is not None

    fred_sent = next(c for stmt, c in claims_by_text.items() if "Later Dr. Frederickson" in stmt)
    fred_mentions = {
        r.target_id
        for r in reduced.relations
        if r.source_id == fred_sent.claim_id and r.relation_type == "MENTIONS"
    }
    ent_by_id = {e.entity_id: e for e in reduced.entities}
    mentioned_names = {ent_by_id[eid].canonical_name for eid in fred_mentions}
    assert "H. George Frederickson" in mentioned_names
    assert "Civic Honors Program" in mentioned_names

    prog_sent = next(c for stmt, c in claims_by_text.items() if "Moreover" in stmt)
    assert prog_sent.predicate == "STRENGTHENS"
    assert prog_sent.subject_id is not None
    assert prog_sent.object_id is not None
    assert any(r.relation_type == "STRENGTHENS" for r in reduced.relations)
    assert all(not is_functional_predicate(pred) for pred in _ANCHORED_VERB_MAP.values())


def test_deterministic_mapper_clause_stops_org_typing_and_temporal_conflicts() -> None:
    src_primary = SourceDocument(
        source_id="src-primary",
        uri="https://civichonors.com/facts",
        source_type=SourceType.WEB,
        title="Civic Honors Notes",
        content=(
            "Dr. Nels Lindahl studied at University of Kansas during the spring of 2002.\n"
            "Dr. Nels Lindahl is based in Denver, Colorado conducting civic research.\n"
            "Gulick and Urwick published via Institute of Public Administration and Fortune Magazine.\n"
            "Thompson published Organizations in Action through McGraw-Hill.\n"
            "The university can bridge community partners.\n"
            "Civic Engagement has been fostered by student leaders."
        ),
        trust_weight=0.95,
    )
    src_conflict = SourceDocument(
        source_id="src-blog",
        uri="https://blog.example/post",
        source_type=SourceType.WEB,
        title="Blog Post",
        content="Dr. Nels Lindahl studied at University of Kansas during the spring of 2004.",
        trust_weight=0.40,
    )
    mapper = DeterministicNLPMapper(min_sentence_length=20)
    b1 = mapper.map_document(src_primary)
    b2 = mapper.map_document(src_conflict)

    ents_by_name = {e.canonical_name: e for e in b1.entities}
    assert ents_by_name["Fortune Magazine"].entity_type == "ORG"
    assert ents_by_name["Institute of Public Administration"].entity_type == "ORG"
    assert "McGraw-Hill" in ents_by_name

    c_studied = next(c for c in b1.claims if "studied at" in c.statement)
    assert c_studied.predicate == "STUDIED_AT"
    assert c_studied.object_literal == "University of Kansas"

    c_based = next(c for c in b1.claims if "is based in" in c.statement)
    assert c_based.predicate == "IS_BASED_IN"
    assert c_based.object_literal == "Denver, Colorado"

    c_uni = next(c for c in b1.claims if "The university can bridge" in c.statement)
    assert c_uni.predicate == "BRIDGES"
    assert c_uni.subject_id == ents_by_name["University of Kansas"].entity_id

    c_passive = next(c for c in b1.claims if "has been fostered" in c.statement)
    assert c_passive.predicate == "FOSTERED_BY"
    assert c_passive.subject_id == ents_by_name["Civic Engagement"].entity_id

    reduced = KnowledgeReducer(conflict_strategy=ConflictStrategy.PRESERVE_DISPUTE).reduce_batches(
        [b1, b2], layer_id="v14-p2-test", layer_name="v14 Phase 2 Test"
    )
    assert len(reduced.conflicts) == 1
    assert reduced.conflicts[0].target_key.endswith("::STUDIED_AT::year")
    assert reduced.conflicts[0].winning_value == "2002"
    assert any(r.relation_type == "CONTRADICTS" for r in reduced.relations)

    # Also verify non-PRESERVE_DISPUTE strategy picks the trusted winner cleanly.
    resolved_trust = KnowledgeReducer(
        conflict_strategy=ConflictStrategy.SOURCE_TRUST_PRIORITY
    ).reduce_batches([b1, b2], layer_id="v14-p2-trust", layer_name="v14 Phase 2 Trust")
    assert len(resolved_trust.conflicts) == 1
    assert resolved_trust.conflicts[0].needs_review is False
    assert resolved_trust.conflicts[0].winning_value == "2002"


def test_integrity_validator_catches_duplicates_dangling_refs_and_warnings() -> None:
    from knowledgereduce.models import ConflictRecord, KnowledgeLayer, LayerData
    from knowledgereduce.reduce import IntegrityValidator

    dup_ent = Entity(entity_id="e1", canonical_name="One", entity_type="CONCEPT")
    dup_clm = Claim(
        claim_id="c1",
        statement="Statement referencing missing subject and object.",
        subject_id="missing_s",
        object_id="missing_o",
    )
    dup_rel = Relation(
        relation_id="r1", source_id="missing_src", target_id="missing_dst", relation_type="LINKS"
    )
    dup_cf = ConflictRecord(conflict_id="cf1", target_type="claim", target_key="k1")
    bad = LayerData(
        layer=KnowledgeLayer(layer_id="bad-val", name="Bad"),
        entities=[dup_ent, dup_ent],
        claims=[dup_clm, dup_clm],
        relations=[dup_rel, dup_rel],
        conflicts=[dup_cf, dup_cf],
    )
    report = IntegrityValidator().validate(bad, strict=False)
    assert report.valid is False
    # 4 duplicate-ID errors + 4 claim subject/object errors + 4 relation source/target errors
    assert len(report.errors) == 12
    assert len(report.warnings) == 4


def test_deterministic_nlp_mapper_filters_headings_questions_and_propagates_section_notes() -> None:
    doc = SourceDocument(
        source_id="src-hygiene",
        uri="https://civichonors.com/hygiene",
        source_type=SourceType.WEB,
        title="Civic Honors",
        content=(
            "Chapter 1: Introduction\n"
            "Dr. Nels Lindahl — June 14, 2020 — Denver, Colorado\n"
            "How does a university launch civic recognition programs?\n"
            "Civic Honors was published in 2006 to inspire student service."
        ),
        trust_weight=0.90,
    )

    default_batch = DeterministicNLPMapper(min_sentence_length=25).map_document(doc)
    stmts = [c.statement for c in default_batch.claims]
    assert not any(s.startswith("Chapter 1:") for s in stmts)
    assert not any(s.endswith("?") for s in stmts)
    assert any("June 14, 2020" in s for s in stmts)
    assert len(default_batch.claims) == 2
    assert all(
        c.contextual_notes == "Section: Chapter 1: Introduction" for c in default_batch.claims
    )

    raw_batch = DeterministicNLPMapper(
        min_sentence_length=20,
        skip_headings=False,
        skip_questions=False,
    ).map_document(doc)
    raw_stmts = [c.statement for c in raw_batch.claims]
    assert any(s.startswith("Chapter 1:") for s in raw_stmts)
    assert any(s.endswith("?") for s in raw_stmts)
    assert len(raw_batch.claims) == 4
