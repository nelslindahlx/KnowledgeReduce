# Changelog

All notable changes to KnowledgeReduce are documented in this file.

## [1.3.0] - 2026-11-24

### Added
- **Zero-GitHub-Minutes Local CI & Maker/Checker Tooling (`#27`)**: Switched `.github/workflows/ci.yml` and `.github/workflows/pr-governance.yml` to manual `workflow_dispatch` only, added `Makefile` stratified local CI targets (`canary`, `lint`, `typecheck`, `smoke-pr`, `test`, `golden`, `benchmark`, `local-ci`, `audit-prs`), synchronized `AGENTS.md` and `.agents/AGENTS.md`, added `.agents/rules/`, `.agents/hooks.json` (`scripts/hooks/pre_pr_safety_gate.py`), `scripts/github_pr_helper.py`, `lessons_learned.md`, `docs/plans/`, and mechanical governance/relevance tests in `tests/meta/test_governance_and_invariants.py`.

## [1.2.0] - 2026-11-24

### Added
- **Civic Honors Offline Golden Benchmark (`#15`)**: Froze the 139,596-char *Civic Honors: The Book* corpus (`benchmarks/civichonors_book_benchmark.py`, `gold_annotations.json`, `baseline_v1_1_0.json`) and pytest regression suite (`tests/golden/test_civichonors_book_golden.py`).
- **Deterministic NER, Two-Pass Linking & Grounded Triples (`#20`)**: Expanded abbreviation-aware splitting, APA bibliography segmentation, heading suppression (`12 -> 0` heading false positives), two-pass entity-to-claim linking, and non-functional grounded SPO triples.
- **Cross-Type Disambiguation & GraphRAG Ranking (`#21`, `#22`)**: Added cross-type exact-name entity consolidation (`DATE > GPE > ORG > PERSON > CONCEPT`), omitted middle/leading-initial person matching (`alias_merge_recall: 0.80 -> 1.00`), stop-word-aware `tokenize_search_query`, and IDF-weighted Hybrid GraphRAG ranking (`retrieval_hit_at_1: 0.80 -> 1.00`).
- **Maker/Checker Governance & Crawler Fix (`#13`, `#14`)**: Added `CODEOWNERS`, PR template, governance docs, and fixed `httpx.DecodingError` gzip double-decompression in `AsyncWebCrawler._safe_get`.

## [1.1.0] - 2026-11-23

### Added
- **Persisted Claim Embeddings & Bounded Subgraph Retrieval:** Added stateless `HashingEmbeddingProvider`, Parquet-backed `claim_embeddings.parquet` index (`save_claim_embeddings` / `load_claim_embeddings` / `HybridGraphRAGRetriever.build_index`), parameterized DuckDB lexical ranking (`search_claims_lexical`), batch ID lookups (`get_claims_by_ids`), and bounded BFS subgraph extraction (`get_k_hop_subgraph`) cutting 10K-fact GraphRAG traced memory by ~37% and halving warm query latency.
- **Cross-Layer Reconciliation (`StackManager`):** Added opt-in `reconcile=True` and `lexical_threshold` to `stack_overlay` and `merge_layers` (`UNION`/`OVERLAY`), plus `--reconcile` in `kr stack` and `reconcile` in MCP `stack_layers`.
- **CLI Conflict Adjudication Parity:** Extracted shared `adjudicate_conflict()` helper and added `kr conflicts` and `kr resolve-conflict` CLI commands; `kr ingest` now exits non-zero with a clear `IngestionError` if no files or URLs are supplied.
- **Sparse JSON/JSONL Schema Inference:** `StructuredMapper` now infers columns across the union of all records (`_collect_present_fields`) rather than only `rows[0]`.
- **Deterministic NER & Release Tooling:** Added CamelCase/PascalCase entity extraction (`_CAMEL_ENTITY_RE`), guarded ALL-CAPS phrases, expanded test coverage across `[nlp]`/`[embeddings]` paths (89.9% total coverage), upgraded GitHub Actions to `actions/checkout@v7` & `astral-sh/setup-uv@v10.4.0`, and added manual PyPI Trusted Publisher `.github/workflows/release.yml`.

## [1.0.0] - 2026-11-23

### Added
- **Clean `src/knowledgereduce/` package** targeting Python 3.11+ with `uv`, PEP 621 `pyproject.toml`, strict `mypy --strict`, `ruff`, and GitHub Actions CI.
- **Pydantic v2 Domain Schemas (`knowledgereduce.models`):** `SourceDocument`, `Evidence`, `Entity`, modernized 16-field `Claim` (ordinal `ReliabilityRating(IntEnum)`, list `tags`, bounded computed `quality_score`), `Relation`, `ConflictRecord`, `KnowledgeLayer`, `MappedBatch`, `LayerData`, `LayerDiff`, `ValidationReport`, and typed domain exceptions.
- **Hardened Ingestion (`knowledgereduce.ingest`):** SSRF-protected `AsyncWebCrawler` (DNS & private/loopback IP blocking, `http`/`https` allowlist, redirect validation, cached `robots.txt` with timeouts, per-domain rate limit, `trafilatura` main-content extraction, `content_sha256` change tracking) plus `CSVConnector`, `JSONConnector`, `MarkdownConnector`, and `TextConnector`.
- **Stateless Mappers (`knowledgereduce.map`):** `DeterministicNLPMapper` (abbreviation-aware sentence splitter, factual triple grounding, `MENTIONS` entity linking), `StructuredMapper`, optional batched `SpacyNLPMapper`, and resumable JSONL stage checkpoints.
- **Sub-Quadratic Resolution & Reduction (`knowledgereduce.resolve`, `knowledgereduce.reduce`):** 3-stage blocking/clustering with Union-Find entity disambiguation, atomic `entity_id_map` endpoint remapping, representative-preserving cluster merging, `PreserveDispute` conflict policy (`CONTRADICTS` + `ConflictRecord`), and `IntegrityValidator` gate.
- **Columnar Storage & Stackable Algebra (`knowledgereduce.storage`, `knowledgereduce.stack`):** `DuckDBParquetStore` with immutable Parquet layers + parameterized DuckDB SQL, `MemoryGraphStore`, and `StackManager` (`overlay`, `union`, `intersection`, `difference`, `diff_layers`, lineage DAG).
- **Portable Exporters (`knowledgereduce.export`):** Versioned JSON (`edges="links"` compatibility), lossless sharded JSONL + `manifest.json` preserving cross-shard edges, and non-mutating sanitized GraphML/GEXF exporters.
- **Query, CLI, & Antigravity MCP (`knowledgereduce.query`, `knowledgereduce.cli`, `knowledgereduce.mcp`):** Fluent `QueryBuilder`, `k_hop_neighborhood`, `bounded_shortest_path`, native Louvain community detection, `HybridGraphRAGRetriever`, `kr` Typer CLI, and 11-tool `stdio` MCP server (`kr mcp`).
- **Evaluation & Examples:** 50-document frozen golden benchmark + 1K/10K scaling harness (`benchmarks/run_benchmark.py`), offline examples (`examples/`), and clean curated notebooks (`notebooks/`).

### Changed
- Archived all 35 historical Colab notebooks, 12 experimental automation trees, and the legacy `knowledge_graph_pkg` prototype into `legacy/` with `legacy/README.md` (pre-reorg snapshot tagged at `archive/experiments-2023-2025`), moved `Paper_Preprint/` to `docs/paper/`, fixed `CITATION.cff`, and removed all committed `.pyc` files.
