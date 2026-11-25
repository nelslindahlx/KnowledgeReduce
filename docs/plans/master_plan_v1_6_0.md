# Master Plan — KnowledgeReduce v1.6.0

**Tracking Roadmap:** `#57` (`v1.6.0 Roadmap: Core Engine Pushdown, Cross-Layer Dedup, Directory/PDF Ingest & Agent-Complete MCP`)

---

## Context & Empirical Evaluation of v1.5.0

`v1.5.0` (`tag: v1.5.0`) shipped sub-15 ms uninstrumented Book warm GraphRAG (`10.7 ms` steady), claim hygiene (`0` headings / `0` questions, `grounded_triple_rate = 0.2821`), the offline multi-source stacked/incremental golden benchmark, and `95.70%` test coverage across `136` passing tests.

Follow-up profiling and architecture inspection on `v1.5.0` surfaced four concrete engineering bottlenecks and missing product capabilities for `v1.6.0`:

| # | Finding (Observed in v1.5.0) | Primary Module(s) | Phase |
|---|---|---|---|
| **1** | `QueryBuilder.execute_claims()` fetches up to `100,000` full Pydantic `Claim` objects into Python to sort/slice (`1,004.6 ms` top-10 at `50K` claims); `load_layer_source_hashes()` and `build_layer_lineage_payload()` call `load_layer()`; `save_layer()` uses a fixed staging dir and deletes `target_dir` before rename; `HybridGraphRAGRetriever.retrieve()` builds an O(N) `id_to_sem` dict per query. | `src/knowledgereduce/storage/base.py`, `duckdb_store.py`, `memory.py`, `query/builder.py`, `query/graphrag.py`, `pipeline/runner.py`, `mcp/server.py` | Phase 1 (`#53`) |
| **2** | `StackManager.merge_layers(..., reconcile=True)` reconciles entities and functional conflicts but does not deduplicate equivalent claims with distinct IDs across independently mapped layers; `_map_single_doc_worker()` drops `structured_config` and heading/question options under `max_workers > 1`; internally created `DuckDBParquetStore` instances are not closed automatically. | `src/knowledgereduce/reduce/reducer.py`, `stack/manager.py`, `pipeline/config.py`, `pipeline/runner.py`, `cli.py` | Phase 2 (`#54`) |
| **3** | Local ingestion only accepts individual files (`--file`), lacks optional `.pdf` extraction (`SourceType.PDF`), and `MarkdownConnector` extracts `title`/`author` from frontmatter without `date`/`published_at` or `tags`. | `src/knowledgereduce/models/enums.py`, `pyproject.toml`, `ingest/files.py`, `pipeline/`, `cli.py` | Phase 3 (`#55`) |
| **4** | MCP exposes `14` tools (`0` resources, `0` prompts), lacks `read_ingested_checkpoint`, `inspect_entity`, and atomic batch `resolve_conflicts`; resolving N conflicts requires N sequential `CURATED` layers; CLI lacks `kr resolve-conflicts`, `kr inspect`, and `kr doctor`. | `src/knowledgereduce/reduce/conflicts.py`, `mcp/server.py`, `cli.py`, Docs, SemVer `1.6.0` | Phase 4 (`#56`) |

---

## Planned Execution Phases (Maker/Checker PRs)

### Phase 1 (`#53`) — DuckDB SQL Pushdown, Crash-Safe `save_layer` & Metadata-Only Reads (`feat/v1-6-sql-pushdown-and-storage-hardening`)
- Extend `GraphStore.list_claims()`, `DuckDBParquetStore.list_claims()`, and `MemoryGraphStore.list_claims()` with parameterized SQL / matching pushdown for `tags_any`, `recorded_after`/`recorded_before`, `published_after`/`published_before`, `subject_id`, `predicate`, `source_id`, `sort_by`, and `descending`.
- Add `filter_published_range`, `filter_subject`, `filter_predicate`, and `filter_source` to `QueryBuilder` and delegate `execute_claims()` directly to `list_claims()` (`< 100 ms` top-10 at `50K` claims).
- Add `get_layer_manifest()` and `list_source_hashes()` metadata-only storage APIs and wire `load_layer_source_hashes()` + `build_layer_lineage_payload()` to them.
- Harden `DuckDBParquetStore.save_layer()` with `_write_lock`, unique temp staging dirs, and atomic backup-swap rollback on overwrite errors; eliminate per-query O(N) `id_to_sem` dict construction in `HybridGraphRAGRetriever.retrieve()`.

### Phase 2 (`#54`) — `StackManager` Cross-Layer Claim Dedup & `PipelineRunner` Parity (`feat/v1-6-stack-dedup-and-pipeline-parity`)
- Extract and export shared claim cluster merge helper in `src/knowledgereduce/reduce/reducer.py`.
- Add `deduplicate_claims: bool = True`, `semantic_threshold: float = 0.84`, and `min_claim_length: int = 0` to `StackManager.merge_layers()` and `stack_overlay()`, deduplicating cross-layer claims and remapping relation endpoints under `reconcile=True`.
- Add `skip_headings`/`skip_questions` on `PipelineConfig`, forward `structured_config`/`skip_headings`/`skip_questions` inside `_map_single_doc_worker()`, and close internally constructed stores cleanly in `PipelineRunner` and `cli.py`.

### Phase 3 (`#55`) — Directory/Glob Ingest, Optional `PDFConnector` & Markdown Frontmatter (`feat/v1-6-directory-pdf-frontmatter-ingest`)
- Add `SourceType.PDF = "pdf"` and optional `pdf = ["pypdf>=5.0"]` extra in `pyproject.toml` + `uv.lock`.
- Parse frontmatter `published_at`/`date` and normalized `tags` in `MarkdownConnector` and propagate document tags to claims in `DeterministicNLPMapper`.
- Add path-sandboxed `PDFConnector` and `DirectoryConnector` / `ingest_local_directory()`, wire `LocalDirectorySourceConfig` / `local_directories` in `PipelineConfig` & `PipelineRunner.ingest()`, and add `--dir`/`--glob` to `kr ingest`.

### Phase 4 (`#56`) — Agent-Complete MCP, Batch Conflict Adjudication, CLI Ergonomics & `v1.6.0` Release (`feat/v1-6-agent-mcp-cli-and-release`)
- Add `ConflictResolutionDecision` and atomic `adjudicate_conflicts()` in `src/knowledgereduce/reduce/conflicts.py`.
- Add MCP tools `read_ingested_checkpoint`, `inspect_entity`, and `resolve_conflicts` (`14 -> 17` tools), wire new ingest/map/stack options, and register 3 `@server.resource` endpoints + 2 `@server.prompt` templates.
- Add `kr resolve-conflicts`, `kr inspect`, and `kr doctor` CLI commands.
- Bump SemVer `1.5.0 -> 1.6.0` (`pyproject.toml`, `__init__.py`, `CITATION.cff`, `tests/unit/test_smoke.py`, `uv.lock`), sync all docs + `lessons_learned.md` + `CHANGELOG.md`, verify `make local-ci && make golden && make audit-prs`, tag `v1.6.0`, and publish GitHub Release `v1.6.0`.

---

## Verification Contract
- All `.github/workflows/*.yml` stay restricted to manual `workflow_dispatch:`.
- Every PR runs local checks (`make canary && make lint` for pure plan docs; `make local-ci && make golden` for code/release PRs), independent Checker diff audit, and `make audit-prs` (`0` open PRs / `0` lingering branches).
