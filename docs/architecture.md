# KnowledgeReduce Architecture & Schema Specification

## 1. Five-Stage Pipeline Overview

```text
[1. INGEST]                 [2. MAP (Stateless, Parallel)]       [3. RESOLVE (Shuffle/Block)]
Web Crawler / Local Files   Per-doc Chunking + Extractors  ──►   Blocking (SHA-256 + LSH + ANN)
  • SSRF IP & http/https    • StructuredMapper (CSV/JSON)        • Entity Disambiguation (Union-Find)
  • Cached robots.txt       • DeterministicNLP / SpacyNLP        • Canonical entity_id_map
  • Trafilatura main text   • Antigravity via MCP                • Atomic endpoint remapping
  • content_sha256            (`submit_mapped_batch`)            └─► 03_resolved.jsonl
  └─► 01_ingested.jsonl     └─► 02_mapped.jsonl                             │
                                                                            ▼
[5. STORE / STACK / SERVE]                         [4. REDUCE (Aggregate + Conflict Resolution)]
  • DuckDB + Parquet Layers (default store)        ◄──  • Cluster-medoid representative selection
  • MemoryGraphStore (NetworkX MultiDiGraph)            • Provenance/alias/tag union (no data loss)
  • StackManager (overlay/union/intersect/diff)         • PreserveDispute default (CONTRADICTS edge +
  • Portable Parquet / Versioned JSON / Sharded           ConflictRecord) + pluggable resolvers
    JSONL+Manifest / Sanitized GraphML & GEXF           • Post-reduce IntegrityValidator gate
  • Typer CLI (`kr`) + Python SDK + stdio MCP Server
```

---

## 2. Core Data Model (`knowledgereduce.models`)

All records are strict **Pydantic v2** models (`extra="forbid"`) with timezone-aware **UTC** datetimes and ordinal **`ReliabilityRating(IntEnum)`** (`UNKNOWN=0`, `UNVERIFIED=1`, `POSSIBLY_TRUE=2`, `LIKELY_TRUE=3`, `VERIFIED=4`).

| Model | Purpose | Key Fields |
|---|---|---|
| `SourceDocument` | Ingested web or file document | `source_id`, `uri`, `source_type`, `title`, `author`, `published_at`, `fetched_at`, `content`, `content_sha256`, `trust_weight` |
| `Evidence` | Fine-grained source provenance | `source_id`, `uri`, `excerpt`, `char_span`, `extractor_name`, `extracted_at`, `extraction_confidence` |
| `Entity` | Canonical entity node | `entity_id`, `canonical_name`, `entity_type`, `aliases`, `attributes`, `evidence`, `external_ids` |
| `Claim` | Modernized 16-field fact record | `claim_id`, `statement`, `category`, `tags: list[str]`, `contextual_notes`, `recorded_at`, `updated_at`, `published_at`, `reliability`, `source_id`, `source_title`, `author_creator`, `url_reference`, `access_level`, `usage_count`, `related_facts`, `confidence`, `subject_id`, `predicate`, `object_id`, `object_literal`, `evidence`, `merged_from`, `needs_review`, computed `quality_score` |
| `Relation` | Typed directed graph edge | `relation_id`, `source_id`, `target_id`, `relation_type`, `confidence`, `weight`, `evidence`, `attributes` |
| `ConflictRecord` | Preserved or resolved dispute | `conflict_id`, `target_type`, `target_key`, `candidates`, `resolution_strategy`, `winning_value`, `winning_source_id`, `resolved_at`, `needs_review`, `resolution_notes` |
| `KnowledgeLayer` | Immutable layer metadata | `layer_id`, `name`, `version`, `tier`, `parent_layer_ids`, `merge_mode`, `created_at`, `pipeline_config_hash`, `stats` |

### Quality Score Formula
`Claim.quality_score` is a read-only `@computed_field` strictly bounded in `[0.0, 100.0]`:
- Reliability: `(int(reliability) / 4.0) * 50.0` (0–50 pts)
- Confidence: `confidence * 25.0` (0–25 pts)
- Usage: `min(usage_count, 10) * 1.5` (0–15 pts)
- Evidence depth: `min(len(evidence), 5) * 2.0` (0–10 pts)
- Structural grounding: `+5.0` for complete `(subject_id, predicate, object_id|object_literal)` triple, or `+2.5` for partial `(subject_id, predicate)` grounding (total score clamped to `[0.0, 100.0]`)

---

## 3. DuckDB + Parquet Storage Layout

Each layer is stored atomically inside `<store_dir>/layers/<layer_id>/`:

```text
<store_dir>/layers/<layer_id>/
├── manifest.json              # schema_version "1.0", serialized KnowledgeLayer metadata, row counts & SHA-256 digests
├── sources.parquet            # typed PyArrow/Zstd Parquet tables
├── entities.parquet
├── claims.parquet
├── relations.parquet
├── conflicts.parquet
└── claim_embeddings.parquet   # optional persisted L2-normalized claim vector index (created on build_index/first query)
```

- `DuckDBParquetStore` queries Parquet files using **parameterized DuckDB SQL** (`read_parquet(?)`, `UNNEST(?::VARCHAR[])`, `list_filter(?::VARCHAR[], ...)`, `?` placeholders — zero SQL string interpolation) over a thread-safe persistent `:memory:` DuckDB read session (`_read_con`, guarded by `_con_lock`), paired with `(st_mtime_ns, st_size)`-validated `ClaimSummary` and bounded layer-graph caches evicted automatically on layer writes and deletes.
- `HybridGraphRAGRetriever` persists `FixedSizeListArray` `claim_embeddings.parquet` zero-copy vector indices for stateless embedding providers (`HashingEmbeddingProvider`, `SentenceTransformerProvider`), scores lightweight `ClaimSummary` projections first, hydrates full `Claim` models only for `top_k` winners, and expands graph context via `get_k_hop_subgraph` without loading entire large layers into memory.
- Empty tables preserve full PyArrow schemas.
- Overwriting an existing immutable layer requires explicit `overwrite=True` (which cleanly invalidates any prior `claim_embeddings.parquet`).

---

## 4. Stackable Layer Algebra (`knowledgereduce.stack.StackManager`)

- **`OVERLAY`**: Applies layers sequentially; incoming layers update scalar fields while unioning `aliases`, `tags`, and `evidence`. Conflicting statements/names record `ConflictRecord`s.
- **`UNION`**: Combines all entities, claims, and relations across layers, merging matching IDs with provenance preservation.
- **`INTERSECTION`**: Retains entities, claims, and relations present across all input layers.
- **`DIFFERENCE`**: Subtracts subsequent layers from `layer_ids[0]` and automatically removes dangling relations whose endpoints were removed.
- **Cross-Layer Reconciliation (`reconcile=True`)**: Available on `UNION` and `OVERLAY` to disambiguate equivalent entities with different IDs across independently generated layers, remap endpoints, surface cross-layer functional conflicts, and run `IntegrityValidator` strictly.
- **Lineage DAG**: `build_lineage_graph()`, `get_ancestors()`, and `get_descendants()` traverse `parent_layer_ids` non-destructively.

---

## 5. Security Invariants

1. **SSRF Defense (`knowledgereduce.security.validate_url_safe`)**: Enforces `http`/`https` schemes, blocks `localhost`, private/loopback/link-local/reserved IPv4 & IPv6 addresses, and re-validates every HTTP redirect target before opening sockets.
2. **Path Containment (`ensure_within_base`)**: All `DuckDBParquetStore`, `export`, and MCP file operations resolve and confine paths within allowed root directories (`PathSecurityError`).
3. **Non-Mutating Graph Exports**: `export_graphml` and `export_gexf` construct sanitized copies of `nx.MultiDiGraph` without mutating stored or live Python objects.
