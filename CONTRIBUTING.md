# Contributing to KnowledgeReduce

KnowledgeReduce enforces a **Maker / Checker Pull Request** process on `main` for both human contributors and AI agents. Direct pushes to `main` are disallowed; all changes flow through feature branches, automated CI gates, and explicit review.

---

## 1. Branch & Environment Setup

```bash
git checkout main
git pull origin main
git checkout -b <type>/<short-description>   # e.g. feat/fts-index, fix/crawl-timeout, chore/docs
uv sync --extra dev
```

Always confirm your branch is **not** `main` before committing.

---

## 2. Maker Responsibilities (Author)

Implement your change alongside focused unit/integration tests and run the local verification suite:

```bash
uv run python -W error::Warning -c "import knowledgereduce"
uv run ruff check src tests examples benchmarks
uv run ruff format --check src tests examples benchmarks
uv run mypy --strict src
uv run pytest --cov=knowledgereduce --cov-report=term-missing --cov-fail-under=85
```

When touching extraction, storage, GraphRAG retrieval, stacking, examples, or notebooks, also verify:

```bash
uv run pip-audit
for s in examples/*.py; do uv run python "$s"; done
uv run python benchmarks/run_benchmark.py --scale 1000
```

Push your branch and open a Pull Request against `main` using `.github/pull_request_template.md`, filling in **Summary**, **Linked Issue**, and **Maker Checklist** honestly from observed command outputs.

---

## 3. Automated CI Checks

Every Pull Request targeting `main` must pass all three required status checks cleanly:

1. **`quality-and-tests (3.11)`** — `ruff check`, `ruff format --check`, `mypy --strict src`, and `pytest --cov-fail-under=85` on Python 3.11.
2. **`quality-and-tests (3.12)`** — Full Python 3.12 matrix including offline `examples/*.py`, stripped `notebooks/*.ipynb` execution, and `benchmarks/run_benchmark.py --scale 1000`.
3. **`maker-checker-gate`** — Verifies non-`main` PR source branch, completed `## Maker` & `## Checker` sections in the PR description, zero tracked `*.pyc` files, and zero committed notebook outputs.

---

## 4. Checker Responsibilities (Independent Reviewer)

Every PR requires an independent **Checker** audit before merge:

1. **Diff & Correctness Audit:** Review the complete diff for boundary conditions, type safety, exception propagation, and single-purpose modular structure.
2. **Security Review:** Verify URL SSRF validation (`validate_url_safe`), workspace/export path sandboxing (`ensure_within_base`), parameterized DuckDB SQL (`read_parquet(?)`, `UNNEST`), and GitHub Actions workflow `env:` variable binding (no shell injection).
3. **Test & CI Verification:** Confirm regression and negative tests cover the changed behavior and all required checks pass on the head commit.
4. **Structured Review & Sign-Off:** Record findings in the PR `## Checker Review` comment/section, resolve all review threads, obtain CODEOWNER approval (`@nelslindahlx` per `.github/CODEOWNERS`), and merge cleanly into `main`.

> **Solo-Maintainer Note:** While `@nelslindahlx` is the sole repository collaborator, GitHub prohibits PR authors from approving their own PRs; `enforce_admins` on `main` allows the repository owner to merge after all required CI checks pass and the Checker review is recorded. Add a second reviewer account and enable `enforce_admins` whenever strict two-person GitHub UI enforcement is desired.

---

## 5. Releases

Version tags (`vX.Y.Z`) are created from merged commits on `main` after verifying CI passes on `main`. See `.github/workflows/release.yml` for manual PyPI Trusted Publisher publishing.
