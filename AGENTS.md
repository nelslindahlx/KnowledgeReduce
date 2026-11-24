# Project Rules & Agent Governance

This file defines repository rules and conventions for **KnowledgeReduce**, aligned with the zero-GitHub-Actions-minutes local CI and two-part Maker/Checker framework. Both `AGENTS.md` and `.agents/AGENTS.md` must stay byte-identical and under `24,000` bytes.

---

## 1. Zero GitHub Actions Minutes & Stratified Local CI

- **Manual-Only Workflows (`workflow_dispatch`)**: All GitHub Actions workflows in `.github/workflows/` MUST trigger strictly via `on: workflow_dispatch:` (no automatic `push` or `pull_request` triggers) so routine PRs and merges consume **zero** GitHub Actions minutes.
- **Stratified Local CI Commands (`Makefile`)**:
  - **Canary Meta Gate (`< 10s`)**: `make canary` (`uv run --no-sync python -W error::Warning -c "import knowledgereduce"` + `pytest tests/meta/ -q`).
  - **Lint & Format**: `make lint` (`ruff check src tests examples benchmarks scripts` + `ruff format --check ...`).
  - **Strict Type Check**: `make typecheck` (`mypy --strict src`).
  - **PR Smoke Tier**: `make smoke-pr` (`canary` + `lint` + `typecheck` + `tests/unit/` + `tests/golden/`).
  - **Full Local CI (Mandatory Before PR Merge)**: `make local-ci` (`canary`, `lint`, `typecheck`, `pytest --cov=knowledgereduce --cov-fail-under=85`, `examples/*.py`, stripped `notebooks/*.ipynb` execution, and `benchmarks/run_benchmark.py --scale 1000`).
  - **Real-World Golden Regression Gate**: `make golden` (`benchmarks/civichonors_book_benchmark.py --strict-regression`).

---

## 2. Two-Part Maker / Checker Pull Request Framework & Pre-Flight Guard

All modifications MUST flow through a two-part **Maker / Checker** GitHub Pull Request lifecycle:

- **Pre-Flight Branch Guard**: Never commit or push directly to `main`. Before editing any files, run `git branch --show-current`; if on `main`, switch immediately to an ephemeral branch (`feat/...`, `fix/...`, `chore/...`, `docs/...`, `refactor/...`). Once a branch is merged, never reuse its name.
- **Direct Push Ban & Mechanical Pre-PR Hook**: `.agents/hooks.json` (`scripts/hooks/pre_pr_safety_gate.py`) hard-denies `git push origin main` and automatically executes `pytest tests/meta/ -q` prior to `gh pr create|merge` or `scripts/github_pr_helper.py --create|--merge`.
- **Part 1 — Maker (Author)**:
  1. Implement focused changes with strict typing, docstrings on public APIs, and regression/negative tests.
  2. Update `CHANGELOG.md` (`## [X.Y.Z]`), `lessons_learned.md`, and `docs/plans/implementation_plan.md` when applicable.
  3. Pass `make local-ci` (and `make golden` when extraction, resolution, reduction, storage, or query logic changes).
  4. Push the branch and open a PR using `.github/pull_request_template.md`, completing `## Summary`, `## Linked Issue`, and `## Maker Checklist` truthfully from observed output.
- **Part 2 — Checker (Independent Auditor)**:
  1. Inspect `git diff origin/main...HEAD` and `git status --short` for edge cases, exception safety, SSRF (`validate_url_safe`), path containment (`ensure_within_base`), parameterized DuckDB SQL, and test rigor.
  2. Confirm `make local-ci` passes cleanly on the head commit and post findings in the PR `## Checker Review` comment/section.
  3. Squash-merge cleanly and delete the remote head branch via `scripts/github_pr_helper.py --merge --pr <N> --delete-branch` (or `gh pr merge <N> --squash --delete-branch`), then sync `main` (`git checkout main && git pull --ff-only origin main && git fetch --prune origin && git branch -d <branch>`).
- **Zero Lingering Open PR Invariant**: Before declaring work complete, execute `uv run --no-sync python scripts/github_pr_helper.py --audit` (`make audit-prs`) and verify it exits `0` (`Zero open pull requests`, `Zero lingering remote feature branches`).

---

## 3. Documentation Synchronicity & Release Tracking

- **Plans & Walkthroughs (`docs/plans/`)**: Archive milestone roadmaps (`docs/plans/master_plan_v<X_Y_Z>.md`), keep the active checklist in `docs/plans/implementation_plan.md`, and record verified milestone walkthroughs in `docs/plans/latest_walkthrough.md`.
- **Lessons Learned (`lessons_learned.md`)**: Store debugging insights, benchmark discoveries, and architectural lessons exclusively in `lessons_learned.md` rather than cluttering roadmap specs.
- **Continuous `CHANGELOG.md`**: Log every completed PR's scope, PR number, and observed benchmark/coverage impact under the active release heading.

---

## 4. Test Timings Reporting, Hermetic Isolation & Cross-Platform Invocation

- **Timings & Metrics Summary**: At the end of verification or milestone execution, present a structured table summarizing local CI stage timings, test counts, coverage percentage, golden benchmark recall/MRR, and 1K/10K scaling latency.
- **Hermetic Isolation**: Every test must use temporary directories (`tmp_path`) or isolated in-memory stores — never mutate tracked datasets under `tests/fixtures/` or `benchmarks/datasets/`.
- **Cross-Platform Invocation**: Prefer `uv run --no-sync python ...` over bare `python3` or POSIX-only paths; use forward slashes (`/`) in Markdown links.

---

## 5. Clean Workspace Hygiene & Zero Local Path Leakage

- Keep the root clean of stray caches and build outputs; never modify archived code under `legacy/`.
- Zero tracked `*.pyc` files (`git ls-files "*.pyc"` must be empty) and zero committed cell outputs in `notebooks/*.ipynb`.
- **Zero Machine-Local Paths**: Never write local workstation filesystem paths or `file://` URLs into committed source, documentation, `.github/`, GitHub issues, PR descriptions, or PR comments.

---

## 6. SemVer Parity & Code-First Invariants

- **SemVer Parity**: `[project].version` in `pyproject.toml` and `__version__` in `src/knowledgereduce/__init__.py` MUST match 1:1. Tag releases cleanly on `main` (`git tag -a vX.Y.Z -m "..."`).
- **Code-First Invariants**: Core invariants (workflow trigger checks, SemVer parity, path/output hygiene, circular-import safety, functional predicate rules, `PRESERVE_DISPUTE` defaults) are enforced mechanically in `tests/meta/test_governance_and_invariants.py`.

---

## 7. Referenced Rule Documents

- `.agents/rules/coding_method_guardrails.md` — 10 mandatory coding-method guardrails for pipeline, schema, security, and boundary safety.
- `.agents/rules/release_and_pr_management.md` — Release tagging, SemVer parity, `CHANGELOG.md`, `docs/plans/`, and Maker/Checker PR lifecycle procedures.
