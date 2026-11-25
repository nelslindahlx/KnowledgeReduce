# Contributing to KnowledgeReduce

KnowledgeReduce enforces a **Maker / Checker Pull Request** process on `main` paired with **zero-GitHub-Actions-minutes stratified local CI**. Direct pushes to `main` are blocked; all changes flow through ephemeral feature branches, complete local CI verification, independent Checker diff audits, and clean PR merges.

---

## 1. Branch & Environment Setup

```bash
git checkout main
git pull --ff-only origin main
git checkout -b <type>/<short-description>   # e.g. feat/fts-index, fix/crawl-timeout, chore/docs
uv sync --extra dev
```

Always confirm `git branch --show-current` is **not** `main` before committing, and never reuse a previously merged branch name.

---

## 2. Stratified Local CI (Zero GitHub Action Minutes)

Automatic GitHub Actions triggers (`push`, `pull_request`) are disabled (`workflow_dispatch` only) so routine development consumes **zero** GitHub Actions minutes. Run verification locally using the `Makefile` targets:

```bash
make canary      # <10s: import warning gate + tests/meta/ invariants & governance checks
make lint        # ruff check & ruff format --check across src, tests, examples, benchmarks, scripts
make typecheck   # mypy --strict src
make smoke-pr    # canary + lint + typecheck + tests/unit/ + tests/golden/
make test        # full pytest suite with --cov-fail-under=95
make golden      # Civic Honors book and multi-source stack strict regression benchmarks
make local-ci    # complete local CI gate (canary + lint + typecheck + test + examples + notebooks + 1K benchmark)
```

Cross-platform invocations also work directly without `make`:

```bash
uv run --no-sync python -W error::Warning -c "import knowledgereduce"
uv run --no-sync ruff check src tests examples benchmarks scripts
uv run --no-sync ruff format --check src tests examples benchmarks scripts
uv run --no-sync mypy --strict src
uv run --no-sync pytest --cov=knowledgereduce --cov-report=term-missing --cov-fail-under=95
uv run --no-sync python benchmarks/run_benchmark.py --scale 1000
```

---

## 3. Maker & Checker Workflow

### Stage A — Maker (Authoring & Local CI)
1. Implement focused changes with strict typing, docstrings on new public APIs, and regression/negative tests.
2. Update `CHANGELOG.md`, `lessons_learned.md`, and `docs/plans/implementation_plan.md` when adding features, fixing subtle bugs, or completing roadmap milestones.
3. Run `make local-ci` (and `make golden` when changing extraction, resolution, reduction, storage, or GraphRAG behavior).
4. Push the branch and open a PR using `.github/pull_request_template.md`, completing `## Summary`, `## Linked Issue`, and `## Maker Checklist` truthfully from observed command outputs (with zero machine-local paths).

### Stage B — Checker (Audit, Merge & Zero-Lingering Check)
1. Audit `git diff origin/main...HEAD` for boundary correctness, SSRF validation (`validate_url_safe`), export/workspace path sandboxing (`ensure_within_base`), parameterized DuckDB SQL (`read_parquet(?)`, `UNNEST`), and test coverage.
2. Confirm `make local-ci` passed on the head commit and record the findings under `## Checker Review` on the PR.
3. Merge and clean up the branch via:
   ```bash
   uv run --no-sync python scripts/github_pr_helper.py --merge --pr <PR_NUMBER> --delete-branch
   git checkout main && git pull --ff-only origin main
   git fetch --prune origin
   uv run --no-sync python scripts/github_pr_helper.py --audit
   ```

---

## 4. Releases

Version strings in `pyproject.toml` and `src/knowledgereduce/__init__.py` must match 1:1. Annotated release tags (`vX.Y.Z`) are created from merged commits on `main` after `make local-ci`, `make golden`, and `--audit` pass cleanly. See `.github/workflows/release.yml` for manual `workflow_dispatch` PyPI Trusted Publisher releases.
