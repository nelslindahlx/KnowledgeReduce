"""Unit tests for cross-type entity disambiguation and initial-based person resolution."""

from __future__ import annotations

from knowledgereduce.models import (
    Claim,
    Entity,
    Evidence,
    KnowledgeLayer,
    LayerData,
    LayerTier,
    MappedBatch,
    MergeMode,
    Relation,
    SourceDocument,
)
from knowledgereduce.resolve import resolve_entities_and_remap
from knowledgereduce.stack import StackManager
from knowledgereduce.storage import MemoryGraphStore


def test_resolve_entities_merges_exact_cross_type_with_specificity_priority() -> None:
    batch_gpe = MappedBatch(
        source_document=SourceDocument(source_id="s1", uri="https://a.example", content="x"),
        entities=[
            Entity(
                entity_id="ent_ny_gpe",
                canonical_name="New York",
                entity_type="GPE",
                evidence=[Evidence(source_id="s1", excerpt="New York, NY")],
            ),
            Entity(
                entity_id="ent_year_date",
                canonical_name="2006",
                entity_type="DATE",
                evidence=[Evidence(source_id="s1", excerpt="published in 2006")],
            ),
        ],
        claims=[
            Claim(
                claim_id="clm_1",
                statement="Published in New York in 2006.",
                subject_id="ent_ny_gpe",
                predicate="MENTIONS_YEAR",
                object_id="ent_year_date",
                source_id="s1",
            )
        ],
        relations=[
            Relation(
                relation_id="rel_1",
                source_id="clm_1",
                target_id="ent_ny_gpe",
                relation_type="MENTIONS",
            )
        ],
    )
    batch_person_noise = MappedBatch(
        source_document=SourceDocument(source_id="s2", uri="https://b.example", content="y"),
        entities=[
            Entity(
                entity_id="ent_ny_person",
                canonical_name="New York",
                entity_type="PERSON",
                evidence=[
                    Evidence(source_id="s2", excerpt="New York: Random House"),
                    Evidence(source_id="s2", excerpt="New York: Free Press"),
                ],
            ),
            Entity(
                entity_id="ent_2006_concept",
                canonical_name="2006",
                entity_type="CONCEPT",
                evidence=[Evidence(source_id="s2", excerpt="Edition 2006")],
            ),
        ],
        claims=[
            Claim(
                claim_id="clm_2",
                statement="Random House is in New York.",
                subject_id="ent_ny_person",
                predicate="CITY",
                object_literal="New York",
                source_id="s2",
            )
        ],
        relations=[
            Relation(
                relation_id="rel_2",
                source_id="clm_2",
                target_id="ent_ny_person",
                relation_type="MENTIONS",
            )
        ],
    )

    entities, claims, relations, _sources, id_map = resolve_entities_and_remap(
        [batch_gpe, batch_person_noise]
    )
    ny_entities = [e for e in entities if e.canonical_name == "New York"]
    assert len(ny_entities) == 1
    assert ny_entities[0].entity_type == "GPE"
    assert len(ny_entities[0].evidence) == 3
    assert id_map["ent_ny_person"] == "ent_ny_gpe"
    assert all(c.subject_id == "ent_ny_gpe" for c in claims)
    assert all(r.target_id == "ent_ny_gpe" for r in relations)

    date_entities = [e for e in entities if e.canonical_name == "2006"]
    assert len(date_entities) == 1
    assert date_entities[0].entity_type == "DATE"

    # Opt-out preserves cross-type separation between non-CONCEPT types.
    separated, _, _, _, _ = resolve_entities_and_remap(
        [batch_gpe, batch_person_noise], merge_exact_cross_type=False
    )
    assert len([e for e in separated if e.canonical_name == "New York"]) == 2


def test_resolve_entities_matches_middle_and_leading_initials_and_rejects_distinct_names() -> None:
    batch = MappedBatch(
        source_document=SourceDocument(source_id="s_init", uri="https://a.example", content="x"),
        entities=[
            Entity(
                entity_id="e_c1",
                canonical_name="Charles Carlsen",
                entity_type="PERSON",
                evidence=[Evidence(source_id="s_init", excerpt="Charles Carlsen")],
            ),
            Entity(
                entity_id="e_c2",
                canonical_name="Dr. Charles J. Carlsen",
                entity_type="PERSON",
                evidence=[
                    Evidence(source_id="s_init", excerpt="Dr. Charles J. Carlsen"),
                    Evidence(source_id="s_init", excerpt="Carlsen 2004"),
                ],
            ),
            Entity(
                entity_id="e_f1",
                canonical_name="George Frederickson",
                entity_type="PERSON",
                evidence=[Evidence(source_id="s_init", excerpt="George Frederickson")],
            ),
            Entity(
                entity_id="e_f2",
                canonical_name="H. George Frederickson",
                entity_type="PERSON",
                evidence=[
                    Evidence(source_id="s_init", excerpt="H. George Frederickson"),
                    Evidence(source_id="s_init", excerpt="Dr. H. George Frederickson"),
                ],
            ),
            Entity(
                entity_id="e_nels",
                canonical_name="Nels Lindahl",
                entity_type="PERSON",
                evidence=[Evidence(source_id="s_init", excerpt="Nels Lindahl")],
            ),
            Entity(
                entity_id="e_susan",
                canonical_name="Susan Lindahl",
                entity_type="PERSON",
                evidence=[Evidence(source_id="s_init", excerpt="Susan Lindahl")],
            ),
        ],
    )

    entities, _, _, _, id_map = resolve_entities_and_remap([batch])
    assert id_map["e_c1"] == id_map["e_c2"]
    assert id_map["e_f1"] == id_map["e_f2"]
    assert id_map["e_nels"] != id_map["e_susan"]
    assert len(entities) == 4


def test_stack_reconcile_merges_cross_type_exact_names_without_dangling_edges() -> None:
    store = MemoryGraphStore()
    layer_org = LayerData(
        layer=KnowledgeLayer(layer_id="layer-org", name="Layer ORG", tier=LayerTier.REDUCED),
        entities=[
            Entity(
                entity_id="e_pr_org",
                canonical_name="Prentice Hall",
                entity_type="ORG",
                evidence=[Evidence(source_id="s1", excerpt="Prentice Hall")],
            )
        ],
        claims=[
            Claim(
                claim_id="c_org",
                statement="Prentice Hall published leadership guides.",
                subject_id="e_pr_org",
                predicate="PUBLISHED",
                object_literal="leadership guides",
                evidence=[Evidence(source_id="s1", excerpt="Prentice Hall")],
            )
        ],
        relations=[
            Relation(
                relation_id="r_org",
                source_id="c_org",
                target_id="e_pr_org",
                relation_type="MENTIONS",
            )
        ],
    )
    layer_person_noise = LayerData(
        layer=KnowledgeLayer(layer_id="layer-per", name="Layer PER", tier=LayerTier.REDUCED),
        entities=[
            Entity(
                entity_id="e_pr_person",
                canonical_name="Prentice Hall",
                entity_type="PERSON",
                evidence=[Evidence(source_id="s2", excerpt="NJ: Prentice Hall.")],
            )
        ],
        claims=[
            Claim(
                claim_id="c_per",
                statement="Upper Saddle River, NJ: Prentice Hall.",
                evidence=[Evidence(source_id="s2", excerpt="NJ: Prentice Hall.")],
            )
        ],
        relations=[
            Relation(
                relation_id="r_per",
                source_id="c_per",
                target_id="e_pr_person",
                relation_type="MENTIONS",
            )
        ],
    )
    store.save_layer(layer_org)
    store.save_layer(layer_person_noise)

    reconciled = StackManager(store).merge_layers(
        ["layer-org", "layer-per"],
        target_layer_id="merged-reconciled",
        mode=MergeMode.UNION,
        reconcile=True,
    )
    assert len(reconciled.entities) == 1
    winner = reconciled.entities[0]
    assert winner.canonical_name == "Prentice Hall"
    assert winner.entity_type == "ORG"
    valid_nodes = {winner.entity_id} | {c.claim_id for c in reconciled.claims}
    assert all(
        r.source_id in valid_nodes and r.target_id in valid_nodes for r in reconciled.relations
    )
    assert all(r.target_id == winner.entity_id for r in reconciled.relations)
