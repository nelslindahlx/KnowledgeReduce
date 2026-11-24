# Mandatory Coding-Method Guardrails

Every contributor and AI agent authoring, modifying, or reviewing code in **KnowledgeReduce** should apply this 10-point engineering checklist before opening a Pull Request.

---

## 1. End-to-End Producer / Consumer Contract Verification
- Every pipeline stage enhancement (`ingest -> map -> resolve -> reduce -> store -> query`) **must** be accompanied by an end-to-end or integration test verifying that downstream stages actually read and benefit from the emitted data (entities, grounded triples, `known_hashes`, persisted embeddings, or lineage metadata).

## 2. Canonical Pydantic v2 Schema & Constructor Enforcement
- Pass typed Pydantic models (`SourceDocument`, `Evidence`, `Entity`, `Claim`, `Relation`, `ConflictRecord`, `MappedBatch`, `LayerData`) built with `extra="forbid"` rather than unvalidated ad-hoc dicts across stage boundaries.

## 3. Provenance & Factual-Truth Preservation
- Never let a lossy heuristic (such as generic paraphrase clustering or stop-word-blind lexical scoring) swallow distinct dated facts, formal bibliographic entries (APA citations), or secondary provenance attributes (`published_at`, `author_creator`, `url_reference`, grounded triples).
- When `ConflictStrategy.PRESERVE_DISPUTE` is active, preserve dissenting evidence and attach `CONTRADICTS` edges cleanly.

## 4. Single-Point Telemetry Accounting Before Control-Flow Jumps
- Record stage statistics (`claims_before`, `claims_after`, `dropped_short_claims`, `skipped_unchanged`, `embeddings_indexed`) unconditionally before early returns or empty-batch fast paths.

## 5. Bounded Memory & Latency Budgets
- Keep 10,000-claim end-to-end reduction + storage + GraphRAG warm retrieval well within the `< 60s` scaling SLA using O(N) exact hashing, bounded token blocking caps, coarse MiniBatchKMeans partitioning, persisted claim embeddings (`claim_embeddings.parquet`), and bounded k-hop subgraphs (`get_k_hop_subgraph`).

## 6. Security & Process-Safe Persistence
- Enforce URL SSRF protection (`validate_url_safe` + private/loopback DNS IP rejection + redirect validation) in web ingestion.
- Enforce workspace/export path containment (`ensure_within_base`) across CLI/MCP/export surfaces.
- Use parameterized DuckDB SQL (`read_parquet(?)`, `UNNEST`) rather than string interpolation of user inputs, and validate `layer_id` formats strictly.

## 7. Empty-Layer & Boundary-Value Invariant Checks
- Guard empty layers (`0` documents, `0` claims, `0` edges), invalid enums, negative `max_*` or `top_k` bounds, and partial path arguments explicitly with typed domain exceptions (`KnowledgeReduceError`, `StorageError`, `SchemaValidationError`).

## 8. Pre-Edit Hotspot Blame & Mechanical Anti-Oscillation Gate
- Before altering claim-blocking rules, predicate vocabularies, entity-resolution heuristics, or GraphRAG scoring weights, inspect existing invariants and run `make golden` and `tests/meta/` to catch subtle accuracy regressions against *Civic Honors: The Book* and the 50-doc corpus.

## 9. Codebase-Wide Sibling Sweep & Shared Primitives
- Fix shared logic in a single canonical helper (`DEFAULT_FUNCTIONAL_PREDICATES` / `is_functional_predicate`, `adjudicate_conflict`, `tokenize_search_query`, `_claims_compatible_for_merge`) and sweep all callers (`CLI`, `MCP`, `StackManager`, `PipelineRunner`) in the same PR.

## 10. Explicit `is not None` Integer & Score Checks
- Always use `if value is not None:` for optional numeric thresholds, reliability ratings (`0` = `UNKNOWN`), hop depths (`k = 0`), and `max_*` limits; never use falsy `or` fallbacks where `0` or `0.0` is valid.
