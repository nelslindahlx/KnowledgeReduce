# Changelog

All notable changes to KnowledgeReduce are documented in this file.

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
