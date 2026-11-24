"""Unit tests for lossless claim clustering and metadata-preserving reduction."""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime

from knowledgereduce.models import (
    Claim,
    Entity,
    Evidence,
    MappedBatch,
    Relation,
    ReliabilityRating,
    SourceDocument,
    SourceType,
)
from knowledgereduce.reduce import KnowledgeReducer
from knowledgereduce.reduce.reducer import _claim_importance, _merge_claim_cluster
from knowledgereduce.resolve import cluster_claims
from knowledgereduce.resolve.blocking import _claims_compatible_for_merge


def _claim(
    claim_id: str,
    statement: str,
    *,
    source_id: str = "src-1",
    reliability: ReliabilityRating = ReliabilityRating.LIKELY_TRUE,
    confidence: float = 0.8,
    subject_id: str | None = None,
    predicate: str | None = None,
    object_id: str | None = None,
    object_literal: str | None = None,
    published_at: datetime | None = None,
    author_creator: str | None = None,
    url_reference: str | None = None,
    source_title: str = "",
    contextual_notes: str = "",
) -> Claim:
    return Claim(
        claim_id=claim_id,
        statement=statement,
        reliability=reliability,
        confidence=confidence,
        source_id=source_id,
        subject_id=subject_id,
        predicate=predicate,
        object_id=object_id,
        object_literal=object_literal,
        published_at=published_at,
        author_creator=author_creator,
        url_reference=url_reference,
        source_title=source_title,
        contextual_notes=contextual_notes,
        evidence=[Evidence(source_id=source_id, excerpt=statement)],
    )


def test_resolve_and_reduce_import_order_has_no_cycles() -> None:
    for script in (
        "import knowledgereduce.resolve; import knowledgereduce.reduce",
        "import knowledgereduce.reduce; import knowledgereduce.resolve",
        "from knowledgereduce.resolve.blocking import _claims_compatible_for_merge",
    ):
        proc = subprocess.run(  # noqa: S603
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, f"{script} failed: {proc.stderr}"


def test_functional_vs_nonfunctional_predicate_merge_compatibility() -> None:
    vocab = frozenset({"PUBLISHED_IN", "FOUNDED_IN"})

    func_a = _claim(
        "c1",
        "Civic Honors was published in 2006.",
        subject_id="ent_ch",
        predicate="PUBLISHED_IN",
        object_literal="2006",
    )
    func_b = _claim(
        "c2",
        "Civic Honors was published in 2020.",
        subject_id="ent_ch",
        predicate="PUBLISHED_IN",
        object_literal="2020",
    )
    assert _claims_compatible_for_merge(func_a, func_b, functional_vocab=vocab) is False

    # Non-functional descriptive predicates with differing literal phrasings can still merge.
    desc_a = _claim(
        "c3",
        "Civic Honors provides students with civic leadership guidance.",
        subject_id="ent_ch",
        predicate="PROVIDES",
        object_literal="students with civic leadership guidance",
    )
    desc_b = _claim(
        "c4",
        "Civic Honors provides college students with civic leadership guidance.",
        subject_id="ent_ch",
        predicate="PROVIDES",
        object_literal="college students with civic leadership guidance",
    )
    assert _claims_compatible_for_merge(desc_a, desc_b, functional_vocab=vocab) is True

    # Non-functional predicates asserting distinct linked entity targets stay separate.
    obj_a = _claim(
        "c5",
        "Civic Honors emphasizes leadership development.",
        subject_id="ent_ch",
        predicate="EMPHASIZES",
        object_id="ent_lead",
    )
    obj_b = _claim(
        "c6",
        "Civic Honors emphasizes community service.",
        subject_id="ent_ch",
        predicate="EMPHASIZES",
        object_id="ent_serv",
    )
    assert _claims_compatible_for_merge(obj_a, obj_b, functional_vocab=vocab) is False


def test_asymmetric_year_and_apa_reference_guards_prevent_fact_erasure() -> None:
    narrative = _claim(
        "c_narr",
        "I was honored to submit an article discussing service learning to the Journal for Civic Commitment.",
    )
    apa_ref = _claim(
        "c_ref",
        "Carlsen, C. J., Lindahl, N., & Lindahl, S. (2004). Service learning in civic commitment programs. Journal for Civic Commitment, 4, 1-9.",
    )
    assert _claims_compatible_for_merge(narrative, apa_ref) is False

    # Even a paraphrase without numbers stays separated from a dated claim or formal APA entry.
    undated = _claim("c_u", "University of Kansas hosted civic leadership workshops.")
    dated = _claim("c_d", "University of Kansas hosted civic leadership workshops in 2002.")
    assert _claims_compatible_for_merge(undated, dated) is False

    # An unpunctuated heading fragment subsumed verbatim by a longer dated sentence can merge
    # so the full dated sentence absorbs it without losing the year.
    heading_frag = _claim("c_hdr", "The Story Behind Graduation With Civic Honors")
    full_dated = _claim(
        "c_full",
        "The story behind graduation with civic honors began during the spring semester of 2002 at the University of Kansas.",
    )
    assert _claims_compatible_for_merge(heading_frag, full_dated) is True

    # Symmetric years remain compatible for paraphrase clustering.
    same_year_a = _claim("c_s1", "Civic Honors was published in 2006 to inspire student leaders.")
    same_year_b = _claim("c_s2", "Civic Honors was published in 2006 to guide student leaders.")
    assert _claims_compatible_for_merge(same_year_a, same_year_b) is True

    clusters, _dropped = cluster_claims([narrative, apa_ref], semantic_threshold=0.5)
    assert len(clusters) == 2


def test_merge_claim_cluster_inherits_triple_and_provenance_atomically() -> None:
    pub_dt = datetime(2004, 6, 1, tzinfo=UTC)
    ungrounded_winner = _claim(
        "c_win",
        "Civic Honors advances democratic participation and community service among students.",
        source_id="src-high",
        reliability=ReliabilityRating.VERIFIED,
        confidence=0.95,
    )
    grounded_secondary = _claim(
        "c_sec",
        "Civic Honors advances community service among students.",
        source_id="src-low",
        reliability=ReliabilityRating.LIKELY_TRUE,
        confidence=0.80,
        subject_id="ent_ch",
        predicate="ADVANCES",
        object_id="ent_svc",
        published_at=pub_dt,
        author_creator="Nels Lindahl",
        url_reference="https://civichonors.com/p/the-book",
        source_title="Civic Honors Book",
        contextual_notes="Chapter 1 summary",
    )

    source_trust = {"src-high": 0.95, "src-low": 0.60}
    merged, id_map = _merge_claim_cluster(
        [ungrounded_winner, grounded_secondary],
        source_trust,
        degree_map={"c_win": 2},
        max_degree=2,
    )
    assert id_map == {"c_win": "c_win", "c_sec": "c_win"}
    assert merged.claim_id == "c_win"
    assert merged.merged_from == ["c_sec"]
    # Atomic triple inherited from secondary donor since winner had none.
    assert merged.subject_id == "ent_ch"
    assert merged.predicate == "ADVANCES"
    assert merged.object_id == "ent_svc"
    assert merged.object_literal is None
    # Provenance fields recovered from cluster members.
    assert merged.published_at == pub_dt
    assert merged.author_creator == "Nels Lindahl"
    assert merged.url_reference == "https://civichonors.com/p/the-book"
    assert merged.source_title == "Civic Honors Book"
    assert merged.contextual_notes == "Chapter 1 summary"

    # Equal-score tie breaks in favor of the grounded claim.
    tie_ungrounded = _claim("c_a", "Same statement text here.", source_id="src-high")
    tie_grounded = _claim(
        "c_b",
        "Same statement text here.",
        source_id="src-high",
        subject_id="ent_1",
        predicate="MENTIONS_TOPIC",
        object_literal="topic",
    )
    assert _claim_importance(tie_grounded, source_trust, {}, 1) > _claim_importance(
        tie_ungrounded, source_trust, {}, 1
    )


def test_reducer_preserves_apa_ref_while_merging_non_functional_paraphrases() -> None:
    src = SourceDocument(
        source_id="src-book",
        uri="https://civichonors.com/p/the-book",
        source_type=SourceType.WEB,
        title="Civic Honors Book",
        content="Civic Honors source text",
        trust_weight=0.85,
    )
    ent_ch = Entity(
        entity_id="ent_ch",
        canonical_name="Civic Honors",
        entity_type="ORG",
        evidence=[Evidence(source_id="src-book", excerpt="Civic Honors")],
    )
    ent_jcc = Entity(
        entity_id="ent_jcc",
        canonical_name="Journal for Civic Commitment",
        entity_type="ORG",
        evidence=[Evidence(source_id="src-book", excerpt="Journal for Civic Commitment")],
    )
    c_para_1 = _claim(
        "c_p1",
        "Civic Honors provides students with civic leadership guidance for local engagement.",
        source_id="src-book",
        subject_id="ent_ch",
        predicate="PROVIDES",
        object_literal="students with civic leadership guidance",
    )
    c_para_2 = _claim(
        "c_p2",
        "Civic Honors provides students with civic leadership guidance in local engagement.",
        source_id="src-book",
        subject_id="ent_ch",
        predicate="PROVIDES",
        object_literal="students with civic leadership guidance in local engagement",
    )
    c_narr = _claim(
        "c_narr",
        "I was honored to submit an article discussing service learning to the Journal for Civic Commitment.",
        source_id="src-book",
    )
    c_apa = _claim(
        "c_apa",
        "Carlsen, C. J., Lindahl, N., & Lindahl, S. (2004). Service learning in civic commitment programs. Journal for Civic Commitment, 4, 1-9.",
        source_id="src-book",
    )
    batch = MappedBatch(
        source_document=src,
        entities=[ent_ch, ent_jcc],
        claims=[c_para_1, c_para_2, c_narr, c_apa],
        relations=[
            Relation(
                relation_id="r1", source_id="c_p1", target_id="ent_ch", relation_type="MENTIONS"
            ),
            Relation(
                relation_id="r2", source_id="c_p2", target_id="ent_ch", relation_type="MENTIONS"
            ),
            Relation(
                relation_id="r3", source_id="c_narr", target_id="ent_jcc", relation_type="MENTIONS"
            ),
            Relation(
                relation_id="r4", source_id="c_apa", target_id="ent_jcc", relation_type="MENTIONS"
            ),
        ],
    )
    layer = KnowledgeReducer().reduce_batches(
        [batch],
        layer_id="lossless-test",
        layer_name="Lossless Test",
        strict_validation=True,
    )
    statements = [c.statement for c in layer.claims]
    assert len(statements) == 3
    assert any("Carlsen, C. J." in s for s in statements)
    assert any("I was honored to submit" in s for s in statements)
