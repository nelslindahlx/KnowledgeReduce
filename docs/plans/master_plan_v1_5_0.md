# Master Plan — KnowledgeReduce v1.5.0

**Tracking Roadmap:** `#46` (`v1.5.0 Roadmap: Sub-15ms GraphRAG, Claim Hygiene & Structural Quality, Multi-Source Golden & 95%+ Coverage`)

---

## Context & Empirical Evaluation of v1.4.0

`v1.4.0` (`tag: v1.4.0`) cut `1K` reduce time to `0.387 s` and `10K` cold scaling to `4.246 s`, raised *Civic Honors: The Book* `grounded_triple_rate` to `0.2614` (`43` semantic relations) and `claim_connectivity_rate` to `0.5131`, lowered `isolated_node_ratio` to `0.4473` (`501` isolated claims, `0` isolated entities), lifted `golden_50_docs` `bcubed_f1` to `1.0000`, reached `94.67%` total test coverage (`124 passed`), and maintained zero automatic GitHub Actions minutes.

Profiling and diagnostic inspection of `v1.4.0` surfaced four focused targets for `v1.5.0`:

| # | Finding (Observed in v1.4.0) | Primary Module(s) | Phase |
|---|---|---|---|
| **1** | Uninstrumented Book warm query averages `51.2 ms` (`load_claim_embeddings` is `0.190 ms`, while `DuckDBParquetStore._query_rows()` opens a fresh `duckdb.connect(":memory:")` per read and `HybridGraphRAGRetriever.retrieve()` hydrates full `Claim` models for all `candidate_pool_size=200` candidates + scans empty `conflicts.parquet`). | `src/knowledgereduce/storage/duckdb_store.py`, `src/knowledgereduce/storage/base.py`, `src/knowledgereduce/query/graphrag.py` | Phase 1 (`#42`) |
| **2** | Book graph contains `37` unpunctuated chapter/section headings and `10` rhetorical `?` questions as `Claim` nodes; `259` linked claims still lack SPO triples; `Claim.quality_score` (`57.0–61.5`) awards `0` points for structural `(subject_id, predicate, object)` grounding. | `src/knowledgereduce/map/nlp.py`, `src/knowledgereduce/models/schemas.py` | Phase 2 (`#43`) |
| **3** | Book regression floors still enforce `v1.3.0` minimums (`grounded_triple_rate >= 0.20`, `total_seconds <= 10.0`), and no offline multi-source stacked/incremental golden benchmark exists for `HTMLConnector` + `incremental_from_layer` + `StackManager` + GraphRAG conflict surfacing + Markdown export. | `benchmarks/civichonors_book_benchmark.py`, `benchmarks/multisource_stack_benchmark.py`, `tests/golden/` | Phase 3 (`#44`) |
| **4** | Small test-coverage pockets remain below `90%` (`structured.py` `85%`, `storage/base.py` `82%`, `ingest/base.py` `87%`, `export/sharded.py` `89%`); `Makefile` `test` gate is still `85%`; SemVer/CHANGELOG/lessons/benchmark docs need `v1.5.0` alignment. | `tests/unit/`, `Makefile`, Docs, SemVer `1.5.0` | Phase 4 (`#45`) |

---

## Planned Execution Phases (Maker/Checker PRs)

### Phase 1 (`#42`) — Sub-15ms Warm GraphRAG (`feat/v1-5-fast-warm-graphrag`)
- **Projection model (`src/knowledgereduce/storage/base.py`, `src/knowledgereduce/storage/__init__.py`)**:
  - Add frozen `@dataclass(frozen=True, slots=True)` `ClaimSummary` (`claim_id`, `statement`, `reliability`, `quality_score`, `source_title`, `author_creator`, `contextual_notes`).
- **Persistent read session & claim summary cache (`src/knowledgereduce/storage/duckdb_store.py`, `src/knowledgereduce/storage/memory.py`)**:
  - Reuse a thread-safe persistent `:memory:` DuckDB read session (`_read_con`, `_con_lock`, `close()`, context manager) across `_query_rows()`, `load_layer()`, and `get_k_hop_subgraph()`.
  - Cache `ClaimSummary` projections keyed by `(st_mtime_ns, st_size)` via direct PyArrow column reads, evicting in `_invalidate_layer_caches()` on writes/deletes; expose `search_claim_summaries_lexical` and `get_claim_summaries_by_ids`.
  - Guard empty `conflicts.parquet` scans in `get_k_hop_subgraph()` via `pq.read_metadata(cf_pq).num_rows > 0`.
- **Two-stage GraphRAG hydration (`src/knowledgereduce/query/graphrag.py`)**:
  - Score candidates over `ClaimSummary` projections (with `contextual_notes` included in `provenance_text`) and hydrate full `Claim` objects only for `top_k` winners, preserving fallback to full-claim queries for custom stores.

### Phase 2 (`#43`) — Claim Hygiene, Section Context, SPO Density & Structural Quality Score (`feat/v1-5-claim-hygiene-and-quality`)
- **Heading & question hygiene + section context (`src/knowledgereduce/map/nlp.py`)**:
  - Add `skip_headings: bool = True` and `skip_questions: bool = True` options to `DeterministicNLPMapper`.
  - Capture heading lines as `current_section` before Pass-1 entity registration (preserving author/date bylines) and attach `contextual_notes = f"Section: {section}"` to downstream claims.
  - Exclude interrogative sentences (`?`) before Pass-1 entity registration when `skip_questions=True`.
  - Expand safe non-colliding narrative predicates in `_ANCHORED_VERB_MAP` and safe entity-anchored triple extraction patterns (`grounded_triple_rate >= 0.28`, `isolated_node_ratio <= 0.44`) without colliding with `_IN`/`_AT`/`_ON`/`_YEAR`/`_DATE` functional suffixes or regressing `heading_noise_fp_count == 0`.
- **Structural grounding weight (`src/knowledgereduce/models/schemas.py`)**:
  - Award `+5.0` inside `Claim.quality_score` for complete `(subject_id, predicate, object_id|object_literal)` triples (`+2.5` for `(subject_id, predicate)`), bounded `[0.0, 100.0]`, keeping ungrounded claim scores backward-compatible.

### Phase 3 (`#44`) — Multi-Source Stacked/Incremental Golden Benchmark & Floor Ratchet (`feat/v1-5-multisource-golden-and-floors`)
- **Book baseline & floor ratchet (`benchmarks/datasets/civichonors_book/baseline_v1_4_0.json`, `benchmarks/civichonors_book_benchmark.py`, `tests/golden/test_civichonors_book_golden.py`)**:
  - Snapshot `baseline_v1_4_0.json`, export `BASELINE_V14_PATH`, and ratchet `DEFAULT_REGRESSION_FLOORS` (`claim_connectivity_rate >= 0.50`, `grounded_triple_rate >= 0.26`, `mean_quality_score >= 59.0`, `isolated_node_ratio <= 0.45`, `total_seconds <= 4.0`).
- **Offline multi-source golden (`benchmarks/multisource_stack_benchmark.py`, `tests/golden/test_multisource_stack_golden.py`, `Makefile`)**:
  - Validate `HTMLConnector` + `MarkdownConnector` -> `base` layer -> `incremental_from_layer="base"` delta (`skipped_unchanged == 1`, `parent_layer_ids == ["base"]`) -> disputed overlay (`3` contradictions) -> `StackManager.stack_layers` (`PRESERVE_DISPUTE`) -> `IntegrityValidator(strict=True)` -> `conflict_detection_recall == 1.0` (`3/3`) -> GraphRAG `Hit@1 == 1.0` -> `export_layer_markdown` + `analyze_graph`.
  - Run both strict golden benchmarks under `make golden`.

### Phase 4 (`#45`) — Coverage Hardening (`>=95%`), Docs Sync & `v1.5.0` Release (`chore/v1-5-coverage-docs-release`)
- **Coverage & CI gate**: Cover remaining branches in `structured.py`, `export/sharded.py`, `export/graph_formats.py`, `ingest/base.py`, and `query/analytics.py`; raise `Makefile` `test` gate from `85%` -> `95%` (target total coverage `>= 95.5%`).
- **Release & docs**: Bump SemVer to `1.5.0` (`pyproject.toml`, `src/knowledgereduce/__init__.py`, `tests/unit/test_smoke.py`, `uv.lock`); sync `README.md`, `docs/conflicts_and_benchmarks.md`, `lessons_learned.md` (Lessons 12–13), `CHANGELOG.md`, `docs/plans/implementation_plan.md`, and `docs/plans/latest_walkthrough.md`; verify `make local-ci && make golden && make audit-prs` and push annotated tag `v1.5.0`.

---

## Target Improvements (`v1.4.0` -> `v1.5.0`)

| Metric | `v1.4.0` (Measured) | `v1.5.0` Target |
|---|---:|---:|
| Book uninstrumented warm query avg | `51.2 ms` | **`< 15 ms`** |
| Book heading / question claims | `37` / `10` | **`0` / `0`** |
| Book `grounded_triple_rate` | `0.2614` | **`>= 0.2800`** |
| Book `mean_quality_score` | `57.97` | **`>= 59.0`** |
| Multi-source stacked/incremental golden | *(none)* | **Strict CLI + pytest gate (`3/3` conflicts, `Hit@1 == 1.0`)** |
| Suite test coverage (`make test`) | `94.67%` (`85%` gate) | **`>= 95.5%`** (`95%` gate) |
| Automatic GitHub Actions minutes | `0` | **`0`** (`workflow_dispatch`-only) |

## Verification Contract
- All `.github/workflows/*.yml` stay restricted to manual `workflow_dispatch:`.
- Every PR runs local checks (`make canary && make lint` for pure plan docs; `make local-ci && make golden` for code/benchmark/release PRs), independent Checker diff audit, and `make audit-prs` (`0` open PRs / `0` lingering branches).
