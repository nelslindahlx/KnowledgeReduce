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

| Metric | Measured Result (`v1.1.0`) | Notes |
|---|---|---|
| **B-Cubed Precision** | **1.0000** | Zero unrelated claims falsely merged |
| **B-Cubed Recall** | **0.9200** | Strong recall across paraphrase & punctuation variants |
| **B-Cubed F1** | **0.9583** | Far exceeds ≥0.85 release SLA |
| **Information Retention** | **1.0000** | 100% of distinct canonical themes retained (vs. 2.2% in legacy `v18`) |
| **Conflict Detection Recall** | **1.0000** | 5 / 5 planted contradictions surfaced with `CONTRADICTS` edges |
| **Conflict Resolution Accuracy** | **1.0000** | 5 / 5 provisional winners matched higher-trust ground truth |
| **Claim-to-Entity Connectivity** | **1.0000** | 100% of reduced claims linked to extracted entities via `MENTIONS` |
| **Entity Extraction F1 (Deterministic Baseline)** | **0.7917** (P=0.6786, R=0.9500) | Zero-download baseline (CamelCase + phrase boundaries); upgrade further via `[nlp]` (`SpacyNLPMapper`) or MCP `submit_mapped_batch` |

### B. Single-Machine Scaling Benchmark (Apple Silicon arm64, Python 3.12)
Includes end-to-end entity resolution, 3-stage claim clustering, `DuckDBParquetStore.save_layer`, cold `HybridGraphRAGRetriever.retrieve` (builds `claim_embeddings.parquet`), and warm cached retrieval (bounded DuckDB subgraph):

| Input Facts | Reduced Claims | Relations | Reduce Time | Parquet Store Time | Cold Query (Build Index) | Warm Query (Cached) | Total Wall Time (Cold) | Peak Traced Memory |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **1,000** | 700 | 700 | 1.331 s | 0.062 s | 0.465 s | 0.221 s | **1.858 s** | 10.85 MiB |
| **10,000** | 7,000 | 7,000 | 10.313 s | 0.564 s | 2.483 s | 1.068 s | **13.361 s** | 85.75 MiB |

Scaling from 1,000 → 10,000 facts (10× input) keeps total cold runtime at **`13.36 s`** (well under the 60 s CI SLA) and drops warm GraphRAG latency to **`1.07 s`** at **`85.75 MiB`** peak traced memory via DuckDB parameterized lexical search, persisted Parquet claim embeddings, and bounded k-hop subgraph loading.

---

### C. Real-World Long-Form Golden Benchmark: *Civic Honors — The Book*

To complement the 50-document synthetic golden evaluation above, KnowledgeReduce freezes the complete real-world prose corpus from `https://www.civichonors.com/p/the-book` (`139,596` characters, `21,765` words, `307` non-empty paragraphs across 14 chapters plus 39 APA references; content SHA-256 `309bf753af49c77b6dc033c05cfd689bb337511cf4f3329c84835cd9b8017d4f`) under `benchmarks/datasets/civichonors_book/`. Evaluating `DeterministicNLPMapper(min_sentence_length=25)` + `KnowledgeReducer` + `DuckDBParquetStore` + `HybridGraphRAGRetriever` against curated ground truth (`gold_annotations.json`) locks an honest `v1.1.0` baseline (`baseline_v1_1_0.json`) for future extraction and retrieval improvements.

Reproduce locally with:

```bash
uv run python benchmarks/civichonors_book_benchmark.py --strict-regression
uv run pytest tests/golden/
uv run python benchmarks/run_benchmark.py --scale 1000 10000
```

#### Locked `v1.1.0` Baseline vs. `v1.2+` Roadmap Targets

| Metric | Locked `v1.1.0` Baseline | `v1.2+` Target | Measurement Scope |
|---|---:|---:|---|
| **Core Entity Name Recall** | **0.9722** (`35/36`) | ≥ 0.99 | 36 curated gold entities (`PERSON`, `ORG`, `GPE`, `CONCEPT`, `DATE`) |
| **Core Entity Typed Recall** | **0.7222** (`26/36`) | ≥ 0.90 | Exact name + canonical `entity_type` match |
| **Core Entity Type Accuracy** | **0.7429** (`26/35`) | ≥ 0.92 | Share of found gold entities assigned expected type |
| **Alias Merge Recall** | **0.8000** (`4/5`) | 1.00 | Honorific variants merged (e.g. `Dr. Nels Lindahl` → `Nels Lindahl`) |
| **Cross-Type Duplicate Names** | **1** (`new york`) | 0 | Canonical names emitted under multiple entity types |
| **Heading Noise False Positives** | **12 / 12** (`1.0000`) | ≤ 2 | Title-case chapter headings emitted as spurious entities |
| **Reference Fact Retention** | **0.9167** (`11/12`) | 1.00 | Core historical & bibliography facts preserved in reduced claims |
| **Claim-to-Entity Connectivity** | **0.0942** (`147` `MENTIONS`, `36` `CO_OCCURS_WITH`) | ≥ 0.45 | Reduced claims connected to ≥1 entity edge (`1,040` claims) |
| **Grounded SPO Triple Rate** | **0.0000** (`0` semantic relations) | ≥ 0.20 | Claims populated with `subject_id`, `predicate`, and object |
| **Isolated Node Ratio** | **0.8198** (`942 / 1149`) | ≤ 0.50 | Isolated claims + entities under `IntegrityValidator` |
| **Mean Claim Quality Score** | **57.05** | ≥ 62.0 | `IntegrityValidator` mean score (`strict=True`, `0` errors) |
| **GraphRAG Hit@1 / Hit@3 / Hit@5** | **0.80 / 0.80 / 0.90** | ≥ 0.90 / 1.00 / 1.00 | 10 curated QA queries (`top_k=5`, `hops=1`) |
| **GraphRAG MRR@5** | **0.8250** | ≥ 0.92 | Mean Reciprocal Rank across 10 curated QA queries |
| **End-to-End Cold Runtime** | **~2.40 s** (`37.87 MiB` peak) | ≤ 5.0 s | Map + Reduce + Validate + Parquet Save + Cold GraphRAG |

#### Six Real-World Failure Modes Surfaced for Future PRs

1. **Middle-initial honorific miss:** `_HONORIFIC_PERSON_RE` only allows optional initials before the first capitalized word (`(?:[A-Z]\.\s+)*[A-Z][a-z]+`), missing mid-name initials between given name and surname such as `"Dr. Charles J. Carlsen"` (`alias_merge_recall = 0.8000`, `missing_core_entities = ["Charles J. Carlsen"]`).
2. **Comma-list `City, State` false `GPE`s:** `_CITY_STATE_RE` matches comma-separated person lists and APA author pairs as locations — mistyping `"Carrie Donham"` and `"Chris Engle"` (`GPE`), plus bibliography pairs like `"Carlsen, Lindahl"` and `"Scott, Foreman"`.
3. **Missing institutional suffixes (`College`, `Journal`, `Hall`):** `_ORG_RE` excludes common suffixes such as `College`, `Journal`, and `Hall`, causing `"Johnson County Community College"` and `"Journal for Civic Commitment"` to fall through as `CONCEPT`, while `"Prentice Hall"` and `"San Francisco"` fall through as `PERSON`.
4. **Title-case fallback heading noise & cross-type duplication:** `_CAP_PHRASE_RE` captures title-case section headings as spurious `PERSON`/`CONCEPT` entities (`12/12` noise canaries hit, e.g., `"Breaking Down"`, `"Strong Leadership"`, `"Thinking About Technology"`) and emits `"New York"` under both `GPE` and `PERSON` (`cross_type_duplicate_count = 1`).
5. **Zero grounded SPO triples in deterministic prose mapping:** `DeterministicNLPMapper` extracts `0` structured `(subject_id, predicate, object)` triples (`grounded_triple_rate = 0.0`, `semantic_relations = 0`), leaving `81.98%` of graph nodes isolated (`942 / 1149`) across 21,765 words of narrative prose.
6. **APA citation period-splitting & short-heading GraphRAG bias:** Period-based sentence splitting fragments `"Carlsen, C. J., Lindahl, N., & Lindahl, S. (2004)."` (`carlsen_lindahl_ref` missed, `11/12` fact retention), and lexical overlap scores favor short repeated program phrases over terse lead facts (`pub_year` query missing `"This book was published in 2006."` in `top_k=5`).
