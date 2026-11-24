# Release Publishing & Pull Request Management Guidelines

## 1. Release Publishing, SemVer Parity & CHANGELOG Protocol
- **Versioning Standard**: Adhere strictly to Semantic Versioning (`vMAJOR.MINOR.PATCH`).
- **Continuous Release Notes Logging**: Document every milestone's additions, bug fixes, algorithmic improvements, PR numbers, and observed benchmark metrics in `CHANGELOG.md` under `## [X.Y.Z] - YYYY-MM-DD`.
- **Manifest Parity**: Keep version strings synchronized 1:1 between `pyproject.toml` (`[project].version`) and `src/knowledgereduce/__init__.py` (`__version__`), verified mechanically by `tests/meta/test_governance_and_invariants.py`.
- **Annotated Release Tagging**:
  1. Verify clean `main` passes `make local-ci`, `make golden`, and `uv run --no-sync python scripts/github_pr_helper.py --audit`.
  2. Update `CHANGELOG.md`, `lessons_learned.md`, and `docs/plans/latest_walkthrough.md`.
  3. Create and push an annotated tag:
     ```bash
     git tag -a vX.Y.Z -m "Release vX.Y.Z: <summary>"
     git push origin vX.Y.Z
     ```
  4. Use manual `workflow_dispatch` on `.github/workflows/release.yml` (PyPI Trusted Publisher) only when publishing artifacts.

## 2. Plans, Walkthroughs & Lessons Learned Synchronization
- Archive milestone plans as `docs/plans/master_plan_v<X_Y_Z>.md`.
- Maintain the active implementation checklist in `docs/plans/implementation_plan.md` and latest verification walkthrough in `docs/plans/latest_walkthrough.md`.
- Record non-obvious bugs, edge cases, caching strategies, and benchmark insights in `lessons_learned.md`.
- **Strict Redaction Rule**: Never write machine-local filesystem paths into committed Markdown, GitHub issues, PR descriptions, or PR comments.

## 3. Maker / Checker PR Lifecycle & Zero-GitHub-Minutes Local CI
- **Zero Automatic GitHub Actions**: Keep all `.github/workflows/*.yml` files restricted to `on: workflow_dispatch:` so routine commits and PRs consume zero GitHub Actions minutes.
- **Branch Isolation & No Reuse**: Never commit or push directly to `main`. Create a dedicated branch (`feat/...`, `fix/...`, `chore/...`, `docs/...`, `refactor/...`) off `main`, and retire it upon merge.
- **Local Verification Before Merge**: Every PR must pass `make local-ci` locally and receive an independent Checker diff audit (`git diff origin/main...HEAD`) recorded in the PR's `## Checker Review` comment before merging.
- **Clean Merge & Zero-Lingering Audit**:
  ```bash
  uv run --no-sync python scripts/github_pr_helper.py --merge --pr <PR_NUMBER> --delete-branch
  git checkout main && git pull --ff-only origin main
  git fetch --prune origin
  uv run --no-sync python scripts/github_pr_helper.py --audit
  ```
  Always verify `--audit` exits `0` (`Zero open pull requests` and `Zero lingering remote feature branches`) before concluding a milestone.
