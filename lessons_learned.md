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
