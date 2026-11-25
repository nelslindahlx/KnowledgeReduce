"""Integration tests for the Antigravity-compatible stdio MCP server."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import httpx
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server.mcpserver.exceptions import ToolError

from knowledgereduce.mcp import create_mcp_server

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _public_dns(_host: str, _port: int) -> list[str]:
    return ["93.184.216.34"]


async def test_mcp_full_agent_in_the_loop_workflow(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    ws.mkdir()
    shutil.copy(FIXTURES_DIR / "civichonors_facts.csv", ws / "civichonors_facts.csv")
    book_html = (FIXTURES_DIR / "civichonors_book.html").read_text(encoding="utf-8")

    def transport_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, text=book_html, headers={"content-type": "text/html"})

    server = create_mcp_server(
        ws,
        web_transport=httpx.MockTransport(transport_handler),
        dns_resolver=_public_dns,
    )

    tools = await server.list_tools()
    tool_names = {t.name for t in tools}
    assert tool_names == {
        "ingest_source",
        "read_ingested_checkpoint",
        "run_local_map",
        "submit_mapped_batch",
        "resolve_and_reduce",
        "stack_layers",
        "diff_layers",
        "query_knowledge_graph",
        "list_conflicts",
        "resolve_conflict",
        "resolve_conflicts",
        "export_layer",
        "validate_layer",
        "list_layers",
        "get_layer_lineage",
        "analyze_graph",
        "inspect_entity",
    }

    # 1. Ingest local CSV + mocked web page
    ing_res = await server.call_tool(
        "ingest_source",
        {
            "local_files": [
                {"path": "civichonors_facts.csv", "source_id": "csv_curated", "trust_weight": 0.95}
            ],
            "crawl_config": {
                "seed_urls": ["https://civichonors.com/p/the-book"],
                "max_depth": 0,
                "rate_limit_seconds": 0.0,
                "trust_weight": 0.6,
            },
        },
    )
    assert not ing_res.is_error
    ing_data = json.loads(ing_res.content[0].text)  # type: ignore[union-attr]
    assert ing_data["document_count"] == 2

    # 2. Run local mapper
    map_res = await server.call_tool("run_local_map", {})
    assert not map_res.is_error
    assert json.loads(map_res.content[0].text)["batch_count"] == 2  # type: ignore[union-attr]

    # 3. Antigravity agent injects an additional high-precision MappedBatch (with a dispute!)
    submit_res = await server.call_tool(
        "submit_mapped_batch",
        {
            "batches": [
                {
                    "source_document": {
                        "source_id": "antigravity_review",
                        "uri": "agent://antigravity/session-1",
                        "source_type": "agent",
                        "title": "Antigravity Verification",
                        "content": "Civic Honors was published in 2006.",
                        "trust_weight": 0.98,
                    },
                    "entities": [
                        {
                            "entity_id": "ent_ag_ch",
                            "canonical_name": "Civic Honors",
                            "entity_type": "ORG",
                            "evidence": [
                                {
                                    "source_id": "antigravity_review",
                                    "excerpt": "Civic Honors",
                                    "extractor_name": "antigravity_agent",
                                }
                            ],
                        }
                    ],
                    "claims": [
                        {
                            "claim_id": "clm_ag_1",
                            "statement": "Civic Honors was published in 2006.",
                            "category": "Publication",
                            "tags": ["verified", "civic"],
                            "reliability": 4,
                            "source_id": "antigravity_review",
                            "subject_id": "ent_ag_ch",
                            "predicate": "PUBLISHED_IN",
                            "object_literal": "2006",
                            "evidence": [
                                {
                                    "source_id": "antigravity_review",
                                    "excerpt": "Civic Honors was published in 2006.",
                                    "extractor_name": "antigravity_agent",
                                }
                            ],
                        }
                    ],
                    "relations": [
                        {
                            "relation_id": "rel_ag_1",
                            "source_id": "clm_ag_1",
                            "target_id": "ent_ag_ch",
                            "relation_type": "MENTIONS",
                        }
                    ],
                }
            ],
            "append": True,
        },
    )
    assert not submit_res.is_error
    assert json.loads(submit_res.content[0].text)["total_batches"] == 3  # type: ignore[union-attr]

    # 4. Reduce into DuckDB + Parquet layer
    red_res = await server.call_tool(
        "resolve_and_reduce",
        {"layer_id": "ch-base", "layer_name": "Civic Honors Base"},
    )
    assert not red_res.is_error

    # 5. Validate layer
    val_res = await server.call_tool("validate_layer", {"layer_id": "ch-base"})
    assert json.loads(val_res.content[0].text)["valid"] is True  # type: ignore[union-attr]

    # 6. List conflicts & adjudicate non-destructively into a CURATED child layer
    cf_res = await server.call_tool("list_conflicts", {"layer_id": "ch-base"})
    cf_payload = json.loads(cf_res.content[0].text)  # type: ignore[union-attr]
    assert cf_payload["count"] >= 1
    conflict_id = cf_payload["conflicts"][0]["conflict_id"]

    adj_res = await server.call_tool(
        "resolve_conflict",
        {
            "base_layer_id": "ch-base",
            "conflict_id": conflict_id,
            "target_layer_id": "ch-curated",
            "winning_value": "2006",
            "resolution_notes": "Confirmed 2006 original print copyright.",
        },
    )
    assert not adj_res.is_error
    adj_data = json.loads(adj_res.content[0].text)  # type: ignore[union-attr]
    assert adj_data["resolved_conflict"]["needs_review"] is False
    assert adj_data["layer"]["tier"] == "curated"

    # 7. Stack & diff layers
    stack_res = await server.call_tool(
        "stack_layers",
        {
            "layer_ids": ["ch-base", "ch-curated"],
            "target_layer_id": "ch-stacked",
            "mode": "overlay",
            "reconcile": True,
        },
    )
    assert not stack_res.is_error

    diff_res = await server.call_tool(
        "diff_layers",
        {"left_layer_id": "ch-base", "right_layer_id": "ch-curated"},
    )
    diff_data = json.loads(diff_res.content[0].text)  # type: ignore[union-attr]
    assert conflict_id in diff_data["resolved_conflict_ids"]

    # 8. Query via Hybrid GraphRAG & structured filters
    q_res = await server.call_tool(
        "query_knowledge_graph",
        {"layer_id": "ch-curated", "query": "Civic Honors 2006", "top_k": 3, "hops": 1},
    )
    assert len(json.loads(q_res.content[0].text)["results"]) > 0  # type: ignore[union-attr]

    q_tag = await server.call_tool(
        "query_knowledge_graph",
        {"layer_id": "ch-curated", "tag": "civic", "min_reliability": 4},
    )
    assert len(json.loads(q_tag.content[0].text)["claims"]) >= 1  # type: ignore[union-attr]

    # 9. Export in all formats inside workspace
    for fmt, out_rel in [
        ("json", "exports/ch.json"),
        ("sharded_jsonl", "exports/sharded"),
        ("graphml", "exports/ch.graphml"),
        ("gexf", "exports/ch.gexf"),
        ("markdown", "exports/ch.md"),
        ("parquet", "exports/parquet_copy"),
    ]:
        exp_res = await server.call_tool(
            "export_layer",
            {"layer_id": "ch-curated", "format": fmt, "output_path": out_rel},
        )
        assert not exp_res.is_error
        assert (ws / out_rel).exists()

    md_text = (ws / "exports/ch.md").read_text(encoding="utf-8")
    assert "## Key Claims" in md_text

    # 9b. Layer catalog, lineage inspection, and graph analytics tools
    layers_res = await server.call_tool("list_layers", {})
    layers_payload = json.loads(layers_res.content[0].text)  # type: ignore[union-attr]
    assert layers_payload["count"] == 3
    assert {item["layer_id"] for item in layers_payload["layers"]} == {
        "ch-base",
        "ch-curated",
        "ch-stacked",
    }

    lineage_res = await server.call_tool("get_layer_lineage", {"layer_id": "ch-stacked"})
    lineage_payload = json.loads(lineage_res.content[0].text)  # type: ignore[union-attr]
    assert "ch-base" in lineage_payload["ancestors"]
    assert "ch-curated" in lineage_payload["ancestors"]

    analytics_res = await server.call_tool(
        "analyze_graph",
        {"layer_id": "ch-curated", "metric": "pagerank", "top_k": 5, "include_communities": True},
    )
    analytics_payload = json.loads(analytics_res.content[0].text)  # type: ignore[union-attr]
    assert analytics_payload["node_count"] > 0
    assert len(analytics_payload["central_nodes"]) > 0
    assert analytics_payload["community_count"] >= 1

    with pytest.raises(ToolError, match="Unsupported centrality metric"):
        await server.call_tool(
            "analyze_graph",
            {"layer_id": "ch-curated", "metric": "eigenvalue"},
        )

    # 10. Path traversal & validation errors must fail inside MCP server with actionable ToolError
    with pytest.raises(ToolError, match="escapes"):
        await server.call_tool(
            "export_layer",
            {"layer_id": "ch-curated", "format": "json", "output_path": "../escape.json"},
        )

    with pytest.raises(ToolError, match="Extra inputs are not permitted"):
        await server.call_tool(
            "submit_mapped_batch",
            {"batches": [{"source_id": "extra"}]},
        )

    with pytest.raises(ToolError, match="ConflictStrategy"):
        await server.call_tool(
            "resolve_and_reduce",
            {"layer_id": "bad-enum", "layer_name": "Bad", "conflict_strategy": "invalid"},
        )

    with pytest.raises(ToolError, match="ReliabilityRating"):
        await server.call_tool(
            "query_knowledge_graph",
            {"layer_id": "ch-curated", "min_reliability": 99},
        )

    # 11. Incremental ingest parity, parent_layer_ids, and pre-warmed claim_embeddings.parquet
    assert (
        ws / ".knowledgereduce_store" / "layers" / "ch-base" / "claim_embeddings.parquet"
    ).is_file()
    assert (
        ws / ".knowledgereduce_store" / "layers" / "ch-stacked" / "claim_embeddings.parquet"
    ).is_file()

    (ws / "extra.html").write_text(
        "<html><head><title>Extra</title></head><body><main>"
        "<p>Johnson County Community College expanded civic service opportunities in 2005.</p>"
        "</main></body></html>",
        encoding="utf-8",
    )
    inc_res = await server.call_tool(
        "ingest_source",
        {
            "local_files": [
                {"path": "civichonors_facts.csv", "source_id": "csv_curated"},
                {"path": "extra.html", "source_id": "html_extra"},
            ],
            "crawl_config": {
                "seed_urls": ["https://civichonors.com/p/the-book"],
                "max_depth": 0,
                "rate_limit_seconds": 0.0,
            },
            "checkpoint_name": "01_inc.jsonl",
            "incremental_from_layer": "ch-base",
        },
    )
    assert not inc_res.is_error
    inc_data = json.loads(inc_res.content[0].text)  # type: ignore[union-attr]
    assert inc_data["skipped_unchanged"] == 2
    assert inc_data["document_count"] == 1
    assert inc_data["source_ids"] == ["html_extra"]

    map_inc = await server.call_tool(
        "run_local_map",
        {"ingested_checkpoint": "01_inc.jsonl", "mapped_checkpoint": "02_inc.jsonl"},
    )
    assert not map_inc.is_error
    red_inc = await server.call_tool(
        "resolve_and_reduce",
        {
            "layer_id": "ch-inc-child",
            "layer_name": "Incremental Child",
            "mapped_checkpoint": "02_inc.jsonl",
            "parent_layer_ids": ["ch-base"],
            "build_embeddings_index": True,
        },
    )
    assert not red_inc.is_error
    red_inc_data = json.loads(red_inc.content[0].text)  # type: ignore[union-attr]
    assert red_inc_data["parent_layer_ids"] == ["ch-base"]
    assert (
        ws / ".knowledgereduce_store" / "layers" / "ch-inc-child" / "claim_embeddings.parquet"
    ).is_file()

    # 12. v1.6.0 MCP tools: read_ingested_checkpoint, inspect_entity, resolve_conflicts,
    # directory ingest, skip_headings/skip_questions, deduplicate_claims, resources & prompts
    read_page_1 = await server.call_tool(
        "read_ingested_checkpoint",
        {"checkpoint_name": "01_ingested.jsonl", "offset": 0, "limit": 1, "max_chars_per_doc": 120},
    )
    page_1_data = json.loads(read_page_1.content[0].text)  # type: ignore[union-attr]
    assert page_1_data["total_documents"] == 2
    assert page_1_data["returned_count"] == 1
    assert page_1_data["has_more"] is True
    assert len(page_1_data["documents"][0]["content"]) <= 120

    read_filtered = await server.call_tool(
        "read_ingested_checkpoint",
        {"checkpoint_name": "01_ingested.jsonl", "source_id": "csv_curated"},
    )
    filtered_data = json.loads(read_filtered.content[0].text)  # type: ignore[union-attr]
    assert filtered_data["total_documents"] == 1
    assert filtered_data["documents"][0]["source_id"] == "csv_curated"

    for bad_read_args in [
        {"offset": -1},
        {"limit": 0},
        {"max_chars_per_doc": 10},
        {"checkpoint_name": "../escape.jsonl"},
    ]:
        with pytest.raises(ToolError):
            await server.call_tool("read_ingested_checkpoint", bad_read_args)

    insp_res = await server.call_tool(
        "inspect_entity",
        {"layer_id": "ch-base", "entity_id_or_name": "civic honors", "max_claims": 5},
    )
    insp_data = json.loads(insp_res.content[0].text)  # type: ignore[union-attr]
    assert insp_data["entity"]["canonical_name"] == "Civic Honors"
    assert insp_data["total_linked_claims"] >= 1
    assert insp_data["conflict_count"] >= 1

    with pytest.raises(ToolError, match="not found"):
        await server.call_tool(
            "inspect_entity", {"layer_id": "ch-base", "entity_id_or_name": "NoSuchEntityXYZ"}
        )

    batch_cf_res = await server.call_tool(
        "resolve_conflicts",
        {
            "base_layer_id": "ch-base",
            "target_layer_id": "ch-batch-curated",
            "resolutions": [
                {
                    "conflict_id": conflict_id,
                    "winning_value": "2006",
                    "resolution_notes": "Batch adjudicated.",
                }
            ],
        },
    )
    batch_cf_data = json.loads(batch_cf_res.content[0].text)  # type: ignore[union-attr]
    assert batch_cf_data["resolved_count"] == 1
    assert batch_cf_data["layer"]["tier"] == "curated"

    notes_dir = ws / "notes_corpus"
    notes_dir.mkdir()
    (notes_dir / "civic.md").write_text(
        "---\ndate: 2025-02-01\ntags: [directory, mcp]\n---\n\n"
        "Directory Heading Without Punctuation\n"
        "Can directory ingestion feed local mapping?\n"
        "Civic Honors collaborated with Kansas educators during campus programs.\n",
        encoding="utf-8",
    )
    dir_ing = await server.call_tool(
        "ingest_source",
        {
            "local_directories": [{"path": "notes_corpus", "patterns": ["*.md"]}],
            "checkpoint_name": "01_dir.jsonl",
        },
    )
    assert json.loads(dir_ing.content[0].text)["document_count"] == 1  # type: ignore[union-attr]

    dir_map = await server.call_tool(
        "run_local_map",
        {
            "ingested_checkpoint": "01_dir.jsonl",
            "mapped_checkpoint": "02_dir.jsonl",
            "skip_headings": False,
            "skip_questions": False,
        },
    )
    assert json.loads(dir_map.content[0].text)["claims"] >= 2  # type: ignore[union-attr]

    dedup_stack = await server.call_tool(
        "stack_layers",
        {
            "layer_ids": ["ch-base", "ch-inc-child"],
            "target_layer_id": "ch-union-dedup",
            "mode": "union",
            "reconcile": True,
            "deduplicate_claims": True,
        },
    )
    assert not dedup_stack.is_error

    resources = await server.list_resources()
    assert {str(r.uri) for r in resources} == {"kr://layers"}
    templates = await server.list_resource_templates()
    assert {t.uri_template for t in templates} == {
        "kr://layers/{layer_id}/manifest",
        "kr://layers/{layer_id}/conflicts",
    }

    layers_res_read = await server.read_resource("kr://layers")
    assert json.loads(layers_res_read[0].content)["count"] >= 4  # type: ignore[arg-type]
    manifest_res_read = await server.read_resource("kr://layers/ch-base/manifest")
    assert json.loads(manifest_res_read[0].content)["layer_id"] == "ch-base"  # type: ignore[arg-type]
    conflicts_res_read = await server.read_resource("kr://layers/ch-base/conflicts")
    assert json.loads(conflicts_res_read[0].content)["count"] >= 1  # type: ignore[arg-type]

    prompts = await server.list_prompts()
    assert {p.name for p in prompts} == {"extract_mapped_batch", "adjudicate_conflicts"}
    extract_prompt = await server.get_prompt(
        "extract_mapped_batch", {"checkpoint_path": "01_inc.jsonl", "source_id": "html_extra"}
    )
    assert "01_inc.jsonl" in extract_prompt.messages[0].content.text  # type: ignore[union-attr]
    adj_prompt = await server.get_prompt("adjudicate_conflicts", {"layer_id": "ch-base"})
    assert "resolve_conflicts" in adj_prompt.messages[0].content.text  # type: ignore[union-attr]


async def test_mcp_stdio_subprocess_initialize_and_list_tools(tmp_path: Path) -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "knowledgereduce.cli", "mcp", "--workspace", str(tmp_path)],
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        init = await session.initialize()
        assert init.server_info.name == "knowledgereduce"
        tools_res = await session.list_tools()
        assert len(tools_res.tools) == 17
