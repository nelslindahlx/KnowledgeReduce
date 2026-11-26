# KnowledgeReduce

**MapReduce-inspired, conflict-aware framework for building stackable knowledge graphs — persisted in DuckDB + Apache Parquet, queried with NetworkX + Hybrid GraphRAG, and operable directly by AI agents over `stdio` MCP.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## Why KnowledgeReduce?

KnowledgeReduce unifies the conceptual architecture from [*KnowledgeReduce: Building Stackable Sets of Knowledge*](docs/paper/paper.tex) with a deterministic, provenance-rich fact and entity-relationship pipeline:

1. **Ingest (`knowledgereduce.ingest`):** SSRF-hardened async web crawler (`httpx`, private-IP blocking, `http`/`https`-only, cached `robots.txt` with timeouts, per-domain rate limiting, lazy warning-free `trafilatura` main-content extraction, `content_sha256` change tracking) plus offline local `CSV`, `JSON`/`JSONL`, `Markdown` (frontmatter `published_at`/`date` and normalized `tags` propagated to extracted claims), `HTML` (`HTMLConnector`), optional `PDF` (`PDFConnector` via `[pdf]`), symlink-safe `DirectoryConnector` / `ingest_local_directory()` glob discovery, and SHA-256 incremental delta ingestion (`incremental_from_layer`).
2. **Map (`knowledgereduce.map`):** Stateless, parallelizable document mappers (`DeterministicNLPMapper`, schema-inferred `StructuredMapper` with per-row typing & sparse JSON support, optional batched `SpacyNLPMapper`) plus resumable `02_mapped.jsonl` checkpoints and an agent-in-the-loop MCP hook (`submit_mapped_batch`). Every `Claim` connects to its extracted `Entity` nodes via `MENTIONS` and semantic `Relation` edges.
3. **Resolve (`knowledgereduce.resolve`):** Sub-quadratic 3-tier deduplication (SHA-256 exact hash → token-blocked `rapidfuzz` → batched L2-normalized embeddings + `AgglomerativeClustering(metric="precomputed")`) with precomputed `O(N)` claim merge features, Union-Find entity disambiguation, and atomic `entity_id_map` endpoint remapping.
4. **Reduce (`knowledgereduce.reduce`):** Representative-preserving cluster merging (never destructive deletion), structural grounding-weighted `quality_score`, full provenance/alias/tag union, **`PreserveDispute`** default conflict handling (`CONTRADICTS` edges + structured `ConflictRecord`s with `needs_review=True`, including single-year temporal conflict detection), single (`adjudicate_conflict`) and atomic batch (`adjudicate_conflicts`) adjudication, and a strict `IntegrityValidator` gate guaranteeing zero dangling edges.
5. **Store, Stack & Serve (`storage`, `stack`, `query`, `export`, `mcp`):** Immutable columnar Parquet layers with crash-safe backup-swap `save_layer` writes, metadata-only `get_layer_manifest()`/`list_source_hashes()` reads, parameterized DuckDB SQL filter/sort/limit pushdown (`list_claims()` & `QueryBuilder`), pre-warmed `FixedSizeListArray` `claim_embeddings.parquet` vector index, `(mtime_ns, size)` summary/graph caches, and thread-safe persistent DuckDB read session for sub-15 ms warm GraphRAG), non-destructive `StackManager` set/overlay algebra (`overlay`, `union`, `intersection`, `difference`, optional `reconcile=True` with cross-layer entity & claim deduplication, `diff_layers`) in a lineage DAG, Hybrid GraphRAG retrieval (`HashingEmbeddingProvider` default), Markdown Knowledge Brief + lossless sharded JSONL + sanitized GraphML/GEXF exports, Typer CLI (`kr`), and a 17-tool (plus 3 Resources, 2 Prompts) Antigravity-ready `stdio` MCP server.

---

## Installation

Requires **Python 3.11+** and [`uv`](https://docs.astral.sh/uv/) (recommended) or `pip`:

```bash
# Editable development install with all test/lint tools
uv sync --extra dev

# Or install directly from GitHub
pip install "git+https://github.com/nelslindahlx/KnowledgeReduce.git"

# Optional extras
uv sync --extra nlp         # spaCy batched dependency extraction
uv sync --extra embeddings  # sentence-transformers embeddings
uv sync --extra viz         # matplotlib helpers
uv sync --extra pdf         # pypdf PDF text extraction
```

Verify the installation:

```bash
uv run kr version
# knowledgereduce 1.6.1
```

---

## Python SDK Quickstart

```python
from pathlib import Path
from knowledgereduce import (
    ConflictStrategy,
    DuckDBParquetStore,
    HybridGraphRAGRetriever,
    LocalFileSourceConfig,
    PipelineConfig,
    PipelineRunner,
    StackManager,
    MergeMode,
)

config = PipelineConfig(
    layer_id="civichonors-v1",
    layer_name="Civic Honors Knowledge Base",
    store_dir=".kr_store",
    checkpoint_dir=".kr_checkpoints",
    local_files=[
        LocalFileSourceConfig(
            path="tests/fixtures/civichonors_facts.csv",
            source_id="csv_curated",
            trust_weight=0.95,
        ),
        LocalFileSourceConfig(
            path="tests/fixtures/civichonors_notes.json",
            source_id="json_notes",
            trust_weight=0.90,
        ),
    ],
    conflict_strategy=ConflictStrategy.PRESERVE_DISPUTE,
)

layer_data = PipelineRunner().run(config)
print(layer_data.layer.stats)

# Query with Hybrid GraphRAG (lexical + embedding similarity + k-hop graph expansion)
store = DuckDBParquetStore(Path(".kr_store"))
ctx = HybridGraphRAGRetriever(store).retrieve(
    "civichonors-v1",
    "When was Civic Honors published?",
    top_k=3,
    hops=1,
)
for item in ctx.results:
    print(item.score, item.claim.statement, item.graph_neighbors)
```

---

## CLI (`kr`) Overview

```bash
kr version
kr doctor -s .kr_store
kr run pipeline.yaml
kr ingest --file facts.csv --dir notes/ --glob "*.md" -o checkpoints/01_ingested.jsonl --incremental-from civic-v1 -s .kr_store
kr map -i checkpoints/01_ingested.jsonl -o checkpoints/02_mapped.jsonl --workers 4
kr reduce --layer-id civic-v2 --name "Civic v2" --parent-layer civic-v1 -i checkpoints/02_mapped.jsonl -s .kr_store
kr stack --layer civic-v1 --layer civic-patch --target civic-stacked --mode overlay --reconcile -s .kr_store
kr index civic-stacked -s .kr_store
kr layers -s .kr_store
kr lineage civic-stacked -s .kr_store
kr inspect civic-stacked "Civic Honors" --json-output -s .kr_store
kr analyze civic-stacked --metric pagerank --top-k 10 -s .kr_store
kr diff civic-v1 civic-stacked -s .kr_store
kr conflicts civic-stacked -s .kr_store
kr resolve-conflict civic-stacked --conflict-id <cf_id> --target civic-curated --winning-value "2006" -s .kr_store
kr resolve-conflicts civic-stacked --decisions resolutions.json --target civic-curated-batch -s .kr_store
kr query civic-curated --query "University of Kansas" --top-k 5 --hops 1 -s .kr_store
kr export civic-curated --format markdown -o exports/civic_brief.md -s .kr_store
kr export civic-curated --format sharded_jsonl -o exports/civic_shards -s .kr_store
kr validate civic-curated --strict -s .kr_store
kr mcp --workspace .
```

---

## Antigravity `stdio` MCP Integration

Start `kr mcp --workspace /path/to/workspace` or register it in Antigravity's `mcp_config.json` (see [docs/mcp_antigravity.md](docs/mcp_antigravity.md) for the complete config and agent-in-the-loop `submit_mapped_batch` workflow). Exposed tools (`17`), resources (`3`), and prompts (`2`):

- `ingest_source` • `read_ingested_checkpoint` • `run_local_map` • `submit_mapped_batch` • `resolve_and_reduce`
- `stack_layers` • `diff_layers` • `query_knowledge_graph` • `analyze_graph` • `inspect_entity`
- `list_layers` • `get_layer_lineage` • `list_conflicts` • `resolve_conflict` • `resolve_conflicts`
- `export_layer` • `validate_layer`
- Resources: `kr://layers`, `kr://layers/{layer_id}/manifest`, `kr://layers/{layer_id}/conflicts`
- Prompts: `extract_mapped_batch`, `adjudicate_conflicts`

---

## Documentation & Project Layout

- `src/knowledgereduce/` — Core production package (`models`, `ingest`, `map`, `resolve`, `reduce`, `storage`, `stack`, `query`, `export`, `pipeline`, `mcp`, `cli`).
- `docs/architecture.md` — Dataflow, Pydantic schemas, Parquet manifest spec, and locked ADRs.
- `docs/mcp_antigravity.md` — Antigravity `stdio` MCP server configuration and 17-tool workflow.
- `docs/conflicts_and_benchmarks.md` — Conflict resolution policies and golden/scaling benchmark results.
- `docs/paper/` — Original preprint paper (*KnowledgeReduce: Building Stackable Sets of Knowledge*, LaTeX + PDF).
- `examples/` — Offline runnable Python scripts demonstrating pipeline, stacking, conflicts, GraphRAG, and exports.
- `notebooks/` — Clean, output-stripped notebooks importing `knowledgereduce`.
- `benchmarks/` — Reproducible 50-document golden evaluation, *Civic Honors: The Book* regression gate, and 1K/10K scaling harness.
- `legacy/` — Deprecated historical Colab notebooks and 2023–2025 experimental prototypes (excluded from builds and CI; preserved under tag `archive/experiments-2023-2025`).

## Development & Quality Checks

All changes to `main` follow the zero-GitHub-Actions-minutes **Maker / Checker Pull Request** workflow documented in [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md). Direct commits to `main` are disallowed; open a feature branch PR passing `make local-ci`, `make golden`, independent Checker review, and `make audit-prs`.

```bash
make canary      # <10s: import warning gate + tests/meta/ invariants & doc parity
make smoke-pr    # canary + ruff + mypy + unit & golden tests
make local-ci    # complete local CI gate (canary + lint + mypy + >=95% cov + examples + notebooks + 1K benchmark)
make golden      # Civic Honors book + offline multi-source stack strict regression benchmarks
make benchmark   # 50-doc golden eval + 1K scaling harness
uv run --no-sync python benchmarks/run_benchmark.py --scale 1000 10000
```
