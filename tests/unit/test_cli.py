"""CLI integration tests using Typer CliRunner."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from knowledgereduce.cli import app

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_cli_full_local_workflow_commands(tmp_path: Path) -> None:
    runner = CliRunner()
    ckpt_1 = tmp_path / "01_ingested.jsonl"
    ckpt_2 = tmp_path / "02_mapped.jsonl"
    store_dir = tmp_path / "store"
    export_json = tmp_path / "out.json"
    export_gml = tmp_path / "out.graphml"

    # 1. ingest
    res = runner.invoke(
        app,
        [
            "ingest",
            "--file",
            str(FIXTURES_DIR / "civichonors_facts.csv"),
            "--file",
            str(FIXTURES_DIR / "civichonors_notes.json"),
            "--output",
            str(ckpt_1),
        ],
    )
    assert res.exit_code == 0, res.stdout
    assert json.loads(res.stdout)["document_count"] == 2

    # 2. map
    res = runner.invoke(
        app,
        ["map", "--input", str(ckpt_1), "--output", str(ckpt_2)],
    )
    assert res.exit_code == 0, res.stdout
    assert json.loads(res.stdout)["batch_count"] == 2

    # 3. reduce
    res = runner.invoke(
        app,
        [
            "reduce",
            "--layer-id",
            "cli-layer-1",
            "--name",
            "CLI Layer 1",
            "--input",
            str(ckpt_2),
            "--store",
            str(store_dir),
        ],
    )
    assert res.exit_code == 0, res.stdout
    assert json.loads(res.stdout)["layer_id"] == "cli-layer-1"

    # 4. stack & diff
    res2 = runner.invoke(
        app,
        [
            "reduce",
            "--layer-id",
            "cli-layer-2",
            "--name",
            "CLI Layer 2",
            "--input",
            str(ckpt_2),
            "--store",
            str(store_dir),
        ],
    )
    assert res2.exit_code == 0, res2.stdout

    res_stack = runner.invoke(
        app,
        [
            "stack",
            "--layer",
            "cli-layer-1",
            "--layer",
            "cli-layer-2",
            "--target",
            "cli-stacked",
            "--mode",
            "union",
            "--store",
            str(store_dir),
        ],
    )
    assert res_stack.exit_code == 0, res_stack.stdout

    res_diff = runner.invoke(
        app,
        ["diff", "cli-layer-1", "cli-stacked", "--store", str(store_dir)],
    )
    assert res_diff.exit_code == 0, res_diff.stdout

    # 5. query
    res_q = runner.invoke(
        app,
        ["query", "cli-stacked", "--query", "Civic Honors 2006", "--store", str(store_dir)],
    )
    assert res_q.exit_code == 0, res_q.stdout
    assert len(json.loads(res_q.stdout)["results"]) > 0

    # 6. export & validate
    res_exp = runner.invoke(
        app,
        [
            "export",
            "cli-stacked",
            "--format",
            "json",
            "--output",
            str(export_json),
            "--store",
            str(store_dir),
        ],
    )
    assert res_exp.exit_code == 0, res_exp.stdout
    assert export_json.is_file()

    res_gml = runner.invoke(
        app,
        [
            "export",
            "cli-stacked",
            "--format",
            "graphml",
            "--output",
            str(export_gml),
            "--store",
            str(store_dir),
        ],
    )
    assert res_gml.exit_code == 0, res_gml.stdout
    assert export_gml.is_file()

    res_val = runner.invoke(
        app,
        ["validate", "cli-stacked", "--store", str(store_dir), "--strict"],
    )
    assert res_val.exit_code == 0, res_val.stdout
    assert json.loads(res_val.stdout)["valid"] is True


def test_cli_run_from_yaml_and_error_exit(tmp_path: Path) -> None:
    runner = CliRunner()
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(
        f"""
layer_id: yaml-run
layer_name: YAML Run
store_dir: {tmp_path / "store"}
local_files:
  - path: {FIXTURES_DIR / "civichonors_facts.csv"}
    source_id: csv_curated
    trust_weight: 0.9
""",
        encoding="utf-8",
    )
    res = runner.invoke(app, ["run", str(cfg_path)])
    assert res.exit_code == 0, res.stdout
    assert json.loads(res.stdout)["layer_id"] == "yaml-run"

    bad = runner.invoke(app, ["validate", "does-not-exist", "--store", str(tmp_path / "store")])
    assert bad.exit_code == 1
    assert "Error:" in bad.output

    bad_rel = runner.invoke(
        app,
        ["query", "yaml-run", "--min-reliability", "99", "--store", str(tmp_path / "store")],
    )
    assert bad_rel.exit_code == 1
    assert "Error:" in bad_rel.output

    ckpt_empty = tmp_path / "empty_ingested.jsonl"
    ckpt_empty.write_text("", encoding="utf-8")
    bad_mapper = runner.invoke(
        app,
        [
            "map",
            "--input",
            str(ckpt_empty),
            "--output",
            str(tmp_path / "out_mapped.jsonl"),
            "--mapper",
            "bogus",
        ],
    )
    assert bad_mapper.exit_code == 1
    assert "Error:" in bad_mapper.output
