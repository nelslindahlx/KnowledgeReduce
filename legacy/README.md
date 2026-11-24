# Legacy Artifacts (Deprecated)

> **Deprecation Notice:** Everything inside `legacy/` is an unmaintained historical snapshot preserved for reference from the 2023–2025 exploratory phase (`archive/experiments-2023-2025` tag).
>
> **Do not import or run code from `legacy/` in production.** It is intentionally excluded from package builds, `ruff`, `mypy`, and `pytest` CI checks.

## Contents
- `legacy/notebooks/` — 35 historical Google Colab exploration notebooks (`CivicHonors*.ipynb`, `KGpkgBuildv4.ipynb`, `updated_json_sharding_notebook.ipynb`).
- `legacy/experiments/` — 12 experimental automation iterations (`Mantus Batch File Download`, `Manus Task`, `Manus Task 2nd Attempt`–`10th Attempt`, `Manus Review of Tasks`).
- `legacy/knowledge_graph_pkg/` — Original 133-LOC prototype package superseded by `src/knowledgereduce/`.

For the production-ready codebase, see `src/knowledgereduce/` and the root `README.md`.
