# Master Plan — KnowledgeReduce v1.4.0

**Tracking Roadmap:** `#36` (`v1.4.0 Roadmap: Performance Engine, Precision/Density, CLI/MCP Parity & Doc Hygiene`)

---

## Context & Empirical Evaluation of v1.3.0

`v1.3.0` (`tag: v1.3.0`) delivered **18/18** metric improvements on *Civic Honors: The Book* (`benchmarks/civichonors_book_benchmark.py`) compared against `baseline_v1_1_0.json` (`core_entity_name_recall: 1.0000`, `core_entity_typed_recall: 1.0000`, `core_entity_type_accuracy: 1.0000`, `alias_merge_recall: 1.0000`, `core_fact_retention: 1.0000` (`12/12`), `retrieval_hit_at_1: 1.0000`, `retrieval_mrr_at_5: 1.0000`, `cross_type_duplicate_count: 0`, `heading_noise_fp_count: 0`), lifted `golden_50_docs` `bcubed_f1` to `0.9726`, and maintained **zero** automatic GitHub Actions minutes across PRs `#28`–`#31` and `v1.3.0` under `make local-ci`.

Profiling `v1.3.0` (`cProfile`, cluster error breakdown, coverage audit, and CLI/MCP/doc inspection) surfaced six concrete bottlenecks and gaps for `v1.4.0`:

| # | Finding (Observed in v1.3.0) | Primary Module(s) | Phase |
|---|---|---|---|
| **1** | `89%` of profiled `1K` reduce time (`8.43s` / `9.43s`; `446,422` `findall` + `226,410` `match` calls) and `67%` of book reduce time is spent recomputing `_YEAR_RE`, `_NUMBER_RE`, and `_APA_REF_RE` inside `O(k^2)` blocking checks (`10K` cold wall time rose from `~13.36s` to `~27.00s`). | `src/knowledgereduce/resolve/blocking.py` | Phase 1 (`#32`) |
| **2** | `save_claim_embeddings` / `load_claim_embeddings` box Python floats via `arr.tolist()` / `.to_pylist()`, while each `HybridGraphRAGRetriever.retrieve()` opens up to `7` separate `duckdb.connect(":memory:")` sessions and reloads Parquet from disk (`236–346ms` warm). | `src/knowledgereduce/storage/duckdb_store.py` | Phase 1 (`#32`) |
| **3** | Last `2` split themes in `golden_50_docs` (`gold_denver_loc`, `gold_ku_origin`; `bcubed_recall = 0.9467`) miss clause-stop boundaries in `_FACTUAL_PATTERNS`; `547 / 1029` book claims (`53.2%`) remain isolated (`isolated_node_ratio = 0.4884`, `grounded_triple_rate = 0.2021`); minor non-gold entity typing slips (`Fortune Magazine`, `Institute of ...`, `HarperCollins`, `McGraw-Hill`). | `src/knowledgereduce/map/nlp.py` | Phase 2 (`#33`) |
| **4** | `DEFAULT_REGRESSION_FLOORS` still enforces loose `v1.1.0` floors (`>= 0.70` typed recall, `>= 0.90` fact retention, `<= 12` heading noise FPs, `<= 30s`). | `benchmarks/civichonors_book_benchmark.py` | Phase 2 (`#33`) |
| **5** | `PipelineConfig.incremental_from_layer` and `build_embeddings_index` are not yet exposed on `kr` CLI commands or MCP tools, and local `.html`/`.htm` files lack a dedicated connector. | `src/knowledgereduce/cli.py`, `src/knowledgereduce/mcp/server.py`, `src/knowledgereduce/ingest/files.py` | Phase 3 (`#34`) |
| **6** | `README.md`, `docs/mcp_antigravity.md`, and `docs/conflicts_and_benchmarks.md` carry `v1.1.0` counts/instructions; total coverage (`91.69%`) leaves small untested pockets (`ingest/security.py`, `json_export.py`, `security.py`, `cli.py`). | Docs, `tests/meta/`, `security.py`, `export/json_export.py`, `cli.py` | Phase 4 (`#35`) |

---

## Planned Execution Phases (Maker/Checker PRs)

### Phase 1 (`#32`) — Performance & Scaling Engine (`feat/v1-4-perf-blocking-arrow`)
- **Precompute `O(N)` claim merge features (`src/knowledgereduce/resolve/blocking.py`)**:
  - Add frozen `@dataclass(slots=True)` `_ClaimMergeFeatures` (`subject_id`, `norm_pred`, `is_functional`, `norm_val`, `object_id`, `is_apa_ref`, `years`, `numbers`, `norm_stmt`, `ends_punct`) computed once per claim in `cluster_claims()`.
  - Retain `_claims_compatible_for_merge(a, b, functional_vocab=...)` as a thin backward-compatible wrapper over `_features_compatible(fa, fb)` so Stage 2 and Stage 3 hot loops run pure cached set/boolean comparisons.
- **Zero-copy Arrow embeddings & DuckDB connection sharing (`src/knowledgereduce/storage/duckdb_store.py`)**:
  - Persist `claim_embeddings.parquet` using `pa.FixedSizeListArray.from_arrays(pa.array(arr.ravel(), type=pa.float32()), dim)` and decode via `combine_chunks().values.to_numpy(zero_copy_only=False).reshape(n, dim)` with a clean fallback for legacy `list<float32>` Parquet files.
  - Add an mtime + file-size validated in-memory embedding cache on `DuckDBParquetStore`, explicitly evicted in `save_layer` and `delete_layer`.
  - Share a single `with duckdb.connect(":memory:") as con:` session per `load_layer()` and `get_k_hop_subgraph()` invocation.
- **Verification**: Add legacy Parquet fallback & cache eviction tests (`tests/unit/test_storage.py`) and feature-parity tests (`tests/unit/test_blocking_and_reducer.py`); verify `reduce_seconds < 0.70s` (`1K` & Book), warm GraphRAG `< 50ms`, and `10K` cold `< 10.0s`.

### Phase 2 (`#33`) — Extraction Precision, Triple Density & Golden Floor Ratchet (`feat/v1-4-nlp-precision-and-density`)
- **Close remaining `golden_50_docs` splits (`src/knowledgereduce/map/nlp.py`)**:
  - Extend `_FACTUAL_PATTERNS` stop boundaries (`AFFILIATION`: `during|while|since|from`; `LOCATION_OR_ORIGIN`: `with|where|while|during|[a-z]+ing`) and snap extracted objects to known entity prefixes (`University of Kansas`, `Denver, Colorado`).
- **Entity typing polish & triple density (`src/knowledgereduce/map/nlp.py`)**:
  - Extend `_ORG_RE` and `_NON_PERSON_KEYWORDS` for `Magazine`, `Institute of ...`, and hyphenated publishers (`McGraw-Hill`, `HarperCollins`).
  - Add unambiguous `"the university"` coreference in `_build_pass2_linker()` when a document contains a single dominant university org.
  - Expand `_ANCHORED_AUX_RE` for modal/auxiliary/passive forms (`will <verb>`, `can <verb>`, `must <verb>`, `has been <participle>`, `is designed to`) using strictly non-functional predicates verified against `_ANCHORED_VERB_MAP` suffix collisions in `tests/meta/test_governance_and_invariants.py`.
- **Golden floor ratchet (`benchmarks/civichonors_book_benchmark.py`, `benchmarks/datasets/civichonors_book/baseline_v1_3_0.json`)**:
  - Snapshot `baseline_v1_3_0.json` and raise `DEFAULT_REGRESSION_FLOORS` (`core_entity_name_recall >= 0.98`, `core_entity_typed_recall >= 0.95`, `core_entity_type_accuracy >= 0.95`, `alias_merge_recall >= 0.95`, `core_fact_retention >= 0.98`, `retrieval_hit_at_1 >= 0.95`, `retrieval_mrr_at_5 >= 0.95`, `claim_connectivity_rate >= 0.45`, `grounded_triple_rate >= 0.20`, `cross_type_duplicate_count == 0`, `heading_noise_fp_count == 0`, `isolated_node_ratio <= 0.50`, `total_seconds <= 10.0`).
- **Verification**: Confirm `golden_50_docs` `bcubed_f1 = 1.0000`, Book `grounded_triple_rate >= 0.25`, `isolated_node_ratio <= 0.45`, and `1.00` recall/retention/Hit@1/MRR@5.

### Phase 3 (`#34`) — CLI/MCP Incremental Refresh, Pre-Warmed Indexing & Local HTML Connector (`feat/v1-4-cli-mcp-incremental-parity`)
- **CLI parity (`src/knowledgereduce/cli.py`)**:
  - Add `--incremental-from` and `--store` to `kr ingest`, `--parent-layer` and `--build-index/--no-build-index` (default `True`) to `kr reduce` and `kr stack`, plus `kr index <layer_id> --store <store_dir>`.
- **MCP parity (`src/knowledgereduce/mcp/server.py`)**:
  - Add `incremental_from_layer: str | None = None` to `ingest_source`, plus `parent_layer_ids` and `build_embeddings_index: bool = True` to `resolve_and_reduce` and `stack_layers`.
- **Zero-dependency `HTMLConnector` (`src/knowledgereduce/ingest/files.py`)**:
  - Add offline `.html`/`.htm` extraction via `trafilatura` + `beautifulsoup4` fallback, wired into `ingest_local_file` and `ensure_within_base`.
- **Verification**: Add CLI/MCP/HTML unit & integration tests plus an end-to-end multi-document incremental refresh + stacked conflict golden test in `tests/integration/test_pipeline_e2e.py`.

### Phase 4 (`#35`) — Documentation Parity, Meta-Guards, Coverage Hardening & `v1.4.0` Release (`chore/v1-4-docs-coverage-release`)
- **Doc synchronization & mechanical meta-guards**:
  - Sync `README.md`, `docs/mcp_antigravity.md`, `docs/conflicts_and_benchmarks.md`, `docs/plans/implementation_plan.md`, `docs/plans/latest_walkthrough.md`, `lessons_learned.md`, and `CHANGELOG.md` for `v1.4.0`.
  - Extend `tests/meta/test_governance_and_invariants.py` to enforce MCP tool <-> `docs/mcp_antigravity.md` parity and verify `README.md` matches zero-GitHub-minutes local CI.
- **Coverage hardening**:
  - Cover/clean `src/knowledgereduce/ingest/security.py` and add negative/error-path tests for `src/knowledgereduce/security.py`, `src/knowledgereduce/export/json_export.py`, and `src/knowledgereduce/cli.py` (target `>= 94.0%` coverage).
- **Release**: Align SemVer `1.4.0` across `pyproject.toml`, `src/knowledgereduce/__init__.py`, and `tests/unit/test_smoke.py`; verify `make local-ci`, `make golden`, `10K` scaling (`< 10.0s`), and `make audit-prs`; create annotated tag `v1.4.0`.

---

## Target Improvements (`v1.3.0` -> `v1.4.0`)

| Metric | `v1.3.0` (Measured) | `v1.4.0` Target |
|---|---:|---:|
| `1K` scaling `reduce_seconds` | `3.19s` | **`< 0.70s`** |
| `10K` scaling total cold wall time | `27.00s` | **`< 10.0s`** |
| Warm GraphRAG latency (`1K` / Book) | `236ms` / `326ms` | **`< 50ms`** |
| `golden_50_docs` B-Cubed F1 / Recall | `0.9726` / `0.9467` | **`1.0000` / `1.0000`** |
| Book `grounded_triple_rate` | `0.2021` | **`>= 0.2500`** |
| Book `isolated_node_ratio` | `0.4884` | **`<= 0.4500`** |
| Book `core_fact_retention` / `Hit@1` / `MRR@5` | `1.00` / `1.00` / `1.00` | **`1.00` / `1.00` / `1.00`** (ratcheted floors) |
| Total test coverage | `91.69%` | **`>= 94.0%`** |
| Automatic GitHub Actions minutes | `0` | **`0`** |

## Verification Contract
- All `.github/workflows/*.yml` stay restricted to manual `workflow_dispatch:`.
- Every PR runs `make local-ci`, `make golden`, independent Checker diff audit (`git diff origin/main...HEAD`), and `make audit-prs` (`0` open PRs / `0` lingering branches).
