# Changelog

All notable changes to KnowledgeReduce are documented in this file.

## [Unreleased]

## [1.6.1] - 2026-11-26

### Fixed
- **Markdown Frontmatter & DuckDB JSON Serialization Hardening:**
  - Normalized YAML frontmatter values via `_json_safe_value()` in `src/knowledgereduce/ingest/files.py` so unquoted YAML `date:`/`datetime` objects serialize cleanly as ISO strings in `SourceDocument.metadata["frontmatter"]`, hardened `author: null` handling to preserve `None`, and guarded `_parse_markdown_frontmatter()` against `yaml.YAMLError` when Markdown files begin with non-frontmatter `---` horizontal rules.
  - Added `default=str` to `json.dumps(...)` in `DuckDBParquetStore.save_layer()` (`src/knowledgereduce/storage/duckdb_store.py`) for `metadata_json`, `attributes_json`, and `manifest.json`, plus `src/knowledgereduce/map/structured.py`, `src/knowledgereduce/export/json_export.py`, and `src/knowledgereduce/export/sharded.py`.
  - Added end-to-end and unit regression tests across `tests/unit/test_ingest.py`, `tests/unit/test_storage.py`, and `tests/unit/test_pipeline_incremental.py`, and bumped SemVer to `1.6.1`.

## [1.6.0] - 2026-11-25

### Added
- **Phase 1: DuckDB SQL Pushdown, Metadata-Only Reads & Crash-Safe `save_layer` (`#53`)**:
  - Extended `GraphStore.list_claims()`, `DuckDBParquetStore.list_claims()`, `MemoryGraphStore.list_claims()`, and `QueryBuilder` (`filter_published_range`, `filter_subject`, `filter_predicate`, `filter_source`, `execute_claims()`) with parameterized SQL / native pushdown for `tags_any` (`list_has_any`), date ranges (`TRY_CAST(... AS TIMESTAMPTZ)`), sorting, and `LIMIT`/`OFFSET` (cutting uninstrumented `50K`-claim top-10 queries from `1,004.6 ms` to `6.82 ms` median).
  - Added metadata-only `get_layer_manifest()` and `list_source_hashes()` wired into `load_layer_source_hashes()` and `build_layer_lineage_payload()`.
  - Hardened `DuckDBParquetStore.save_layer()` with `_write_lock`, unique `.staging_` temp directories, and atomic backup-swap rollback on overwrite failures, eliminated per-query `id_to_sem` allocation in `HybridGraphRAGRetriever.retrieve()`, and made golden timing checks coverage-aware.
- **Phase 2: `StackManager` Cross-Layer Claim Dedup & `PipelineRunner` Parity (`#54`)**:
  - Exported shared `deduplicate_and_merge_claims()`, `merge_claim_cluster()`, and `deduplicate_relations()` in `src/knowledgereduce/reduce/reducer.py` and added `deduplicate_claims: bool = True`, `semantic_threshold`, and `min_claim_length` to `StackManager.merge_layers()` and `stack_overlay()` under `reconcile=True`.
  - Added `skip_headings` and `skip_questions` to `PipelineConfig`, forwarded `structured_config`, `skip_headings`, and `skip_questions` in `_map_single_doc_worker()`, added `PipelineRunner._open_store()`, and wrapped `DuckDBParquetStore` instances in `with ... as store:` across `src/knowledgereduce/cli.py`.
- **Phase 3: Directory/Glob Ingest, Optional `PDFConnector` & Markdown Frontmatter (`#55`)**:
  - Added `SourceType.PDF = "pdf"`, optional `[pdf]` extra (`pypdf>=5.0` in `pyproject.toml` + `uv.lock`), and path-sandboxed `PDFConnector`.
  - Added symlink-safe `DirectoryConnector` and `ingest_local_directory()`, `LocalDirectorySourceConfig` / `PipelineConfig.local_directories`, and `kr ingest --dir --glob`.
  - Parsed Markdown frontmatter `published_at`/`date` and normalized `tags` in `MarkdownConnector`, propagating document tags onto emitted `Claim.tags` in `DeterministicNLPMapper.map_document()`.
- **Phase 4: Atomic Batch Conflicts, Agent-Complete 17-Tool MCP & CLI Ergonomics (`#56`)**:
  - Added `ConflictResolutionDecision` and `adjudicate_conflicts()` in `src/knowledgereduce/reduce/conflicts.py` (preserving `needs_review=True` and `CONTRADICTS` edges for claims still participating in remaining open conflicts).
  - Expanded MCP server (`14 -> 17` tools) with `read_ingested_checkpoint`, `inspect_entity`, and `resolve_conflicts`, wired `local_directories` / `skip_headings` / `skip_questions` / `deduplicate_claims`, and registered 3 `@server.resource` endpoints (`kr://layers`, `kr://layers/{layer_id}/manifest`, `kr://layers/{layer_id}/conflicts`) plus 2 `@server.prompt` templates (`extract_mapped_batch`, `adjudicate_conflicts`).
  - Added CLI commands `kr resolve-conflicts`, `kr inspect`, and `kr doctor`, bumped SemVer to `1.6.0` across `pyproject.toml`, `src/knowledgereduce/__init__.py`, `docs/paper/CITATION.cff`, `tests/unit/test_smoke.py`, and `uv.lock`, and synchronized repository docs & governance parity.

### Changed
- Synchronized repository governance, CI documentation, `docs/paper/CITATION.cff`, and `Makefile` clean/gate parity (`--cov-fail-under=95` across `AGENTS.md`, `.agents/AGENTS.md`, `CONTRIBUTING.md`, `.github/pull_request_template.md`, and `.github/workflows/ci.yml`).

## [1.5.0] - 2026-11-24

### Added
- **Phase 1: Sub-15ms Warm GraphRAG via Persistent DuckDB Session & Claim Projection Cache (`#42`)**:
  - Added frozen `@dataclass(slots=True)` `ClaimSummary`, `summarize_claim()`, and shared `rank_claim_summaries()` in `src/knowledgereduce/storage/base.py` (re-exported in `src/knowledgereduce/storage/__init__.py`) and added matching summary lookup/ranking methods on `MemoryGraphStore` (`src/knowledgereduce/storage/memory.py`).
  - Updated `DuckDBParquetStore` (`src/knowledgereduce/storage/duckdb_store.py`) with a thread-safe persistent `:memory:` DuckDB read session (`_read_con`, `_con_lock`, `close()`, context manager), `(mtime_ns, size)`-validated `_claim_summary_cache` + `_layer_graph_cache` (`graph_cache_max_rows=50_000` with SQL fallback) evicted in `_invalidate_layer_caches()`, and empty `conflicts.parquet` / `relations.parquet` scan guards in `get_k_hop_subgraph()`.
  - Updated `HybridGraphRAGRetriever.retrieve()` (`src/knowledgereduce/query/graphrag.py`) to score lightweight `ClaimSummary` projections (including `contextual_notes` in provenance matching) and hydrate full Pydantic `Claim` objects only for `top_k` winners, cutting uninstrumented Book warm query latency from `51.2 ms` -> `10.7 ms` steady (`11.1 ms` first pass) and `10K` warm query latency to `21.4 ms` (`13.2 ms` steady).
- **Phase 2: Claim Hygiene, Section Context, SPO Density & Structural Quality Score (`#43`)**:
  - Added `skip_headings: bool = True` and `skip_questions: bool = True` options to `DeterministicNLPMapper` (`src/knowledgereduce/map/nlp.py`), capturing headings into downstream `contextual_notes = "Section: ..."` (preserving date/year bylines) and excluding unpunctuated section headings (`37` -> `0`) and rhetorical questions (`10` -> `0`) before Pass-1 entity registration.
  - Expanded safe non-colliding narrative predicates in `_ANCHORED_VERB_MAP` and modal/negated auxiliaries in `_ANCHORED_AUX_RE`, lifting *Civic Honors: The Book* `grounded_triple_rate` from `0.2614` -> `0.2821` (`44` semantic relations), `claim_connectivity_rate` from `0.5131` -> `0.5204`, and lowering `isolated_node_ratio` from `0.4473` -> `0.4390`.
  - Added structural grounding weights to `Claim.quality_score` (`src/knowledgereduce/models/schemas.py`: `+5.0` complete SPO triple, `+2.5` partial `(subject_id, predicate)`, bounded `[0.0, 100.0]`), raising *Civic Honors: The Book* `mean_quality_score` from `57.97` -> `59.42` while preserving full backward compatibility for ungrounded claims.
- **Phase 3: Multi-Source Stacked/Incremental Golden Benchmark & Floor Ratchet (`#44`)**:
  - Snapshotted verified `v1.4.0` metrics into `benchmarks/datasets/civichonors_book/baseline_v1_4_0.json`, exported `BASELINE_V14_PATH`, and ratcheted `DEFAULT_REGRESSION_FLOORS` in `benchmarks/civichonors_book_benchmark.py` (`claim_connectivity_rate >= 0.50`, `grounded_triple_rate >= 0.26`, `mean_quality_score >= 59.0`, `isolated_node_ratio <= 0.45`, `total_seconds <= 8.0`).
  - Added offline `benchmarks/multisource_stack_benchmark.py` and `tests/golden/test_multisource_stack_golden.py` exercising `HTMLConnector`, `MarkdownConnector`, `incremental_from_layer` SHA-256 skip-unchanged deltas, pre-warmed embeddings, `StackManager.merge_layers(..., reconcile=True)` over conflicting overlays, GraphRAG conflict surfacing, analytics, and Markdown brief export, wired into `make golden`.
- **Phase 4: Coverage Hardening (`>= 95%`), SemVer `1.5.0` & Doc Sync (`#45`)**:
  - Expanded unit coverage in `tests/unit/test_structured_mapper.py`, `tests/unit/test_export.py`, `tests/unit/test_ingest.py`, and `tests/unit/test_query.py` covering `src/knowledgereduce/map/structured.py` (`99%`), `src/knowledgereduce/export/sharded.py` (`100%`), `src/knowledgereduce/export/graph_formats.py` (`100%`), `src/knowledgereduce/ingest/base.py` (`97%`), and `src/knowledgereduce/query/analytics.py` (`100%`), lifting total coverage to `95.70%` (`135 passed`) and raising `Makefile` `test` gate to `--cov-fail-under=95`.
  - Bumped SemVer to `1.5.0` across `pyproject.toml`, `src/knowledgereduce/__init__.py`, `tests/unit/test_smoke.py`, and `uv.lock`, and synced `README.md`, `docs/conflicts_and_benchmarks.md`, `lessons_learned.md`, `CHANGELOG.md`, and `docs/plans/`.

## [1.4.0] - 2026-11-24

### Added
- **Phase 1: `O(N)` Claim Merge Features & Zero-Copy Arrow Embeddings (`#32`)**:
  - Precomputed frozen `@dataclass(slots=True)` `_ClaimMergeFeatures` once per claim in `src/knowledgereduce/resolve/blocking.py` (`_extract_merge_features`, `_features_compatible`, and backward-compatible `_claims_compatible_for_merge`), eliminating repeated regex evaluation across Stage 2 blocking and Stage 3 dense-bucket loops.
  - Updated `src/knowledgereduce/storage/duckdb_store.py` to write `claim_embeddings.parquet` as `pa.FixedSizeListArray`, decode embeddings via zero-copy `to_numpy` with backward-compatible fallback for legacy `list<float32>` Parquet files, cache loaded embeddings keyed by `(mtime_ns, size)` with eviction on `save_layer`/`delete_layer`/`save_claim_embeddings`, and share a single `duckdb.connect(":memory:")` session across `load_layer()` and `get_k_hop_subgraph()`.
  - Cut `1K` `reduce_seconds` from `3.19s` -> `0.387s` (`8.2x`), *Civic Honors: The Book* `reduce_seconds` from `3.12s` -> `0.623s` (`5.0x`), and `10K` end-to-end cold scaling from `27.00s` -> `4.241s` (`6.4x`), while cutting warm query latency nearly in half with zero accuracy regressions.
- **Phase 2: Extraction Precision, Triple Density & Golden Floor Ratchet (`#33`)**:
  - Extended `_FACTUAL_PATTERNS` clause-stop boundaries in `src/knowledgereduce/map/nlp.py` (`golden_50_docs` `bcubed_recall`: `0.9467` -> `1.0000`, `bcubed_f1`: `0.9726` -> `1.0000`) and added shared single-year temporal conflict resolution inside `src/knowledgereduce/reduce/conflicts.py` (`_resolve_bucket_conflict`, `::year` conflict keys) so truncated functional claims keep `1.0000` conflict detection/resolution.
  - Added `Magazine`, `Institute of ...`, and hyphenated CamelCase (`McGraw-Hill`) patterns, dominant non-Press `"the university"` coreference in `_build_pass2_linker()`, widened appositive matching and modal/passive verb grounding (`_ANCHORED_AUX_RE` / `_ANCHORED_VERB_MAP`), raising *Civic Honors: The Book* `grounded_triple_rate` (`0.2021` -> `0.2614`), `semantic_relations` (`29` -> `43`), and `claim_connectivity_rate` (`0.4684` -> `0.5131`) while lowering `isolated_node_ratio` (`0.4884` -> `0.4473`) with `1.0000` recall/retention/`Hit@1`/`MRR@5`.
  - Snapshotted `benchmarks/datasets/civichonors_book/baseline_v1_3_0.json` and ratcheted `DEFAULT_REGRESSION_FLOORS` in `benchmarks/civichonors_book_benchmark.py`.
- **Phase 3: CLI/MCP Incremental Refresh, Pre-Warmed Indexing & Local HTML Connector (`#34`)**:
  - Extracted shared `load_layer_source_hashes` and `filter_unchanged_documents` in `src/knowledgereduce/pipeline/runner.py` (re-exported in `src/knowledgereduce/pipeline/__init__.py`) and added `skipped_unchanged` tracking to `AsyncWebCrawler` / `WebConnector` (`src/knowledgereduce/ingest/web.py`).
  - Added `SourceType.HTML` (`src/knowledgereduce/models/enums.py`), offline `HTMLConnector` (`src/knowledgereduce/ingest/files.py`, `.html`/`.htm` dispatch in `ingest_local_file`, exported in `src/knowledgereduce/ingest/__init__.py`) reusing `extract_main_text` and enforcing `ensure_within_base`.
  - Exposed `--incremental-from` + `--store` on `kr ingest`, `--parent-layer` + `--build-index/--no-build-index` on `kr reduce`, `--build-index/--no-build-index` on `kr stack`, and `kr index` in `src/knowledgereduce/cli.py`; added `incremental_from_layer`, `parent_layer_ids`, and `build_embeddings_index` parity to `ingest_source`, `resolve_and_reduce`, and `stack_layers` in `src/knowledgereduce/mcp/server.py`.
- **Docs, Governance Parity & Coverage (`#35`)**:
  - Bumped SemVer to `1.4.0` across `pyproject.toml`, `src/knowledgereduce/__init__.py`, and `tests/unit/test_smoke.py`.
  - Synced `README.md`, `docs/mcp_antigravity.md`, `docs/conflicts_and_benchmarks.md`, `lessons_learned.md`, `CHANGELOG.md`, and `docs/plans/` with all `14` MCP tools, `make local-ci`, `v1.4.0` scaling/golden metrics, and Lesson 10–11; added mechanical doc-parity checks to `tests/meta/test_governance_and_invariants.py`.
  - Expanded unit test coverage across `ingest.security`, `storage.export`, `ingest`, `cli`, and `resolve`/`reduce` validator branches, raising suite coverage above `94%`.

## [1.3.0] - 2026-11-24

### Added
- **Zero-GitHub-Minutes Local CI & Maker/Checker Tooling (`#27`)**: Switched `.github/workflows/ci.yml` and `.github/workflows/pr-governance.yml` to manual `workflow_dispatch` only, added `Makefile` stratified local CI targets (`canary`, `lint`, `typecheck`, `smoke-pr`, `test`, `golden`, `benchmark`, `local-ci`, `audit-prs`), synchronized `AGENTS.md` and `.agents/AGENTS.md`, added `.agents/rules/`, `.agents/hooks.json` (`scripts/hooks/pre_pr_safety_gate.py`), `scripts/github_pr_helper.py`, `lessons_learned.md`, `docs/plans/`, and mechanical governance/relevance tests in `tests/meta/test_governance_and_invariants.py`.
- **Lossless Claim Clustering & Metadata-Preserving Reduction (`#23`)**: Separated functional vs. non-functional predicate merge compatibility cleanly in `src/knowledgereduce/resolve/blocking.py`, added asymmetric 4-digit year and formal APA citation guards raising *Civic Honors: The Book* `core_fact_retention` from `0.9167` to `1.0000`, added atomic grounded-triple and provenance recovery in `src/knowledgereduce/reduce/reducer.py`, and applied `0.75` structural heading scaling across both lexical and semantic retrieval scores in `src/knowledgereduce/query/graphrag.py`.
- **Incremental Delta Ingestion & Pre-Warmed Indexing (`#24`)**: Added `PipelineConfig.incremental_from_layer` and `PipelineConfig.build_embeddings_index` in `src/knowledgereduce/pipeline/config.py`, plus automatic SHA-256 skip-unchanged delta ingestion (both `CrawlConfig.known_hashes` and local files), parent lineage wiring, and pre-built stateless claim embeddings in `src/knowledgereduce/pipeline/runner.py`.
- **Graph Analytics, Layer Introspection & Markdown Knowledge Brief Export (`#25`)**: Added `render_layer_markdown` and `export_layer_markdown` in `src/knowledgereduce/export/markdown_export.py` (re-exported in `src/knowledgereduce/export/__init__.py`), added shared analytics/lineage payload builders and MCP tools `list_layers`, `get_layer_lineage`, `analyze_graph`, and `export_layer(format="markdown")` in `src/knowledgereduce/mcp/server.py` (14 tools total), added CLI commands `kr layers`, `kr lineage`, `kr analyze`, and `kr export --format markdown` in `src/knowledgereduce/cli.py`, and synchronized SemVer `1.3.0` across `pyproject.toml` and `src/knowledgereduce/__init__.py`.

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
