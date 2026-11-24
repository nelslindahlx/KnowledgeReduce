"""Example 3: Hybrid GraphRAG retrieval, graph analytics, and lossless portable exports."""

from __future__ import annotations

import tempfile
from pathlib import Path

from knowledgereduce import (
    Claim,
    DuckDBParquetStore,
    Entity,
    Evidence,
    HybridGraphRAGRetriever,
    KnowledgeLayer,
    LayerData,
    QueryBuilder,
    Relation,
    ReliabilityRating,
    bounded_shortest_path,
    central_nodes,
    detect_communities,
    k_hop_neighborhood,
)
from knowledgereduce.export import (
    export_gexf,
    export_graphml,
    export_layer_json,
    export_layer_sharded,
    import_layer_sharded,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        store = DuckDBParquetStore(tmp_path / "store")

        layer_data = LayerData(
            layer=KnowledgeLayer(layer_id="graphrag-demo", name="GraphRAG Demo"),
            entities=[
                Entity(entity_id="ent_nels", canonical_name="Nels Lindahl", entity_type="PERSON"),
                Entity(entity_id="ent_ch", canonical_name="Civic Honors", entity_type="ORG"),
                Entity(
                    entity_id="ent_ku", canonical_name="University of Kansas", entity_type="ORG"
                ),
            ],
            claims=[
                Claim(
                    claim_id="clm_1",
                    statement="Nels Lindahl authored Civic Honors in 2006.",
                    category="Biography",
                    tags=["civic", "book"],
                    reliability=ReliabilityRating.VERIFIED,
                    evidence=[Evidence(source_id="src_1", excerpt="authored Civic Honors")],
                ),
                Claim(
                    claim_id="clm_2",
                    statement="Nels Lindahl studied public administration at the University of Kansas.",
                    category="Education",
                    tags=["ku", "academic"],
                    reliability=ReliabilityRating.LIKELY_TRUE,
                    evidence=[Evidence(source_id="src_1", excerpt="University of Kansas")],
                ),
            ],
            relations=[
                Relation(
                    relation_id="rel_1",
                    source_id="clm_1",
                    target_id="ent_nels",
                    relation_type="MENTIONS",
                ),
                Relation(
                    relation_id="rel_2",
                    source_id="clm_1",
                    target_id="ent_ch",
                    relation_type="MENTIONS",
                ),
                Relation(
                    relation_id="rel_3",
                    source_id="clm_2",
                    target_id="ent_nels",
                    relation_type="MENTIONS",
                ),
                Relation(
                    relation_id="rel_4",
                    source_id="clm_2",
                    target_id="ent_ku",
                    relation_type="MENTIONS",
                ),
            ],
        )
        store.save_layer(layer_data)

        # Structured QueryBuilder
        verified = (
            QueryBuilder(store, "graphrag-demo")
            .filter_min_reliability(ReliabilityRating.VERIFIED)
            .filter_tag("civic")
            .execute_claims()
        )
        assert [c.claim_id for c in verified] == ["clm_1"]

        # NetworkX analytics
        graph = store.to_networkx("graphrag-demo")
        sub = k_hop_neighborhood(graph, "ent_nels", k=1)
        path = bounded_shortest_path(graph, "ent_ch", "ent_ku", max_hops=4)
        top_nodes = central_nodes(graph, metric="pagerank", top_k=3)
        communities = detect_communities(graph)
        assert sub.number_of_nodes() == 3
        assert path == ["ent_ch", "clm_1", "ent_nels", "clm_2", "ent_ku"]

        # Hybrid GraphRAG
        ctx = HybridGraphRAGRetriever(store).retrieve(
            "graphrag-demo", "Civic Honors author", top_k=2, hops=1
        )
        assert len(ctx.results) > 0

        # Portable exports (JSON, lossless sharded JSONL, GraphML, GEXF)
        json_path = export_layer_json(layer_data, tmp_path / "exports" / "demo.json")
        shard_dir = export_layer_sharded(layer_data, tmp_path / "exports" / "shards", shard_size=1)
        restored = import_layer_sharded(shard_dir)
        gml_path = export_graphml(layer_data, tmp_path / "exports" / "demo.graphml")
        gexf_path = export_gexf(layer_data, tmp_path / "exports" / "demo.gexf")

        assert json_path.is_file()
        assert len(restored.relations) == len(layer_data.relations)
        assert gml_path.is_file() and gexf_path.is_file()

        print("Top PageRank nodes:", top_nodes)
        print("Communities:", communities)
        print("GraphRAG top hit:", ctx.results[0].claim.statement)


if __name__ == "__main__":
    main()
