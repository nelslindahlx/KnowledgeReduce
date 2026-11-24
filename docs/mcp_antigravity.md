# Antigravity MCP Server Guide (`stdio`)

KnowledgeReduce ships a built-in **Model Context Protocol (`mcp>=2.0`)** server (`kr mcp`) that exposes the entire reduction, stacking, querying, and conflict-adjudication pipeline directly to **Antigravity** over `stdio`.

This enables **zero-API-key LLM-quality extraction**: Antigravity can read complex documents from `01_ingested.jsonl`, submit high-precision `Entity`/`Claim`/`Relation` graphs via `submit_mapped_batch`, trigger deterministic resolution and reduction, and adjudicate open conflicts non-destructively into `CURATED` child layers.

---

## 1. Antigravity `mcp_config.json` Setup

Add the following entry to your Antigravity MCP server configuration:

```json
{
  "mcpServers": {
    "knowledgereduce": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/KnowledgeReduce",
        "kr",
        "mcp",
        "--workspace",
        "/path/to/your/project_workspace"
      ]
    }
  }
}
```

Or if `knowledgereduce` is installed directly into a virtual environment:

```json
{
  "mcpServers": {
    "knowledgereduce": {
      "command": "/path/to/.venv/bin/kr",
      "args": [
        "mcp",
        "--workspace",
        "/path/to/your/project_workspace",
        "--store-dir",
        ".knowledgereduce_store",
        "--checkpoint-dir",
        ".knowledgereduce_checkpoints"
      ]
    }
  }
}
```

All file paths passed to MCP tools are strictly sandboxed inside `--workspace` via `ensure_within_base`. All `structlog` telemetry routes to `stderr` so `stdout` stays clean JSON-RPC.

---

## 2. Exposed Tools (11 Tools)

| Tool | Role | Key Arguments |
|---|---|---|
| `ingest_source` | Crawl URLs (SSRF-safe) or read local CSV/JSON/MD/TXT files into `01_ingested.jsonl` | `local_files`, `crawl_config`, `checkpoint_name` |
| `run_local_map` | Run local `deterministic`, `structured`, or `spacy` mapper into `02_mapped.jsonl` | `ingested_checkpoint`, `mapped_checkpoint`, `mapper` |
| `submit_mapped_batch` | Inject Antigravity-extracted `MappedBatch` objects directly into `02_mapped.jsonl` | `batches`, `mapped_checkpoint`, `append` |
| `resolve_and_reduce` | Entity resolution, 3-stage dedup, conflict detection, integrity gate → Parquet layer | `layer_id`, `layer_name`, `mapped_checkpoint`, `conflict_strategy` |
| `stack_layers` | Compose layers via `overlay`, `union`, `intersection`, or `difference` (with optional cross-layer `reconcile`) | `layer_ids`, `target_layer_id`, `mode`, `conflict_strategy`, `reconcile` |
| `diff_layers` | Compute added/removed/modified entities, claims, relations, and resolved conflicts | `left_layer_id`, `right_layer_id` |
| `query_knowledge_graph` | Hybrid GraphRAG semantic+lexical+graph search or structured tag/category/reliability queries | `layer_id`, `query`, `category`, `tag`, `min_reliability`, `top_k`, `hops` |
| `list_conflicts` | Inspect unresolved (`needs_review=True`) or historical `ConflictRecord`s | `layer_id`, `needs_review_only`, `limit` |
| `resolve_conflict` | Adjudicate a conflict non-destructively into a new immutable `CURATED` child layer | `base_layer_id`, `conflict_id`, `target_layer_id`, `winning_value` |
| `export_layer` | Export a layer inside workspace (`json`, `sharded_jsonl`, `graphml`, `gexf`, `parquet`) | `layer_id`, `format`, `output_path`, `shard_size` |
| `validate_layer` | Run `IntegrityValidator` and return graph connectivity & quality telemetry | `layer_id` |

---

## 3. Recommended Agent-in-the-Loop Workflow

1. **Ingest:** Call `ingest_source` on target websites and local files → writes `01_ingested.jsonl`.
2. **Map:** Call `run_local_map` for baseline extraction, and/or inspect documents and call `submit_mapped_batch` with agent-verified entities, semantic triples, and `Evidence` spans.
3. **Reduce:** Call `resolve_and_reduce(layer_id="base-v1", conflict_strategy="preserve_dispute")`.
4. **Adjudicate:** Call `list_conflicts("base-v1")` to review disputed facts and their competing evidence, then call `resolve_conflict(base_layer_id="base-v1", ..., target_layer_id="curated-v1")` to publish an immutable audited layer.
5. **Query & Export:** Query via `query_knowledge_graph("curated-v1", query=..., hops=1)` or export via `export_layer`.

### Example `submit_mapped_batch` Payload

Each item in `batches` validates strictly (`extra="forbid"`) against the `MappedBatch` schema using the top-level keys `source_document`, `entities`, `claims`, and `relations`:

```json
{
  "batches": [
    {
      "source_document": {
        "source_id": "antigravity_review",
        "uri": "agent://antigravity/session-1",
        "source_type": "agent",
        "title": "Agent Curated Notes",
        "content": "Civic Honors was published in 2006.",
        "trust_weight": 0.95
      },
      "entities": [
        {
          "entity_id": "ent_ch",
          "canonical_name": "Civic Honors",
          "entity_type": "ORG",
          "evidence": [{"source_id": "antigravity_review", "excerpt": "Civic Honors", "extractor_name": "antigravity"}]
        }
      ],
      "claims": [
        {
          "claim_id": "clm_ag_1",
          "statement": "Civic Honors was published in 2006.",
          "category": "Publication",
          "reliability": 4,
          "source_id": "antigravity_review",
          "subject_id": "ent_ch",
          "predicate": "PUBLISHED_IN",
          "object_literal": "2006",
          "evidence": [{"source_id": "antigravity_review", "excerpt": "published in 2006", "extractor_name": "antigravity"}]
        }
      ],
      "relations": [
        {
          "relation_id": "rel_ag_1",
          "source_id": "clm_ag_1",
          "target_id": "ent_ch",
          "relation_type": "MENTIONS"
        }
      ]
    }
  ],
  "append": true
}
```
