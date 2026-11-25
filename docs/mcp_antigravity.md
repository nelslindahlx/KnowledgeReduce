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

## 2. Exposed Tools (17 Tools)

| Tool | Role | Key Arguments |
|---|---|---|
| `ingest_source` | Crawl URLs (SSRF-safe) or read local files/directories (CSV/JSON/MD/HTML/PDF/TXT) into `01_ingested.jsonl` with optional SHA-256 skip-unchanged delta mode | `local_files`, `local_directories`, `crawl_config`, `checkpoint_name`, `incremental_from_layer` |
| `read_ingested_checkpoint` | Paginate and optionally filter or truncate ingested `SourceDocument` records inside `--checkpoint-dir` | `checkpoint_name`, `offset`, `limit`, `max_chars_per_doc`, `source_id` |
| `run_local_map` | Run local `deterministic`, `structured`, or `spacy` mapper into `02_mapped.jsonl` | `ingested_checkpoint`, `mapped_checkpoint`, `mapper`, `min_sentence_length`, `skip_headings`, `skip_questions` |
| `submit_mapped_batch` | Inject Antigravity-extracted `MappedBatch` objects directly into `02_mapped.jsonl` | `batches`, `mapped_checkpoint`, `append` |
| `resolve_and_reduce` | Entity resolution, 3-stage dedup, conflict detection, integrity gate → Parquet layer + optional pre-warmed `claim_embeddings.parquet` | `layer_id`, `layer_name`, `mapped_checkpoint`, `conflict_strategy`, `parent_layer_ids`, `build_embeddings_index` |
| `stack_layers` | Compose layers via `overlay`, `union`, `intersection`, or `difference` (with optional `reconcile`, `deduplicate_claims` & pre-warmed index) | `layer_ids`, `target_layer_id`, `mode`, `conflict_strategy`, `reconcile`, `deduplicate_claims`, `build_embeddings_index` |
| `diff_layers` | Compute added/removed/modified entities, claims, relations, and resolved conflicts | `left_layer_id`, `right_layer_id` |
| `query_knowledge_graph` | Hybrid GraphRAG semantic+lexical+graph search or structured tag/category/reliability queries | `layer_id`, `query`, `category`, `tag`, `min_reliability`, `top_k`, `hops` |
| `list_conflicts` | Inspect unresolved (`needs_review=True`) or historical `ConflictRecord`s | `layer_id`, `needs_review_only`, `limit` |
| `resolve_conflict` | Adjudicate a single conflict non-destructively into a new immutable `CURATED` child layer | `base_layer_id`, `conflict_id`, `target_layer_id`, `winning_value` |
| `resolve_conflicts` | Atomically adjudicate multiple conflicts into a single immutable `CURATED` child layer | `base_layer_id`, `target_layer_id`, `resolutions`, `default_notes`, `overwrite` |
| `export_layer` | Export a layer inside workspace (`json`, `sharded_jsonl`, `graphml`, `gexf`, `markdown`, `parquet`) | `layer_id`, `format`, `output_path`, `shard_size` |
| `validate_layer` | Run `IntegrityValidator` and return graph connectivity & quality telemetry | `layer_id` |
| `list_layers` | List all persisted knowledge layers and metadata in the workspace store | — |
| `get_layer_lineage` | Inspect parent, ancestor, and descendant lineage for a stored layer | `layer_id` |
| `analyze_graph` | Run PageRank/degree/betweenness centrality, Louvain communities, and bounded shortest paths | `layer_id`, `metric`, `top_k`, `include_communities`, `path_source_id`, `path_target_id`, `max_hops` |
| `inspect_entity` | Inspect an entity by ID, canonical name, or alias with linked claims, graph neighbors, open conflicts, and cited sources | `layer_id`, `entity_id_or_name`, `max_claims`, `max_neighbors` |

---

## 3. Resources (3 Endpoints) & Prompts (2 Templates)

### Resources (`application/json`)
- `kr://layers` — Serialized catalog of all persisted layers in the workspace store.
- `kr://layers/{layer_id}/manifest` — Metadata-only `KnowledgeLayer` manifest for `{layer_id}`.
- `kr://layers/{layer_id}/conflicts` — Open conflict records (`needs_review=True`) awaiting adjudication in `{layer_id}`.

### Prompts
- `extract_mapped_batch(checkpoint_path="01_ingested.jsonl", source_id=None)` — Guides an agent through reading `read_ingested_checkpoint` pages and submitting normalized `MappedBatch` objects via `submit_mapped_batch`.
- `adjudicate_conflicts(layer_id)` — Guides an agent through inspecting `kr://layers/{layer_id}/conflicts`, verifying entity context with `inspect_entity`, and committing one atomic batch via `resolve_conflicts`.

---

## 4. Recommended Agent-in-the-Loop Workflow

1. **Ingest:** Call `ingest_source` on target websites, local files, or `local_directories` → writes `01_ingested.jsonl`.
2. **Map:** Call `run_local_map` for baseline extraction, and/or inspect documents with `read_ingested_checkpoint` and call `submit_mapped_batch` with agent-verified entities, semantic triples, and `Evidence` spans.
3. **Reduce:** Call `resolve_and_reduce(layer_id="base-v1", conflict_strategy="preserve_dispute")`.
4. **Adjudicate:** Read `kr://layers/base-v1/conflicts` or `list_conflicts("base-v1")` alongside `inspect_entity`, then call `resolve_conflicts(base_layer_id="base-v1", target_layer_id="curated-v1", resolutions=[...])` (or `resolve_conflict` for single items) to publish an immutable audited layer.
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
