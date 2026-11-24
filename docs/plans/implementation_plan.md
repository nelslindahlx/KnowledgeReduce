# Active Implementation Plan — KnowledgeReduce v1.3.0

- [x] Governance & Zero-GitHub-Minutes Local CI PR (`#27`): `workflow_dispatch` workflows, `Makefile`, `AGENTS.md` / `.agents/` parity, `scripts/github_pr_helper.py`, `scripts/hooks/pre_pr_safety_gate.py`, `tests/meta/test_governance_and_invariants.py`, `lessons_learned.md`, `docs/plans/`, `CHANGELOG.md`, and `main` branch protection update.
- [x] Phase 1 PR (`#23`): Non-functional predicate blocking, asymmetric year/APA citation preservation, atomic triple + provenance inheritance, structural heading retrieval de-biasing (`core_fact_retention = 1.0000`, `retrieval_hit_at_1 = 1.0000`).
- [x] Phase 2 PR (`#24`): `PipelineConfig.incremental_from_layer` SHA-256 delta ingestion and `PipelineConfig.build_embeddings_index` pre-warmed GraphRAG index persistence.
- [ ] Phase 3 PR (`#25`): `export_layer_markdown` / `render_layer_markdown`, MCP `list_layers` / `get_layer_lineage` / `analyze_graph` (14 tools), CLI `layers` / `lineage` / `analyze` / `--format markdown`, and `1.3.0` SemVer manifest bump.
- [ ] Final Verification & Release (`v1.3.0`): `make local-ci`, `make golden`, 10K SLA benchmark (`< 60s`), `scripts/github_pr_helper.py --audit`, annotated tag `v1.3.0`, and close `#26`.
