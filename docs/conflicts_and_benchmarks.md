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

| Metric | Measured Result (`v1.1.0`) | Measured Result (`v1.4.0`) | Notes |
|---|---:|---:|---|
| **B-Cubed Precision** | 1.0000 | **1.0000** | Zero unrelated claims falsely merged |
| **B-Cubed Recall** | 0.9200 | **1.0000** | Modal/passive canonical predicate matching catches remaining paraphrase variants |
| **B-Cubed F1** | 0.9583 | **1.0000** | Far exceeds ≥0.85 release SLA |
| **Information Retention** | 1.0000 | **1.0000** | 100% of distinct canonical themes retained (vs. 2.2% in legacy `v18`) |
| **Conflict Detection Recall** | 1.0000 | **1.0000** | 5 / 5 planted contradictions surfaced with `CONTRADICTS` edges |
| **Conflict Resolution Accuracy** | 1.0000 | **1.0000** | 5 / 5 provisional winners matched higher-trust ground truth |
| **Claim-to-Entity Connectivity** | 1.0000 | **1.0000** | 100% of reduced claims linked to extracted entities via `MENTIONS` |
| **Entity Extraction F1 (Deterministic Baseline)** | 0.7917 (`P=0.6786, R=0.9500`) | **0.7451** (`P=0.6129, R=0.9500`) | Zero-download baseline (`R=0.95`); broader org/publisher extraction tuned for narrative prose; upgrade via `[nlp]` (`SpacyNLPMapper`) or MCP `submit_mapped_batch` |

### B. Single-Machine Scaling Benchmark (Apple Silicon arm64, Python 3.12)
Includes end-to-end entity resolution, 3-stage claim clustering, `DuckDBParquetStore.save_layer`, cold `HybridGraphRAGRetriever.retrieve` (builds `claim_embeddings.parquet`), and warm cached retrieval (bounded DuckDB subgraph):

| Input Facts | Reduced Claims | Relations | Reduce Time | Parquet Store Time | Cold Query (Build Index) | Warm Query (Cached) | Total Wall Time (Cold) | Peak Traced Memory |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **1,000 (`v1.4.0`)** | 700 | 700 | **0.392 s** | 0.061 s | **0.279 s** | **0.130 s** | **0.731 s** | **9.76 MiB** |
| **10,000 (`v1.4.0`)** | 7,000 | 7,000 | **2.943 s** | 0.610 s | **0.602 s** | **0.180 s** | **4.155 s** | **52.49 MiB** |
| *(ref `v1.1.0` 10,000)* | *7,000* | *7,000* | *10.313 s* | *0.564 s* | *2.483 s* | *1.068 s* | *13.361 s* | *85.75 MiB* |

Scaling from 1,000 → 10,000 facts (10× input) in `v1.4.0` cuts 10K cold wall time from **`13.361 s`** → **`4.155 s`** (reduce **`10.313 s` → `2.943 s`**, warm GraphRAG **`1.068 s` → `0.180 s`**, peak traced memory **`85.75 MiB` → `52.49 MiB`**) via precomputed merge-feature sets in `cluster_claims()`, Arrow `FixedSizeListArray` zero-copy embedding I/O, and read-only session caching.

---

### C. Real-World Long-Form Golden Benchmark: *Civic Honors — The Book*

To complement the 50-document synthetic golden evaluation above, KnowledgeReduce freezes the complete real-world prose corpus from `https://www.civichonors.com/p/the-book` (`139,596` characters, `21,765` words, `307` non-empty paragraphs across 14 chapters plus 39 APA references; content SHA-256 `309bf753af49c77b6dc033c05cfd689bb337511cf4f3329c84835cd9b8017d4f`) under `benchmarks/datasets/civichonors_book/`. Evaluating `DeterministicNLPMapper(min_sentence_length=25)` + `KnowledgeReducer` + `DuckDBParquetStore` + `HybridGraphRAGRetriever` against curated ground truth (`gold_annotations.json`) locks both the historical `v1.1.0` baseline (`baseline_v1_1_0.json`) and the post-SPA `v1.3.0` snapshot (`baseline_v1_3_0.json`) with tightened `DEFAULT_REGRESSION_FLOORS`.

Reproduce locally with:

```bash
uv run python benchmarks/civichonors_book_benchmark.py --strict-regression
uv run pytest tests/golden/
uv run python benchmarks/run_benchmark.py --scale 1000 10000
```

#### Locked `v1.1.0` Baseline vs. Measured `v1.4.0` Results (`18 / 18` Metrics Improved)

| Metric | Locked `v1.1.0` Baseline | `v1.4.0` Floor / Target | Measured `v1.4.0` Result | Measurement Scope |
|---|---:|---:|---:|---|
| **Core Entity Name Recall** | 0.9722 (`35/36`) | ≥ 0.99 | **1.0000** (`36/36`) | 36 curated gold entities (`PERSON`, `ORG`, `GPE`, `CONCEPT`, `DATE`) |
| **Core Entity Typed Recall** | 0.7222 (`26/36`) | ≥ 0.90 | **1.0000** (`36/36`) | Exact name + canonical `entity_type` match |
| **Core Entity Type Accuracy** | 0.7429 (`26/35`) | ≥ 0.92 | **1.0000** (`36/36`) | Share of found gold entities assigned expected type |
| **Alias Merge Recall** | 0.8000 (`4/5`) | 1.00 | **1.0000** (`5/5`) | Honorific variants merged (e.g. `Dr. Nels Lindahl` → `Nels Lindahl`) |
| **Cross-Type Duplicate Names** | 1 (`new york`) | 0 | **0** | Canonical names emitted under multiple entity types |
| **Heading Noise False Positives** | 12 / 12 (`1.0000`) | 0 | **0 / 12** (`0.0000`) | Title-case chapter headings emitted as spurious entities |
| **Reference Fact Retention** | 0.9167 (`11/12`) | 1.00 | **1.0000** (`12/12`) | Core historical & bibliography facts preserved in reduced claims |
| **Claim-to-Entity Connectivity** | 0.0942 (`147` `MENTIONS`, `36` `CO_OCCURS_WITH`) | ≥ 0.50 | **0.5131** (`962` `MENTIONS`, `66` `CO_OCCURS_WITH`) | Reduced claims connected to ≥1 entity edge (`1,029` claims) |
| **Grounded SPO Triple Rate** | 0.0000 (`0` semantic relations) | ≥ 0.25 | **0.2614** (`43` semantic relations) | Claims populated with `subject_id`, `predicate`, and object |
| **Isolated Node Ratio** | 0.8198 (`942 / 1149`) | ≤ 0.46 | **0.4473** (`501` isolated; `91` entities + `1,029` claims) | Isolated claims + entities under `IntegrityValidator` |
| **Mean Claim Quality Score** | 57.05 | ≥ 57.5 | **57.97** | `IntegrityValidator` mean score (`strict=True`, `0` errors, `0` warnings) |
| **GraphRAG Hit@1 / Hit@3 / Hit@5** | 0.80 / 0.80 / 0.90 | ≥ 0.90 / 1.00 / 1.00 | **1.00 / 1.00 / 1.00** | 10 curated QA queries (`top_k=5`, `hops=1`) — all 10 at rank 1 |
| **GraphRAG MRR@5** | 0.8250 | ≥ 0.95 | **1.0000** | Mean Reciprocal Rank across 10 curated QA queries |
| **End-to-End Cold Runtime** | ~2.40 s (`37.87 MiB` peak) | ≤ 5.0 s | **1.397 s** (`0.627 s` reduce, `39.39 MiB` peak) | Map + Reduce + Validate + Parquet Save + Cold GraphRAG |

#### Historical Baseline Failure Modes Resolved Through `v1.4.0`

1. **Middle-initial honorific miss (`[RESOLVED]`):** Expanded `_HONORIFIC_PERSON_RE` handles mid-name initials such as `"Dr. Charles J. Carlsen"` (`alias_merge_recall = 1.0000`).
2. **Comma-list `City, State` false `GPE`s (`[RESOLVED]`):** `_CITY_STATE_RE` and bibliographic surname guards eliminate person/bibliography mistyping as locations (`core_entity_type_accuracy = 1.0000`).
3. **Missing institutional suffixes (`College`, `Journal`, `Hall`) & publisher/institute patterns (`[RESOLVED]`):** `_ORG_RE` and `_CAMEL_ENTITY_RE` recognize `College`, `Journal`, `Hall`, `McGraw-Hill`, `Fortune Magazine`, and `Institute of Public Administration` (`core_entity_typed_recall = 1.0000`).
4. **Title-case fallback heading noise & cross-type duplication (`[RESOLVED]`):** Title-case heading suppression and canonical cross-type resolution drop heading noise from `12/12` → `0/12` and `cross_type_duplicate_count` from `1` → `0`.
5. **Grounded SPO triples & claim connectivity (`[RESOLVED in v1.2–v1.4]`):** `_FACTUAL_PATTERNS` stop boundaries, appositive extraction (`{2,70}`), modal/passive `_ANCHORED_AUX_RE`/`_ANCHORED_VERB_MAP`, and dominant non-Press `"the university"` coref lift `grounded_triple_rate` from `0.0000` → **`0.2614`** (`43` semantic relations), `claim_connectivity_rate` from `0.0942` → **`0.5131`**, and cut `isolated_node_ratio` from `0.8198` → **`0.4473`**.
6. **APA citation period-splitting & short-heading GraphRAG bias (`[RESOLVED]`):** Abbreviation/initial-aware sentence segmentation preserves `"Carlsen, C. J., Lindahl, N., & Lindahl, S. (2004)."` (`core_fact_retention = 1.0000`) and hybrid retrieval achieves **`1.0000` Hit@1 / MRR@5**.
