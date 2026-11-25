# Latest Verification Walkthrough — KnowledgeReduce v1.4.0

1. **Roadmap Execution (`#32`–`#36`)**:
   - **Phase 1 (`#32`, PR #38)**: Precomputed `_ClaimMergeFeatures` in `cluster_claims()`, Arrow `pa.FixedSizeListArray` zero-copy claim embeddings I/O, and read-only DuckDB/Parquet session caching cut 10K cold runtime from `13.361s` → `4.155s` (`reduce: 2.943s`, `warm query: 0.180s`, `peak traced: 52.49 MiB`).
   - **Phase 2 (`#33`, PR #39)**: Tightened SPO boundaries, added `_ORG_RE`/`_CAMEL_ENTITY_RE` publisher patterns, dominant non-Press `"the university"` coreference, modal/passive canonical predicates, single-year `::year` temporal conflict buckets, and `baseline_v1_3_0.json` regression gates.
   - **Phase 3 (`#34`, PR #40)**: Added `SourceType.HTML` (`HTMLConnector`), unified incremental content-hash skipping (`load_layer_source_hashes`, `filter_unchanged_documents`), and exposed full CLI/MCP parity (`--incremental-from`, `--parent-layer`, `--build-index`, `kr index`).
   - **Phase 4 (`#35`)**: Bumped SemVer to `1.4.0`, synced docs (`README.md`, `docs/mcp_antigravity.md`, `docs/conflicts_and_benchmarks.md`, `lessons_learned.md`, `CHANGELOG.md`), added mechanical doc-parity meta-tests, and lifted suite coverage above `94%`.
2. **Local CI Gate (`make local-ci`)**:
   - Verified clean meta/governance tests (`tests/meta/`), `ruff check`, `ruff format --check`, `mypy src`, and full `pytest` suite (`>= 94%` coverage) with zero GitHub Actions runner minutes consumed (`workflow_dispatch`-only workflows).
3. **Real-World Golden & Scaling Verification (`make golden` + `benchmarks/run_benchmark.py --scale 1000 10000`)**:
   - *Civic Honors: The Book* (`139,596` chars / `21,765` words) completed in `1.397s` cold (`0.627s` reduce) with `18/18` metrics improved vs. `baseline_v1_1_0.json`, `grounded_triple_rate = 0.2614` (`43` semantic relations), `claim_connectivity_rate = 0.5131`, `isolated_node_ratio = 0.4473`, `1.0000` recall/retention/Hit@1/MRR@5.
   - 50-doc frozen golden achieved `bcubed_f1 = 1.0000` (`bcubed_recall = 1.0000`, `conflict_detection_recall = 1.0000`).
