# Latest Verification Walkthrough — KnowledgeReduce v1.3.0

## Summary of Delivered Capabilities
- **Zero-GitHub-Actions-Minutes Stratified Local CI (`#27`)**: Workflows in `.github/workflows/` are restricted to manual `workflow_dispatch`, paired with `Makefile` (`canary`, `lint`, `typecheck`, `smoke-pr`, `test`, `golden`, `benchmark`, `local-ci`, `audit-prs`), `.agents/` rules/hooks (`scripts/hooks/pre_pr_safety_gate.py`), `scripts/github_pr_helper.py`, `lessons_learned.md`, and `tests/meta/test_governance_and_invariants.py`.
- **Lossless Claim Clustering & Retrieval Accuracy (`#23`)**: Separated functional vs. non-functional predicate blocking, protected asymmetric dated claims and formal APA bibliography citations, added atomic triple/provenance inheritance in `KnowledgeReducer`, and applied `0.75` heading scaling across lexical and semantic Hybrid GraphRAG scores.
- **Incremental Refresh & Pre-Warmed Vector Indexing (`#24`)**: Added `PipelineConfig.incremental_from_layer` (SHA-256 skip-unchanged delta ingestion across local and web connectors + parent lineage) and `PipelineConfig.build_embeddings_index` (stateless `claim_embeddings.parquet` pre-warming).
- **Markdown Knowledge Briefs & Analytics Surfaces (`#25`)**: Added `export_layer_markdown` / `render_layer_markdown`, expanded the MCP server to 14 tools (`list_layers`, `get_layer_lineage`, `analyze_graph`, `export_layer(format="markdown")`), added CLI commands (`kr layers`, `kr lineage`, `kr analyze`, `kr export --format markdown`), and aligned SemVer `1.3.0` across `pyproject.toml` and `src/knowledgereduce/__init__.py`.

## Verified Quality Gates
- **Meta Gate (`make canary`)**: `7/7` passed (`AGENTS.md` <-> `.agents/AGENTS.md` parity, SemVer `1.3.0` parity, `workflow_dispatch`-only workflows, `lessons_learned.md` relevance & repo path checks, pre-PR hook guard, domain invariants).
- **Lint & Format (`make lint`)**: `ruff check` and `ruff format --check` clean across `73` files.
- **Type Check (`make typecheck`)**: `mypy --strict src` clean across `44` source files.
- **Test Suite (`make local-ci`)**: `112 passed in 32.14s` at `91.69%` coverage (above `85%` floor), including all `3` examples, `3` curated notebooks with zero committed outputs, `golden_50_docs` (`bcubed_f1 = 0.9726`), and `1K` scaling (`3.533s`).
- **Real-World Golden Benchmark (`make golden`)**: *Civic Honors: The Book* (`139,596` chars / `21,765` words) completed in `4.388s` with `core_fact_retention = 1.0`, `retrieval_hit_at_1 = 1.0`, `retrieval_mrr_at_5 = 1.0`, and `18/18` metrics improved vs. `baseline_v1_1_0.json`.
