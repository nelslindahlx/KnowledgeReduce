## Summary
<!-- Concise summary of what changed and why. -->

## Linked Issue
<!-- Reference resolved or related GitHub issues, e.g. Closes #123 or Related to #123 -->

## Maker Checklist
- [ ] Changes live on a feature branch targeting `main` (not committed directly to `main`).
- [ ] Local quality checks ran and passed on the latest commit (`ruff check`, `ruff format --check`, `mypy --strict src`, `pytest --cov-fail-under=85`).
- [ ] Regression and negative tests cover new behavior/edge cases.
- [ ] Zero tracked `*.pyc` files and zero committed cell outputs in `notebooks/*.ipynb`.
- [ ] Documentation / examples / `CHANGELOG.md` updated if public APIs or behavior changed.

## Checker Review
<!-- Completed independently by the Checker reviewer (agent audit + human sign-off) prior to merge. -->
- [ ] Diff reviewed for correctness, security invariants (SSRF, path containment, parameterized SQL), and API consistency.
- [ ] Test assertions and edge cases audited (no relaxed/skipped assertions hiding bugs).
- [ ] All required CI checks (`quality-and-tests (3.11)`, `quality-and-tests (3.12)`, `maker-checker-gate`) pass on head commit.
- [ ] CODEOWNER sign-off and open review conversations resolved before merge.
