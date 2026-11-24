# Repository Agent Governance (Maker / Checker Protocol)

All coding agents (including Antigravity) and automated contributors operating in this repository MUST follow the **Maker / Checker Pull Request** workflow before any code, documentation, or workflow change reaches `main`.

## 1. Hard Prohibitions

- **Never commit or push directly to `main`.** Always create a scoped branch (`feat/...`, `fix/...`, `chore/...`, `docs/...`, or `refactor/...`).
- **Never force-push** (`--force`, `--force-with-lease` on `main`), delete `main`, or bypass branch protection rules.
- **Never self-merge a PR** without explicit Checker review completed and explicit human approval from `@nelslindahlx`.
- **Never modify historical archives** under `legacy/` (preserved for reference; excluded from builds and CI).
- **Never write machine-local filesystem paths** (`/Users/...`, `file://...`) into GitHub issues, PR descriptions, PR comments, or committed docs.

## 2. Two-Stage Maker / Checker Workflow

### Stage A — Maker (Authoring & Self-Verification)
1. Branch cleanly from `origin/main` (`git checkout -b <type>/<short-slug>`).
2. Implement focused changes with strict typing, docstrings on new public APIs, and regression tests.
3. Run local quality gates before pushing:
   - `uv run python -W error::Warning -c "import knowledgereduce"`
   - `uv run ruff check src tests examples benchmarks`
   - `uv run ruff format --check src tests examples benchmarks`
   - `uv run mypy --strict src`
   - `uv run pytest --cov=knowledgereduce --cov-report=term-missing --cov-fail-under=85`
   - Run `examples/*.py`, stripped `notebooks/*.ipynb` checks, and `benchmarks/run_benchmark.py --scale 1000` whenever pipeline, storage, query, or mapper behavior changes.
4. Confirm zero tracked `*.pyc` files and zero committed outputs in `notebooks/*.ipynb`.
5. Push the feature branch and open a Pull Request against `main` using `.github/pull_request_template.md`, completing `## Summary`, `## Linked Issue`, and `## Maker Checklist` truthfully (reporting only directly observed results).

### Stage B — Checker (Independent Audit Prior to Merge)
Before requesting human approval or merging:
1. Perform an **independent read-only audit** of the full PR diff (`git diff origin/main...HEAD`) — checking edge cases, error handling, SSRF / path-containment (`ensure_within_base`) / parameterized DuckDB SQL invariants, API/doc alignment, and test rigor (especially negative and multi-row cases).
2. Verify all required GitHub Actions checks pass green on the latest PR commit:
   - `quality-and-tests (3.11)`
   - `quality-and-tests (3.12)`
   - `maker-checker-gate`
3. Post a structured Checker finding summary on the PR under `## Checker Review` (either approving for human merge with any caveats noted, or requesting changes on the branch if any gap is found).
4. Leave final approval and merge to `@nelslindahlx` (matching `.github/CODEOWNERS`) unless explicitly instructed to merge after review.
