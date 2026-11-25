"""Meta-tests enforcing repository governance, zero-GitHub-minutes CI, and code invariants."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import yaml

import knowledgereduce
from knowledgereduce.map.nlp import _ANCHORED_VERB_MAP
from knowledgereduce.mcp import create_mcp_server
from knowledgereduce.models import ConflictStrategy
from knowledgereduce.reduce import KnowledgeReducer
from knowledgereduce.reduce.conflicts import DEFAULT_FUNCTIONAL_PREDICATES, is_functional_predicate
from scripts.hooks.pre_pr_safety_gate import evaluate_command

REPO_ROOT = Path(__file__).resolve().parents[2]
_MAX_AGENTS_BYTES = 24_000
_BACKTICK_PATH_RE = re.compile(
    r"`((?:src|tests|benchmarks|scripts|docs|\.github|\.agents)/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+|"
    r"Makefile|pyproject\.toml|AGENTS\.md|CHANGELOG\.md|CONTRIBUTING\.md|lessons_learned\.md)`"
)


def test_agents_md_parity_and_size_budget() -> None:
    root_agents = REPO_ROOT / "AGENTS.md"
    scoped_agents = REPO_ROOT / ".agents" / "AGENTS.md"
    assert root_agents.is_file()
    assert scoped_agents.is_file()
    root_bytes = root_agents.read_bytes()
    assert root_bytes == scoped_agents.read_bytes(), (
        "AGENTS.md and .agents/AGENTS.md must remain byte-identical."
    )
    assert len(root_bytes) < _MAX_AGENTS_BYTES


def test_semver_manifest_parity() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pyproject_ver = pyproject["project"]["version"]
    assert knowledgereduce.__version__ == pyproject_ver
    citation = yaml.safe_load(
        (REPO_ROOT / "docs" / "paper" / "CITATION.cff").read_text(encoding="utf-8")
    )
    assert str(citation["version"]) == pyproject_ver


def test_github_workflows_are_workflow_dispatch_only() -> None:
    workflows_dir = REPO_ROOT / ".github" / "workflows"
    workflow_files = sorted(workflows_dir.glob("*.yml"))
    assert workflow_files, "Expected GitHub Actions workflow files under .github/workflows/"
    for wf_path in workflow_files:
        parsed = yaml.safe_load(wf_path.read_text(encoding="utf-8"))
        # PyYAML may parse bare `on:` as boolean True key in YAML 1.1
        triggers = parsed.get("on") if "on" in parsed else parsed.get(True)
        if isinstance(triggers, str):
            trigger_keys = {triggers}
        elif isinstance(triggers, (list, dict)):
            trigger_keys = {str(k) for k in triggers}
        else:
            trigger_keys = set()
        assert trigger_keys == {"workflow_dispatch"}, (
            f"{wf_path.name} must trigger ONLY on workflow_dispatch to save GitHub Actions minutes "
            f"(found {trigger_keys!r})."
        )


def test_no_tracked_pyc_or_notebook_outputs_or_local_paths() -> None:
    git_bin = shutil.which("git")
    assert git_bin is not None
    pyc_out = subprocess.check_output(  # noqa: S603
        [git_bin, "ls-files", "*.pyc"],
        cwd=str(REPO_ROOT),
        text=True,
    ).strip()
    assert pyc_out == "", f"Tracked .pyc files found:\n{pyc_out}"

    for nb_path in sorted((REPO_ROOT / "notebooks").glob("*.ipynb")):
        nb = json.loads(nb_path.read_text(encoding="utf-8"))
        for idx, cell in enumerate(nb.get("cells", [])):
            if cell.get("cell_type") != "code":
                continue
            assert not cell.get("outputs"), f"Notebook {nb_path.name} cell {idx} has outputs."
            assert cell.get("execution_count") is None, (
                f"Notebook {nb_path.name} cell {idx} has non-null execution_count."
            )

    forbidden_needles = (
        "/" + "Users/",
        "file:///" + "Users/",
        "C:" + "\\Users\\",
    )
    checked_paths: list[Path] = [
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "CONTRIBUTING.md",
        REPO_ROOT / "CHANGELOG.md",
        REPO_ROOT / "Makefile",
        REPO_ROOT / "README.md",
        REPO_ROOT / "lessons_learned.md",
        *sorted((REPO_ROOT / ".github").rglob("*")),
        *sorted((REPO_ROOT / ".agents").rglob("*")),
        *sorted((REPO_ROOT / "docs").glob("*.md")),
        *sorted((REPO_ROOT / "docs" / "plans").glob("*.md")),
        *sorted((REPO_ROOT / "scripts").rglob("*.py")),
        *sorted((REPO_ROOT / "tests" / "meta").glob("*.py")),
    ]
    for path in checked_paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for needle in forbidden_needles:
            assert needle not in text, f"Machine-local path {needle!r} leaked into {path}"


def test_lessons_learned_relevance_and_integrity() -> None:
    lessons_path = REPO_ROOT / "lessons_learned.md"
    assert lessons_path.is_file(), "lessons_learned.md must exist at repository root."
    content = lessons_path.read_text(encoding="utf-8")
    assert len(content.strip()) > 200

    headings = re.findall(r"^##\s+Lesson\s+\d+:", content, flags=re.MULTILINE)
    assert len(headings) >= 5, (
        f"Expected >=5 numbered lessons in lessons_learned.md (got {len(headings)})."
    )

    referenced_paths = set(_BACKTICK_PATH_RE.findall(content))
    assert len(referenced_paths) >= 8, (
        "lessons_learned.md should reference concrete KnowledgeReduce source/test/config files."
    )
    for rel_path in sorted(referenced_paths):
        target = REPO_ROOT / rel_path
        assert target.exists(), f"lessons_learned.md references nonexistent repo path: {rel_path}"

    required_domain_anchors = (
        "knowledgereduce",
        "DuckDB",
        "AsyncWebCrawler",
        "DeterministicNLPMapper",
        "KnowledgeReducer",
        "GraphRAG",
        "Civic Honors",
    )
    for anchor in required_domain_anchors:
        assert anchor.lower() in content.lower(), (
            f"lessons_learned.md is missing KnowledgeReduce domain context {anchor!r}."
        )

    foreign_needles = (
        "two-adic" + "-zipper",
        "two_adic" + "_zipper",
        "zipper_engine" + "_rust",
        "RSA" + "-8192",
        "Coppersmith" + "Solver",
        "hensel" + "-lifting",
        "solver_quarantine" + ".json",
    )
    governance_files: list[Path] = [
        lessons_path,
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "CONTRIBUTING.md",
        REPO_ROOT / "Makefile",
        REPO_ROOT / "CHANGELOG.md",
        *sorted((REPO_ROOT / ".agents").rglob("*")),
        *sorted((REPO_ROOT / "docs" / "plans").glob("*.md")),
        *sorted((REPO_ROOT / "scripts").rglob("*.py")),
    ]
    for path in governance_files:
        if not path.is_file():
            continue
        file_text = path.read_text(encoding="utf-8", errors="ignore")
        for needle in foreign_needles:
            assert needle.lower() not in file_text.lower(), (
                f"Foreign template term {needle!r} found in {path}; keep rules KnowledgeReduce-specific."
            )


def test_pre_pr_safety_gate_blocks_direct_main_push_and_allows_feature_push() -> None:
    deny_main = evaluate_command(
        "git push origin main",
        REPO_ROOT,
        run_meta_suite=False,
    )
    assert deny_main["decision"] == "deny"

    deny_head = evaluate_command(
        "git push --force origin HEAD:main",
        REPO_ROOT,
        run_meta_suite=False,
    )
    assert deny_head["decision"] == "deny"

    allow_feat = evaluate_command(
        "git push -u origin feat/v1.3-example",
        REPO_ROOT,
        run_meta_suite=False,
    )
    assert allow_feat["decision"] == "allow"


def test_runtime_domain_invariants_and_import_safety() -> None:
    assert "PUBLISHED_IN" in DEFAULT_FUNCTIONAL_PREDICATES
    assert is_functional_predicate("published_in")
    assert is_functional_predicate("LAUNCHED_AT")
    assert not is_functional_predicate("MENTIONS")

    reducer = KnowledgeReducer()
    assert reducer.conflict_strategy == ConflictStrategy.PRESERVE_DISPUTE

    # Anchored narrative verbs must never accidentally use _ON/_IN/_AT/_YEAR/_DATE functional suffixes.
    for pred in _ANCHORED_VERB_MAP.values():
        assert not is_functional_predicate(pred), (
            f"Anchored predicate {pred!r} collides with functional conflict rules."
        )

    # Guard against circular imports between resolve and reduce regardless of import order.
    proc = subprocess.run(
        [sys.executable, "-c", "import knowledgereduce.resolve; import knowledgereduce.reduce"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


def test_docs_mcp_tools_and_readme_local_ci_parity(tmp_path: Path) -> None:
    server = create_mcp_server(tmp_path)
    tool_names = {tool.name for tool in asyncio.run(server.list_tools())}
    mcp_doc = (REPO_ROOT / "docs" / "mcp_antigravity.md").read_text(encoding="utf-8")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert f"({len(tool_names)} Tools)" in mcp_doc
    for name in sorted(tool_names):
        assert f"`{name}`" in mcp_doc, f"Missing MCP tool {name!r} in docs/mcp_antigravity.md"
        assert f"`{name}`" in readme, f"Missing MCP tool {name!r} in README.md"

    assert "make local-ci" in readme
    assert "quality-and-tests (3.11)" not in readme
    assert "maker-checker-gate" not in readme
    assert f"knowledgereduce {knowledgereduce.__version__}" in readme


def test_coverage_gate_parity() -> None:
    gate_files = (
        REPO_ROOT / "Makefile",
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / ".agents" / "AGENTS.md",
        REPO_ROOT / "CONTRIBUTING.md",
        REPO_ROOT / ".github" / "pull_request_template.md",
        REPO_ROOT / ".github" / "workflows" / "ci.yml",
    )
    for path in gate_files:
        text = path.read_text(encoding="utf-8")
        assert "--cov-fail-under=95" in text, f"Expected 95% coverage gate in {path.name}"
        assert "--cov-fail-under=85" not in text, f"Stale 85% coverage gate in {path.name}"
