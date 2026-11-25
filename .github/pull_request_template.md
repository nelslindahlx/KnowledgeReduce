## Summary
<!-- Concise summary of what changed and why. -->

## Linked Issue
<!-- Reference resolved or related GitHub issues, e.g. Closes #123 or Related to #123 -->

## Maker Checklist
- [ ] Changes live on a dedicated feature branch targeting `main` (never pushed directly to `main`).
- [ ] Local CI ran and passed on the latest commit (`make local-ci`: canary meta-gate, `ruff check`, `ruff format --check`, `mypy --strict src`, `pytest --cov-fail-under=95`, `examples/*.py`, `notebooks/*.ipynb`, and 1K benchmark).
- [ ] Regression and negative tests cover new behavior/edge cases.
- [ ] Zero tracked `*.pyc` files, zero committed cell outputs in `notebooks/*.ipynb`, and zero leaked machine-local paths.
- [ ] `CHANGELOG.md`, `lessons_learned.md`, and `docs/plans/` updated as appropriate.

## Checker Review
<!-- Completed independently by the Checker reviewer prior to merge. -->
- [ ] Diff reviewed (`git diff origin/main...HEAD`) for correctness, security invariants (SSRF, path containment, parameterized SQL), and API consistency.
- [ ] Test assertions and edge cases audited (no relaxed/skipped assertions hiding bugs).
- [ ] Local CI verification outputs and timings recorded honestly.
- [ ] Merged cleanly via `scripts/github_pr_helper.py --merge --pr <N> --delete-branch` (or `gh pr merge --squash --delete-branch`) and audited via `--audit`.
