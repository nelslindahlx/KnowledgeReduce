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

    empty_ingest = runner.invoke(app, ["ingest", "--output", str(tmp_path / "empty_out.jsonl")])
    assert empty_ingest.exit_code == 1
    assert "Error:" in empty_ingest.output


def test_cli_conflicts_resolve_conflict_and_stack_reconcile(tmp_path: Path) -> None:
    runner = CliRunner()
    store_dir = tmp_path / "store"
    file_a = tmp_path / "a.csv"
    file_b = tmp_path / "b.csv"
    file_a.write_text(
        "subject,subject_type,predicate,object,object_type,statement,reliability\n"
        'Civic Honors,ORG,PUBLISHED_IN,2006,DATE,"Civic Honors was published in 2006.",VERIFIED\n',
        encoding="utf-8",
    )
    file_b.write_text(
        "subject,subject_type,predicate,object,object_type,statement,reliability\n"
        'Civic Honors,ORG,PUBLISHED_IN,2020,DATE,"Civic Honors was published in 2020.",UNVERIFIED\n',
        encoding="utf-8",
    )

    for tag, csv_file in [("a", file_a), ("b", file_b)]:
        ing = tmp_path / f"{tag}_ing.jsonl"
        mp = tmp_path / f"{tag}_map.jsonl"
        assert runner.invoke(app, ["ingest", "-f", str(csv_file), "-o", str(ing)]).exit_code == 0
        assert runner.invoke(app, ["map", "-i", str(ing), "-o", str(mp)]).exit_code == 0
        assert (
            runner.invoke(
                app,
                [
                    "reduce",
                    "--layer-id",
                    f"layer-{tag}",
                    "--name",
                    tag,
                    "-i",
                    str(mp),
                    "-s",
                    str(store_dir),
                ],
            ).exit_code
            == 0
        )

    res_stack = runner.invoke(
        app,
        [
            "stack",
            "--layer",
            "layer-a",
            "--layer",
            "layer-b",
            "--target",
            "stacked-rec",
            "--mode",
            "union",
            "--reconcile",
            "-s",
            str(store_dir),
        ],
    )
    assert res_stack.exit_code == 0, res_stack.output

    res_list = runner.invoke(app, ["conflicts", "stacked-rec", "-s", str(store_dir)])
    assert res_list.exit_code == 0, res_list.output
    listed = json.loads(res_list.stdout)
    assert listed["count"] == 1
    cf_id = listed["conflicts"][0]["conflict_id"]

    res_adj = runner.invoke(
        app,
        [
            "resolve-conflict",
            "stacked-rec",
            "--conflict-id",
            cf_id,
            "--target",
            "stacked-curated",
            "--winning-value",
            "2006",
            "--notes",
            "CLI adjudication verified",
            "-s",
            str(store_dir),
        ],
    )
    assert res_adj.exit_code == 0, res_adj.output
    adj_payload = json.loads(res_adj.stdout)
    assert adj_payload["resolved_conflict"]["needs_review"] is False
    assert adj_payload["layer"]["tier"] == "curated"

    res_open_after = runner.invoke(app, ["conflicts", "stacked-curated", "-s", str(store_dir)])
    assert res_open_after.exit_code == 0
    assert json.loads(res_open_after.stdout)["count"] == 0

    res_all_after = runner.invoke(
        app, ["conflicts", "stacked-curated", "--all", "-s", str(store_dir)]
    )
    assert res_all_after.exit_code == 0
    assert json.loads(res_all_after.stdout)["count"] == 1
