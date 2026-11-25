# Conflict Resolution & Benchmark Evaluation

## 1. Conflict Resolution Policies (`knowledgereduce.reduce`)

Legacy notebooks (`v17`–`v18`) suffered from a symmetric-deletion bug in `super_aggressive_cleaning` that wiped 98.2% of facts (268 → 6) and dropped conflicting source provenance. KnowledgeReduce `v1.0` solves this at two levels:

1. **Incompatible-Claim Guard (`knowledgereduce.resolve.blocking`):** Claims asserting conflicting functional triples (`subject_id + predicate` with differing objects) or differing numeric/year literals are blocked from merging into duplicate clusters.
2. **Pluggable Conflict Policies (`ConflictStrategy`):**
   - **`preserve_dispute` (Default):** Ranks candidates by `(source_trust, reliability, confidence, timestamp)`, designates a provisional winner, marks participating claims `needs_review=True`, emits directed `CONTRADICTS` edges, and preserves **all candidates and `Evidence`** inside a `ConflictRecord`.
   - **`source_trust_priority`:** Selects the highest-trust/highest-reliability candidate automatically and marks `needs_review=False`.
   - **`weighted_consensus`:** Aggregates `source_trust * confidence * (reliability + 1)` across supporting claims per distinct asserted value.
   - **`latest_timestamp`:** Selects the assertion with the newest `published_at` / `updated_at` timestamp.
3. **Non-Destructive Single & Atomic Batch Adjudication:** `adjudicate_conflict()` and `adjudicate_conflicts()` (using `ConflictResolutionDecision`) produce immutable `CURATED` child layers while preserving `needs_review=True` and `CONTRADICTS` edges on claims that still participate in remaining unresolved conflicts.

---

## 2. Reproducible Benchmark Results

Reproduce locally with:

```bash
uv run python benchmarks/run_benchmark.py --scale 1000 10000
```

### A. 50-Document Frozen Golden Evaluation (`DeterministicNLPMapper` + `KnowledgeReducer`)
Evaluates 50 multi-source CivicHonors + domain documents containing 15 thematic duplicate clusters (45 docs) and 5 planted factual contradictions (5 docs):

| Metric | Measured Result (`v1.1.0`) | Measured Result (`v1.5.0`) | Notes |
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
Includes end-to-end entity resolution, 3-stage claim clustering, `DuckDBParquetStore.save_layer`, cold `HybridGraphRAGRetriever.retrieve` (builds `claim_embeddings.parquet`), and warm cached retrieval (bounded DuckDB subgraph + `ClaimSummary` projection):

| Input Facts | Reduced Claims | Relations | Reduce Time | Parquet Store Time | Cold Query (Build Index) | Warm Query (Cached) | Total Wall Time (Cold) | Peak Traced Memory |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **1,000 (`v1.5.0`)** | 700 | 700 | **0.388 s** | 0.062 s | **0.229 s** | **0.064 s** *(traced)* | **0.679 s** | **9.76 MiB** |
| **10,000 (`v1.5.0`)** | 7,000 | 7,000 | **2.968 s** | 0.604 s | **0.720 s** | **0.109 s** *(traced; `21.4 ms` avg / `13.2 ms` steady untraced)* | **4.292 s** | **52.52 MiB** |
| *(ref `v1.1.0` 10,000)* | *7,000* | *7,000* | *10.313 s* | *0.564 s* | *2.483 s* | *1.068 s* | *13.361 s* | *85.75 MiB* |

Scaling from 1,000 → 10,000 facts (10× input) in `v1.5.0` holds 10K cold wall time at **`4.292 s`** (`13.361 s` in `v1.1.0`), keeps traced warm GraphRAG at **`0.109 s`** (**`21.4 ms` avg / `13.2 ms` steady uninstrumented**), and retains **`52.52 MiB`** peak traced memory via precomputed merge-feature sets, Arrow `FixedSizeListArray` embedding I/O, a persistent DuckDB read session, `(mtime_ns, size)` `ClaimSummary` & graph caches, and `top_k`-only full hydration.

---

### C. Real-World Long-Form Golden Benchmark: *Civic Honors — The Book*

To complement the 50-document synthetic golden evaluation above, KnowledgeReduce freezes the complete real-world prose corpus from `https://www.civichonors.com/p/the-book` (`139,596` characters, `21,765` words, `307` non-empty paragraphs across 14 chapters plus 39 APA references; content SHA-256 `309bf753af49c77b6dc033c05cfd689bb337511cf4f3329c84835cd9b8017d4f`) under `benchmarks/datasets/civichonors_book/`. Evaluating `DeterministicNLPMapper(min_sentence_length=25)` + `KnowledgeReducer` + `DuckDBParquetStore` + `HybridGraphRAGRetriever` against curated ground truth (`gold_annotations.json`) locks historical `v1.1.0`, `v1.3.0`, and `v1.4.0` snapshots (`baseline_v1_1_0.json`, `baseline_v1_3_0.json`, `baseline_v1_4_0.json`) with tightened `DEFAULT_REGRESSION_FLOORS`.

Reproduce locally with:

```bash
uv run python benchmarks/civichonors_book_benchmark.py --strict-regression
uv run python benchmarks/multisource_stack_benchmark.py --strict-regression
uv run pytest tests/golden/
uv run python benchmarks/run_benchmark.py --scale 1000 10000
```

#### Locked `v1.1.0` Baseline vs. Measured `v1.5.0` Results (`18 / 18` Metrics Improved)

| Metric | Locked `v1.1.0` Baseline | `v1.4.0` Snapshot | `v1.5.0` Floor / Target | Measured `v1.5.0` Result | Measurement Scope |
|---|---:|---:|---:|---:|---|
| **Core Entity Name Recall** | 0.9722 (`35/36`) | 1.0000 | ≥ 0.99 | **1.0000** (`36/36`) | 36 curated gold entities (`PERSON`, `ORG`, `GPE`, `CONCEPT`, `DATE`) |
| **Core Entity Typed Recall** | 0.7222 (`26/36`) | 1.0000 | ≥ 0.98 | **1.0000** (`36/36`) | Exact name + canonical `entity_type` match |
| **Core Entity Type Accuracy** | 0.7429 (`26/35`) | 1.0000 | ≥ 0.98 | **1.0000** (`36/36`) | Share of found gold entities assigned expected type |
| **Alias Merge Recall** | 0.8000 (`4/5`) | 1.0000 | ≥ 0.98 | **1.0000** (`5/5`) | Honorific variants merged (e.g. `Dr. Nels Lindahl` → `Nels Lindahl`) |
| **Cross-Type Duplicate Names** | 1 (`new york`) | 0 | 0 | **0** | Canonical names emitted under multiple entity types |
| **Heading Noise False Positives** | 12 / 12 (`1.0000`) | 0 / 12 | 0 | **0 / 12** (`0.0000`) | Title-case chapter headings emitted as spurious entities |
| **Reference Fact Retention** | 0.9167 (`11/12`) | 1.0000 | ≥ 0.99 | **1.0000** (`12/12`) | Core historical & bibliography facts preserved in reduced claims |
| **Claim-to-Entity Connectivity** | 0.0942 (`147` `MENTIONS`) | 0.5131 (`962`) | ≥ 0.50 | **0.5204** (`942` `MENTIONS`, `65` `CO_OCCURS_WITH`) | Reduced claims connected to ≥1 entity edge (`982` hygiene-filtered claims) |
| **Grounded SPO Triple Rate** | 0.0000 (`0`) | 0.2614 (`43`) | ≥ 0.26 | **0.2821** (`44` semantic relations) | Claims populated with `subject_id`, `predicate`, and object |
| **Isolated Node Ratio** | 0.8198 (`942 / 1149`) | 0.4473 (`501`) | ≤ 0.45 | **0.4390** (`471` isolated; `91` entities + `982` claims) | Isolated claims + entities under `IntegrityValidator` |
| **Mean Claim Quality Score** | 57.05 | 57.97 | ≥ 59.0 | **59.42** | Structural grounding bonus + reliability/confidence/evidence (`0` errors, `0` warnings) |
| **GraphRAG Hit@1 / Hit@3 / Hit@5** | 0.80 / 0.80 / 0.90 | 1.00 / 1.00 / 1.00 | ≥ 0.98 | **1.00 / 1.00 / 1.00** | 10 curated QA queries (`top_k=5`, `hops=1`) — all 10 at rank 1 |
| **GraphRAG MRR@5** | 0.8250 | 1.0000 | ≥ 0.98 | **1.0000** | Mean Reciprocal Rank across 10 curated QA queries |
| **End-to-End Cold Runtime** | ~2.40 s (`37.87 MiB` peak) | 1.693 s (`173 ms` warm) | ≤ 8.0 s *(in cov CI)* | **1.447 s** (`0.638 s` reduce, `0.098 s`–`0.100 s` traced warm; **`10.7 ms` steady untraced**) | Map + Reduce + Validate + Parquet Save + Cold & Warm GraphRAG |

#### Historical Baseline Failure Modes Resolved Through `v1.5.0`

1. **Middle-initial honorific miss (`[RESOLVED]`):** Expanded `_HONORIFIC_PERSON_RE` handles mid-name initials such as `"Dr. Charles J. Carlsen"` (`alias_merge_recall = 1.0000`).
2. **Comma-list `City, State` false `GPE`s (`[RESOLVED]`):** `_CITY_STATE_RE` and bibliographic surname guards eliminate person/bibliography mistyping as locations (`core_entity_type_accuracy = 1.0000`).
3. **Missing institutional suffixes (`College`, `Journal`, `Hall`) & publisher/institute patterns (`[RESOLVED]`):** `_ORG_RE` and `_CAMEL_ENTITY_RE` recognize `College`, `Journal`, `Hall`, `McGraw-Hill`, `Fortune Magazine`, and `Institute of Public Administration` (`core_entity_typed_recall = 1.0000`).
4. **Title-case fallback heading noise, heading/question claims & cross-type duplication (`[RESOLVED in v1.2–v1.5]`):** Heading suppression captures sections into `contextual_notes = "Section: ..."` (`977/982` Book claims) while eliminating heading (`37` → `0`) and question (`10` → `0`) claim noise, `heading_noise_fp_count = 0/12`, and `cross_type_duplicate_count = 0`.
5. **Grounded SPO triples, structural quality score & claim connectivity (`[RESOLVED in v1.2–v1.5]`):** `_FACTUAL_PATTERNS`, expanded narrative predicates (`_ANCHORED_AUX_RE`/`_ANCHORED_VERB_MAP`), dominant non-Press `"the university"` coref, and structural grounding bonus in `Claim.quality_score` lift `grounded_triple_rate` to **`0.2821`**, `claim_connectivity_rate` to **`0.5204`**, `mean_quality_score` to **`59.42`**, and cut `isolated_node_ratio` to **`0.4390`**.
6. **APA citation period-splitting & GraphRAG latency (`[RESOLVED in v1.3–v1.5]`):** Abbreviation/initial-aware sentence segmentation preserves `"Carlsen, C. J., Lindahl, N., & Lindahl, S. (2004)."` (`core_fact_retention = 1.0000`), and persistent DuckDB read sessions + `ClaimSummary`/graph caches achieve **`1.0000` Hit@1 / MRR@5** at **`10.7 ms` steady uninstrumented warm latency**.

---

### D. Offline Multi-Source Incremental & Stacked Golden Benchmark (`benchmarks/multisource_stack_benchmark.py`)

Complements single-corpus benchmarks with an end-to-end deterministic workflow combining local `.html` (`HTMLConnector`) and `.md` (`MarkdownConnector`) ingestion, `incremental_from_layer` SHA-256 skip-unchanged deltas (`skipped_unchanged = 1`), `StackManager.merge_layers(..., mode=MergeMode.UNION, conflict_strategy=ConflictStrategy.PRESERVE_DISPUTE, reconcile=True)` over a disputed low-trust overlay, pre-warmed `claim_embeddings.parquet` indices, warm GraphRAG retrieval + conflict surfacing, graph analytics, and GFM Markdown brief export:

| Metric | Measured Result (`v1.5.0`) | Strict Floor / Ceiling |
|---|---:|---:|
| **Incremental Unchanged Skipped (`skipped_unchanged`)** | **1** (`delta` parents `["ms-base"]`) | ≥ 1 |
| **Conflict Detection Recall / Resolution Accuracy** | **1.0000 / 1.0000** (`3 / 3` conflicts, `3` `CONTRADICTS` edges) | 1.0000 / 1.0000 |
| **GraphRAG Hit@1 & Disputed Conflict Surfacing** | **1.0000 / 1.0000** (`top_k = 3`, `hops = 1`) | 1.0000 / 1.0000 |
| **Strict Integrity Errors / Warnings / Isolated Entities** | **0 / 0 / 0** (`mean_quality_score = 69.5`) | 0 / 0 / 0 (`≥ 65.0`) |
| **End-to-End Runtime** | **0.176 s** | ≤ 5.0 s |

---

### E. `v1.6.0` Verified Measurements (SQL Pushdown, Scaling & Strict Golden Gates)

- **50,000-Claim `QueryBuilder` SQL Pushdown Top-10 (`DuckDBParquetStore.list_claims`)**: **`6.82 ms` median** (`6.42`–`8.62 ms` uninstrumented across tag, reliability, confidence sort, and `LIMIT 10` — down from `1,004.6 ms` pre-pushdown).
- **1K / 10K Scaling (`benchmarks/run_benchmark.py --scale 1000 10000`)**: `1,000` facts in **`0.689 s`** total (`0.067 s` warm, `9.76 MiB` peak); `10,000` facts in **`4.202 s`** total (`0.110 s` traced warm, `52.49 MiB` peak).
- **Strict Golden Suites**: *Civic Honors — The Book* **`1.486 s`** (`18 / 18` metrics improved vs `v1.1.0`, `1.00` Hit@1 & MRR@5, `59.42` mean quality); Multi-Source Stacked/Incremental **`0.188 s`** (`1.00` Hit@1 & conflict recall, `0` integrity errors/warnings).
