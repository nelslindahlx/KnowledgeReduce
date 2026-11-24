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
        "run_local_map",
        "submit_mapped_batch",
        "resolve_and_reduce",
        "stack_layers",
        "diff_layers",
        "query_knowledge_graph",
        "list_conflicts",
        "resolve_conflict",
        "export_layer",
        "validate_layer",
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
        ("parquet", "exports/parquet_copy"),
    ]:
        exp_res = await server.call_tool(
            "export_layer",
            {"layer_id": "ch-curated", "format": fmt, "output_path": out_rel},
        )
        assert not exp_res.is_error
        assert (ws / out_rel).exists()

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


async def test_mcp_stdio_subprocess_initialize_and_list_tools(tmp_path: Path) -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "knowledgereduce.cli", "mcp", "--workspace", str(tmp_path)],
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        init = await session.initialize()
        assert init.server_info.name == "knowledgereduce"
        tools_res = await session.list_tools()
        assert len(tools_res.tools) == 11
