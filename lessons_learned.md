# KnowledgeReduce Engineering Lessons Learned

Verified engineering insights, bug root causes, and optimization patterns discovered during real-world corpus testing, benchmarking, and production hardening of **KnowledgeReduce**.

---

## Lesson 1: Stripping `Content-Encoding` After `httpx` Streaming Gzip Decode
- **Symptom**: Crawling gzip-compressed HTTP responses caused `httpx.DecodingError` when passing raw response bytes/headers onward.
- **Root Cause**: `AsyncWebCrawler._safe_get` in `src/knowledgereduce/ingest/web.py` decompressed the body stream via `resp.aiter_bytes()` while preserving original `Content-Encoding` / `Content-Length` headers on the reconstructed `httpx.Response`, triggering a second decompression failure when callers accessed `.text`.
- **Resolution & Guard**: Strip hop-by-hop encoding/length headers after streaming decompression in `src/knowledgereduce/ingest/web.py`, verified by gzip regression tests in `tests/unit/test_ingest.py`.

---

## Lesson 2: Functional Predicate Suffix Collisions (`_IN`, `_AT`, `_ON`, `_YEAR`, `_DATE`)
- **Symptom**: Non-functional descriptive narrative relations extracted by `DeterministicNLPMapper` triggered false contradiction detection inside `KnowledgeReducer`.
- **Root Cause**: `is_functional_predicate()` in `src/knowledgereduce/reduce/conflicts.py` treats any predicate ending in `_IN`, `_AT`, `_ON`, `_YEAR`, or `_DATE` as single-valued (`DEFAULT_FUNCTIONAL_PREDICATES`), so verb mappings in `src/knowledgereduce/map/nlp.py` using `_ON` suffixes (for example `BASED_ON` instead of `DRAWS_ON` or `BUILT_FROM`) collided unexpectedly with conflict resolution.
- **Resolution & Guard**: Keep narrative `_ANCHORED_VERB_MAP` predicates non-colliding and enforce this mechanically inside `tests/meta/test_governance_and_invariants.py`.

---

## Lesson 3: Breaking the `knowledgereduce.reduce` <-> `knowledgereduce.resolve` Import Cycle
- **Symptom**: Importing `DEFAULT_FUNCTIONAL_PREDICATES` at module import time inside `src/knowledgereduce/resolve/blocking.py` creates a circular import whenever callers import `knowledgereduce.resolve` before `knowledgereduce.reduce` (because `src/knowledgereduce/reduce/__init__.py` imports `KnowledgeReducer` which imports `knowledgereduce.resolve`).
- **Resolution & Guard**: Resolve `DEFAULT_FUNCTIONAL_PREDICATES` lazily once per `cluster_claims()` call inside `_resolve_functional_vocab()` and pass `functional_vocab` explicitly down into `_claims_compatible_for_merge` and `_cluster_dense_bucket`, keeping hot loops cycle-free and verified by dual-order import tests in `tests/meta/test_governance_and_invariants.py`.

---

## Lesson 4: Enabling Root Benchmark Imports Under `uv run pytest`
- **Symptom**: Golden regression tests importing modules from `benchmarks/civichonors_book_benchmark.py` failed during fresh editable installs without `pythonpath = ["."]` configured.
- **Resolution**: Configure `pythonpath = ["."]` under `[tool.pytest.ini_options]` in `pyproject.toml` so `tests/golden/test_civichonors_book_golden.py` resolves `benchmarks/` consistently across local virtualenv and CLI runners.

---

## Lesson 5: Stop-Word Saturation & Structural Heading Dominance in DuckDB + GraphRAG
- **Symptom**: Natural-language questions ("When and where did...") returned off-target generic sentences or bare Title-Case section headings in `HybridGraphRAGRetriever`.
- **Root Cause**: Raw SQL `LIKE` queries in `src/knowledgereduce/storage/base.py` tokenized stop words and high-frequency corpus terms with equal weight, while short unpunctuated headings achieved higher token overlap density than full declarative sentences in `src/knowledgereduce/query/graphrag.py`.
- **Resolution**: Filter query stop words via `tokenize_search_query()`, score candidates with IDF-weighted lexical overlap + bounded provenance bonus + `0.75` structural heading scaling on both lexical and semantic scores (`_is_structural_heading` in `src/knowledgereduce/query/graphrag.py`), and maintain retrieval regressions in `tests/unit/test_query.py`.

---

## Lesson 6: Asymmetric Years, Formal APA Citations & Atomic Triple Inheritance
- **Symptom**: Real-world *Civic Honors: The Book* evaluation (`benchmarks/civichonors_book_benchmark.py`) retained 11/12 core reference facts (`0.9167`) because an undated narrative sentence absorbed the formal APA citation (`Carlsen, C. J., Lindahl, N., & Lindahl, S. (2004)...`), while non-functional descriptive paraphrases were overly split on `object_literal` text and secondary claims lost grounded triples during cluster merges.
- **Resolution**: In `src/knowledgereduce/resolve/blocking.py`, restrict literal blocking to functional predicates (plus explicit differing `object_id`s), block merges across asymmetric APA references and asymmetric 4-digit years (except unpunctuated verbatim heading fragments subsumed in longer dated sentences), and inherit complete grounded triples and missing provenance atomically inside `src/knowledgereduce/reduce/reducer.py`.

---

## Lesson 7: Zero-GitHub-Actions-Minutes Stratified Local CI & Maker/Checker Audit
- **Problem**: Frequent PRs across multi-phase milestones consume GitHub Actions minutes rapidly when triggered automatically on every push and pull request.
- **Resolution**: Configure `.github/workflows/ci.yml` and `.github/workflows/pr-governance.yml` for manual `workflow_dispatch` only, run complete stratified validation locally via `Makefile` (`make canary`, `make smoke-pr`, `make local-ci`, `make golden`), guard `main` pushes with `.agents/hooks.json` (`scripts/hooks/pre_pr_safety_gate.py`), automate PR lifecycle and lingering-branch audits with `scripts/github_pr_helper.py`, and keep `CHANGELOG.md` and `docs/plans/` synchronized on every PR.

---

## Lesson 8: Pre-Warmed Stateless Claim Embeddings & Empty-Delta Incremental Refresh
- **Symptom**: First queries against freshly stored DuckDB+Parquet layers paid full cold vector-index build latency, while re-ingesting mostly unchanged corpora re-processed unchanged sources unnecessarily.
- **Resolution & Guard**: Wire `incremental_from_layer` and `build_embeddings_index` (`src/knowledgereduce/pipeline/config.py`, `src/knowledgereduce/pipeline/runner.py`) to skip unchanged web/local sources via prior `content_sha256` digests, record parent lineage automatically, guard empty-claim delta layers before Parquet embedding writes, and verify across both `DuckDBParquetStore` and `MemoryGraphStore` in `tests/unit/test_pipeline_incremental.py`.

---

## Lesson 9: Shared Analytics Payloads & GFM-Safe Markdown Export
- **Design Pattern**: Rather than duplicating centrality, community detection, shortest-path, or lineage aggregation logic across CLI (`src/knowledgereduce/cli.py`) and MCP (`src/knowledgereduce/mcp/server.py`), route both interfaces through shared helpers (`build_layers_payload`, `build_layer_lineage_payload`, `build_graph_analytics_payload`) and escape newlines and pipe characters (`|`) cleanly in `src/knowledgereduce/export/markdown_export.py` (tested in `tests/unit/test_markdown_and_analytics_surfaces.py` and `tests/integration/test_mcp_server.py`).

---

## Lesson 10: Precomputing `O(N)` Claim Features & Zero-Copy Fixed-Size Arrow Embeddings
- **Bottleneck**: Profiling `v1.3.0` showed `_claims_compatible_for_merge` recomputed `_YEAR_RE`, `_NUMBER_RE`, and `_APA_REF_RE` repeatedly inside `O(k^2)` dense-bucket loops (`89%` of profiled `1K` reduce time), while `save_claim_embeddings` / `load_claim_embeddings` boxed Python floats via `arr.tolist()` / `.to_pylist()` on every read.
- **Resolution & Guard**: Precompute frozen `@dataclass(slots=True)` `_ClaimMergeFeatures` once per claim in `src/knowledgereduce/resolve/blocking.py`, store embeddings via `pa.FixedSizeListArray` with `(mtime_ns, size)` in-memory caching + explicit write/delete eviction + backward-compatible variable-size `list<float32>` fallback in `src/knowledgereduce/storage/duckdb_store.py`, and verify across `tests/unit/test_storage.py` (`1K` reduce `< 0.5s`, `10K` cold scaling `< 5s`).

---

## Lesson 11: Clause-Stop Boundaries Pair With Temporal Conflict Detection
- **Trade-off Discovered**: Adding clause-stop boundaries (`during|while|since|from`) in `src/knowledgereduce/map/nlp.py` merged all paraphrase clusters on `golden_50_docs` (`bcubed_f1`: `0.9726` -> `1.0000`), but normalizing `"studied at University of Kansas during the spring of 2002"` and `"...2004"` to the same `object_literal` (`"University of Kansas"`) hides year contradictions if conflict detection only inspects object values.
- **Resolution & Guard**: Inside `resolve_claim_conflicts()` (`src/knowledgereduce/reduce/conflicts.py`), when a functional group shares a normalized object value, check mutually exclusive single 4-digit years via the shared `_resolve_bucket_conflict` helper (`::year` conflict keys), snapshot `benchmarks/datasets/civichonors_book/baseline_v1_3_0.json`, ratchet `DEFAULT_REGRESSION_FLOORS` in `benchmarks/civichonors_book_benchmark.py`, and lock both behaviors in `tests/unit/test_map_resolve_reduce.py`.

---

## Lesson 12: Persistent DuckDB Session, Two-Stage GraphRAG Hydration & Bounded Graph Cache
- **Bottleneck**: After `v1.4.0` moved embeddings to `FixedSizeListArray`, warm `HybridGraphRAGRetriever.retrieve()` still averaged `51.2 ms` uninstrumented because `DuckDBParquetStore._query_rows()` opened a fresh `duckdb.connect(":memory:")` per call, hydrated up to `400` full Pydantic `Claim` rows before ranking, scanned empty `conflicts.parquet`, and re-parsed large entity `evidence_json` arrays during `get_k_hop_subgraph()`.
- **Resolution & Guard**: Reuse an `RLock`-guarded persistent `:memory:` DuckDB connection inside `src/knowledgereduce/storage/duckdb_store.py`, score lightweight `ClaimSummary` projections (`src/knowledgereduce/storage/base.py`, `src/knowledgereduce/query/graphrag.py`) hydrating full `Claim` models only for `top_k` winners, cache `(st_mtime_ns, st_size)`-validated entity/relation indices (bounded by `graph_cache_max_rows=50_000` with SQL fallback) evicted in `_invalidate_layer_caches()`, and lock parity/eviction in `tests/unit/test_storage.py` and `tests/unit/test_query.py` (`10.7 ms` steady Book warm query).

---

## Lesson 13: Pre-Registration Claim Hygiene & Structural Grounding Quality Weights
- **Symptom**: Real-world *Civic Honors: The Book* evaluation surfaced `37` unpunctuated chapter/section headings and `10` rhetorical `?` questions still emitted as `Claim` nodes, while single-document grounded `(S, P, O)` claims scored almost identically (`59.51` vs `57.43`) to ungrounded sentences.
- **Resolution & Guard**: Filter heading lines into downstream `contextual_notes = "Section: ..."` provenance and exclude `?` questions before Pass-1 entity registration when `skip_headings=True` / `skip_questions=True` in `DeterministicNLPMapper` (`src/knowledgereduce/map/nlp.py`), add bounded `+5.0`/`+2.5` structural grounding weights to `Claim.quality_score` (`src/knowledgereduce/models/schemas.py`), lock expectations in `tests/unit/test_models.py` and `tests/unit/test_map_resolve_reduce.py`, and verify stacked multi-source behavior in `benchmarks/multisource_stack_benchmark.py` and `tests/golden/test_multisource_stack_golden.py`.

---

## Lesson 14: Parameterized DuckDB SQL Pushdown, Metadata-Only Reads & Atomic Backup-Swap Writes
- **Bottleneck**: Filtering or paginating top-k claims in `QueryBuilder.execute_claims()` hydrated up to `100,000` full `Claim` models into Python before sorting/slicing (`1,004.6 ms` at `50K` claims), incremental hash lookups loaded entire layers via `load_layer()`, and `DuckDBParquetStore.save_layer()` removed existing target directories prior to renaming a fixed staging directory.
- **Resolution & Guard**: Push `tags_any` (`list_has_any`), UTC range filters (`TRY_CAST(... AS TIMESTAMPTZ)`), `subject_id`/`predicate`/`source_id`, allowlisted `sort_by`, and `LIMIT`/`OFFSET` into `DuckDBParquetStore.list_claims()` and `MemoryGraphStore.list_claims()` (`6.82 ms` median top-10 at `50K` claims), expose metadata-only `get_layer_manifest()`/`list_source_hashes()`, serialize `save_layer()` with `_write_lock` + unique `.staging_` dirs + backup-swap rollback (`src/knowledgereduce/storage/duckdb_store.py`, `src/knowledgereduce/query/builder.py`), and verify behavior in `tests/unit/test_storage.py` and `tests/unit/test_query.py`.

---

## Lesson 15: Guarded Shared Claims During Atomic Batch Conflict Adjudication
- **Risk Identified**: Clearing `needs_review=False` or removing all `CONTRADICTS` edges for every participating claim ID in a resolved conflict can clear flags prematurely when the same claim participates in another still-open dispute.
- **Resolution & Guard**: Compute per-conflict resolved claim sets alongside remaining unresolved conflict claim sets in `adjudicate_conflicts()` (`src/knowledgereduce/reduce/conflicts.py`), clearing `needs_review` and removing `CONTRADICTS` edges only when the claim/edge no longer belongs to any open `needs_review=True` conflict, locked by multi-conflict regression tests in `tests/unit/test_map_resolve_reduce.py`.

---

## Lesson 16: YAML `date` Objects Inside `yaml.safe_load()` Frontmatter Metadata
- **Bug Caught**: Live end-to-end testing on Markdown files containing unquoted ISO frontmatter (`date: 2024-06-15`) crashed `DuckDBParquetStore.save_layer()` (`src/knowledgereduce/storage/duckdb_store.py`) with `TypeError: Object of type date is not JSON serializable` because PyYAML parses unquoted dates into `datetime.date` objects while `SourceDocument.metadata` was persisted with bare `json.dumps(...)`.
- **Resolution & Guard**: Recursively normalize YAML frontmatter values via `_json_safe_value()` inside `src/knowledgereduce/ingest/files.py` (alongside `yaml.YAMLError` fallback and `author: null` normalization), add `default=str` to `json.dumps` calls across `src/knowledgereduce/storage/duckdb_store.py`, `src/knowledgereduce/map/structured.py`, `src/knowledgereduce/export/json_export.py`, and `src/knowledgereduce/export/sharded.py`, and lock end-to-end YAML `date` ingestion -> DuckDB persistence -> `QueryBuilder` filtering in `tests/unit/test_ingest.py`, `tests/unit/test_storage.py`, and `tests/unit/test_pipeline_incremental.py`.
