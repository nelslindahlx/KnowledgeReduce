# Conflict Resolution & Benchmark Evaluation

## 1. Conflict Resolution Policies (`knowledgereduce.reduce`)

Legacy notebooks (`v17`–`v18`) suffered from a symmetric-deletion bug in `super_aggressive_cleaning` that wiped 98.2% of facts (268 → 6) and dropped conflicting source provenance. KnowledgeReduce `v1.0` solves this at two levels:

1. **Incompatible-Claim Guard (`knowledgereduce.resolve.blocking`):** Claims asserting conflicting functional triples (`subject_id + predicate` with differing objects) or differing numeric/year literals are blocked from merging into duplicate clusters.
2. **Pluggable Conflict Policies (`ConflictStrategy`):**
   - **`preserve_dispute` (Default):** Ranks candidates by `(source_trust, reliability, confidence, timestamp)`, designates a provisional winner, marks participating claims `needs_review=True`, emits directed `CONTRADICTS` edges, and preserves **all candidates and `Evidence`** inside a `ConflictRecord`.
   - **`source_trust_priority`:** Selects the highest-trust/highest-reliability candidate automatically and marks `needs_review=False`.
   - **`weighted_consensus`:** Aggregates `source_trust * confidence * (reliability + 1)` across supporting claims per distinct asserted value.
   - **`latest_timestamp`:** Selects the assertion with the newest `published_at` / `updated_at` timestamp.

---

## 2. Reproducible Benchmark Results

Reproduce locally with:

```bash
uv run python benchmarks/run_benchmark.py --scale 1000 10000
```

### A. 50-Document Frozen Golden Evaluation (`DeterministicNLPMapper` + `KnowledgeReducer`)
Evaluates 50 multi-source CivicHonors + domain documents containing 15 thematic duplicate clusters (45 docs) and 5 planted factual contradictions (5 docs):

| Metric | Measured Result | Notes |
|---|---|---|
| **B-Cubed Precision** | **1.0000** | Zero unrelated claims falsely merged |
| **B-Cubed Recall** | **0.9200** | Strong recall across paraphrase & punctuation variants |
| **B-Cubed F1** | **0.9583** | Far exceeds ≥0.85 release SLA |
| **Information Retention** | **1.0000** | 100% of distinct canonical themes retained (vs. 2.2% in legacy `v18`) |
| **Conflict Detection Recall** | **1.0000** | 5 / 5 planted contradictions surfaced with `CONTRADICTS` edges |
| **Conflict Resolution Accuracy** | **1.0000** | 5 / 5 provisional winners matched higher-trust ground truth |
| **Claim-to-Entity Connectivity** | **0.7826** | Fraction of reduced claims linked to extracted entities via `MENTIONS` |
| **Entity Extraction F1 (Deterministic Baseline)** | **0.5581** (P=0.5217, R=0.6000) | Zero-download baseline; upgrade via `[nlp]` (`SpacyNLPMapper`) or MCP `submit_mapped_batch` |

### B. Single-Machine Scaling Benchmark (Apple Silicon arm64, Python 3.12)
Includes end-to-end entity resolution, 3-stage claim clustering, `DuckDBParquetStore.save_layer`, and `HybridGraphRAGRetriever.retrieve`:

| Input Facts | Reduced Claims | Relations | Reduce Time | Parquet Store Time | GraphRAG Query Time | Total Wall Time | Peak Traced Memory |
|---:|---:|---:|---:|---:|---:|---:|---:|
| **1,000** | 700 | 700 | 1.667 s | 0.067 s | 0.415 s | **2.148 s** | 15.55 MiB |
| **10,000** | 7,000 | 7,000 | 11.108 s | 0.572 s | 2.274 s | **13.954 s** | 136.15 MiB |

Scaling from 1,000 → 10,000 facts (10× input) increases total runtime by **6.5×** (`13.95 s`, well under the 60 s CI SLA), confirming sub-quadratic behavior via prefix/token blocking and coarse `MiniBatchKMeans` partitioning prior to `AgglomerativeClustering(metric="precomputed")`.
