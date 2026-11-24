"""Example 2: Immutable layer stacking (overlay, union, intersection, difference) & conflicts."""

from __future__ import annotations

import tempfile
from pathlib import Path

from knowledgereduce import (
    Claim,
    ConflictStrategy,
    DuckDBParquetStore,
    Entity,
    Evidence,
    KnowledgeLayer,
    LayerData,
    LayerTier,
    MergeMode,
    Relation,
    ReliabilityRating,
    StackManager,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = DuckDBParquetStore(Path(tmp) / "store")
        mgr = StackManager(store)

        base_layer = LayerData(
            layer=KnowledgeLayer(layer_id="base", name="Base Civic Corpus", tier=LayerTier.REDUCED),
            entities=[
                Entity(entity_id="ent_ch", canonical_name="Civic Honors", entity_type="ORG"),
                Entity(
                    entity_id="ent_ku", canonical_name="University of Kansas", entity_type="ORG"
                ),
            ],
            claims=[
                Claim(
                    claim_id="clm_pub",
                    statement="Civic Honors was published in 2006.",
                    category="Publication",
                    tags=["civic", "history"],
                    reliability=ReliabilityRating.LIKELY_TRUE,
                    source_id="archive_2006",
                    evidence=[Evidence(source_id="archive_2006", excerpt="published in 2006")],
                ),
                Claim(
                    claim_id="clm_ku",
                    statement="University of Kansas is in Lawrence, Kansas.",
                    category="Geography",
                    tags=["ku"],
                    reliability=ReliabilityRating.VERIFIED,
                    source_id="archive_2006",
                    evidence=[Evidence(source_id="archive_2006", excerpt="Lawrence, Kansas")],
                ),
            ],
            relations=[
                Relation(
                    relation_id="rel_1",
                    source_id="clm_pub",
                    target_id="ent_ch",
                    relation_type="MENTIONS",
                ),
                Relation(
                    relation_id="rel_2",
                    source_id="clm_ku",
                    target_id="ent_ku",
                    relation_type="MENTIONS",
                ),
            ],
        )

        patch_layer = LayerData(
            layer=KnowledgeLayer(layer_id="patch", name="2020 Web Update", tier=LayerTier.CURATED),
            entities=[
                Entity(entity_id="ent_ch", canonical_name="Civic Honors", entity_type="ORG"),
                Entity(entity_id="ent_nels", canonical_name="Nels Lindahl", entity_type="PERSON"),
            ],
            claims=[
                Claim(
                    claim_id="clm_pub",
                    statement="Civic Honors was republished online in 2020.",
                    category="Publication",
                    tags=["online"],
                    reliability=ReliabilityRating.VERIFIED,
                    source_id="web_2020",
                    evidence=[Evidence(source_id="web_2020", excerpt="online in 2020")],
                )
            ],
            relations=[
                Relation(
                    relation_id="rel_3",
                    source_id="ent_nels",
                    target_id="ent_ch",
                    relation_type="AUTHORED",
                )
            ],
        )

        store.save_layer(base_layer)
        store.save_layer(patch_layer)

        overlay = mgr.stack_overlay(
            "base",
            "patch",
            target_layer_id="stacked-overlay",
            conflict_strategy=ConflictStrategy.PRESERVE_DISPUTE,
        )
        union_layer = mgr.merge_layers(
            ["base", "patch"], target_layer_id="stacked-union", mode=MergeMode.UNION
        )
        inter_layer = mgr.merge_layers(
            ["base", "patch"], target_layer_id="stacked-inter", mode=MergeMode.INTERSECTION
        )
        diff_layer = mgr.merge_layers(
            ["base", "patch"], target_layer_id="stacked-diff", mode=MergeMode.DIFFERENCE
        )
        structural_diff = mgr.diff_layers("base", "stacked-overlay")

        assert len(overlay.conflicts) == 1
        assert overlay.conflicts[0].needs_review is True
        assert len(union_layer.entities) == 3
        assert [e.entity_id for e in inter_layer.entities] == ["ent_ch"]
        assert [e.entity_id for e in diff_layer.entities] == ["ent_ku"]
        assert "stacked-overlay" in mgr.get_descendants("base")

        print("Overlay stats:", overlay.layer.stats)
        print("Structural diff added entities:", structural_diff.added_entity_ids)


if __name__ == "__main__":
    main()
