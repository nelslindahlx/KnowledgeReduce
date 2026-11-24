"""Validate that curated notebooks contain zero committed outputs and execute cleanly."""

from __future__ import annotations

from pathlib import Path

import nbformat


def verify_all_notebooks(notebooks_dir: Path | str = "notebooks") -> int:
    """Verify and execute every ``*.ipynb`` under *notebooks_dir*."""
    paths = sorted(Path(notebooks_dir).glob("*.ipynb"))
    for nb_path in paths:
        nb = nbformat.read(nb_path, as_version=4)
        for idx, cell in enumerate(nb.cells):
            if cell.cell_type != "code":
                continue
            if cell.get("outputs") or cell.get("execution_count") is not None:
                raise AssertionError(
                    f"Committed outputs or execution_count found in {nb_path} cell {idx}"
                )
        namespace: dict[str, object] = {}
        for idx, cell in enumerate(nb.cells):
            if cell.cell_type == "code":
                code_obj = compile(cell.source, f"{nb_path}:cell[{idx}]", "exec")
                exec(code_obj, namespace)  # noqa: S102
    print(f"Verified and executed {len(paths)} curated notebook(s) with zero committed outputs.")
    return len(paths)


if __name__ == "__main__":
    verify_all_notebooks()
