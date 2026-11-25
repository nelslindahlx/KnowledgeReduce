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


def test_cli_incremental_ingest_parent_lineage_and_index_command(tmp_path: Path) -> None:
    runner = CliRunner()
    store_dir = tmp_path / "store"
    html_src = tmp_path / "ch_note.html"
    html_src.write_text(
        "<html><head><title>CH Note</title></head><body><main>"
        "<p>Civic Honors was published in 2006 to inspire student leaders.</p>"
        "</main></body></html>",
        encoding="utf-8",
    )
    txt_delta = tmp_path / "delta.txt"
    txt_delta.write_text(
        "Dr. Raymond Davis advised Civic Honors research in Kansas.",
        encoding="utf-8",
    )

    ing_base = tmp_path / "base_ing.jsonl"
    map_base = tmp_path / "base_map.jsonl"
    res_ing = runner.invoke(app, ["ingest", "-f", str(html_src), "-o", str(ing_base)])
    assert res_ing.exit_code == 0, res_ing.stdout
    assert json.loads(res_ing.stdout)["skipped_unchanged"] == 0

    assert runner.invoke(app, ["map", "-i", str(ing_base), "-o", str(map_base)]).exit_code == 0
    res_red_no_idx = runner.invoke(
        app,
        [
            "reduce",
            "--layer-id",
            "cli-base",
            "--name",
            "CLI Base",
            "-i",
            str(map_base),
            "-s",
            str(store_dir),
            "--no-build-index",
        ],
    )
    assert res_red_no_idx.exit_code == 0, res_red_no_idx.stdout
    assert not (store_dir / "layers" / "cli-base" / "claim_embeddings.parquet").exists()

    # Build persisted embeddings explicitly with `kr index`
    res_idx = runner.invoke(app, ["index", "cli-base", "-s", str(store_dir)])
    assert res_idx.exit_code == 0, res_idx.stdout
    assert json.loads(res_idx.stdout)["embeddings_indexed"] >= 1
    assert (store_dir / "layers" / "cli-base" / "claim_embeddings.parquet").is_file()

    # Incremental ingest skips unchanged html_src while capturing new txt_delta
    ing_delta = tmp_path / "delta_ing.jsonl"
    map_delta = tmp_path / "delta_map.jsonl"
    res_inc = runner.invoke(
        app,
        [
            "ingest",
            "-f",
            str(html_src),
            "-f",
            str(txt_delta),
            "--incremental-from",
            "cli-base",
            "-s",
            str(store_dir),
            "-o",
            str(ing_delta),
        ],
    )
    assert res_inc.exit_code == 0, res_inc.stdout
    inc_payload = json.loads(res_inc.stdout)
    assert inc_payload["document_count"] == 1
    assert inc_payload["skipped_unchanged"] == 1

    assert runner.invoke(app, ["map", "-i", str(ing_delta), "-o", str(map_delta)]).exit_code == 0
    res_child = runner.invoke(
        app,
        [
            "reduce",
            "--layer-id",
            "cli-delta",
            "--name",
            "CLI Delta",
            "--parent-layer",
            "cli-base",
            "-i",
            str(map_delta),
            "-s",
            str(store_dir),
        ],
    )
    assert res_child.exit_code == 0, res_child.stdout
    child_layer = json.loads(res_child.stdout)
    assert child_layer["parent_layer_ids"] == ["cli-base"]
    assert (store_dir / "layers" / "cli-delta" / "claim_embeddings.parquet").is_file()


def test_cli_structured_query_exports_analytics_and_error_branches(tmp_path: Path) -> None:
    runner = CliRunner()
    store_dir = tmp_path / "store"
    ing = tmp_path / "ing.jsonl"
    mp = tmp_path / "mp.jsonl"
    src_csv = tmp_path / "facts.csv"
    src_csv.write_text(
        "subject,subject_type,predicate,object,object_type,statement,category,tags,reliability\n"
        'Civic Honors,ORG,PUBLISHED_IN,2006,DATE,"Civic Honors was published in 2006.",Pub,"civic,book",VERIFIED\n',
        encoding="utf-8",
    )
    assert runner.invoke(app, ["ingest", "-f", str(src_csv), "-o", str(ing)]).exit_code == 0
    assert runner.invoke(app, ["map", "-i", str(ing), "-o", str(mp)]).exit_code == 0
    assert (
        runner.invoke(
            app,
            ["reduce", "--layer-id", "q-layer", "--name", "Q", "-i", str(mp), "-s", str(store_dir)],
        ).exit_code
        == 0
    )

    # Structured filter query branch (--category + --tag + --query)
    q_filtered = runner.invoke(
        app,
        [
            "query",
            "q-layer",
            "--category",
            "Pub",
            "--tag",
            "civic",
            "--query",
            "Civic Honors",
            "-s",
            str(store_dir),
        ],
    )
    assert q_filtered.exit_code == 0, q_filtered.stdout
    assert len(json.loads(q_filtered.stdout)) == 1

    # Export sharded_jsonl, gexf, markdown, and invalid format
    assert (
        runner.invoke(
            app,
            [
                "export",
                "q-layer",
                "-f",
                "sharded_jsonl",
                "-o",
                str(tmp_path / "shards"),
                "-s",
                str(store_dir),
            ],
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app,
            [
                "export",
                "q-layer",
                "-f",
                "gexf",
                "-o",
                str(tmp_path / "q.gexf"),
                "-s",
                str(store_dir),
            ],
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app,
            [
                "export",
                "q-layer",
                "-f",
                "markdown",
                "-o",
                str(tmp_path / "q.md"),
                "-s",
                str(store_dir),
            ],
        ).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app,
            ["export", "q-layer", "-f", "bogus", "-o", str(tmp_path / "bad"), "-s", str(store_dir)],
        ).exit_code
        == 1
    )

    # Analytics & catalog commands
    assert runner.invoke(app, ["layers", "-s", str(store_dir)]).exit_code == 0
    assert runner.invoke(app, ["lineage", "q-layer", "-s", str(store_dir)]).exit_code == 0
    assert runner.invoke(app, ["analyze", "q-layer", "-s", str(store_dir)]).exit_code == 0

    # Corrupt claims/entities to exercise `validate --strict` failure exit code 1
    from knowledgereduce.models import Claim, KnowledgeLayer, LayerData
    from knowledgereduce.storage import DuckDBParquetStore

    DuckDBParquetStore(store_dir).save_layer(
        LayerData(
            layer=KnowledgeLayer(layer_id="bad-layer", name="Bad"),
            claims=[
                Claim(claim_id="c1", statement="Dangling subject claim.", subject_id="missing_ent")
            ],
        )
    )
    assert (
        runner.invoke(app, ["validate", "bad-layer", "--strict", "-s", str(store_dir)]).exit_code
        == 1
    )

    # Representative error exits across CLI subcommands
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("layer_id: [unclosed", encoding="utf-8")
    for argv in [
        ["run", str(bad_yaml)],
        [
            "reduce",
            "--layer-id",
            "x",
            "--name",
            "X",
            "-i",
            str(tmp_path / "missing.jsonl"),
            "-s",
            str(store_dir),
        ],
        ["stack", "--layer", "missing-a", "--target", "out", "-s", str(store_dir)],
        ["diff", "missing-a", "q-layer", "-s", str(store_dir)],
        ["conflicts", "missing-a", "-s", str(store_dir)],
        [
            "resolve-conflict",
            "missing-a",
            "--conflict-id",
            "cf1",
            "--target",
            "out",
            "--winning-value",
            "x",
            "-s",
            str(store_dir),
        ],
        ["lineage", "missing-a", "-s", str(store_dir)],
        ["analyze", "missing-a", "-s", str(store_dir)],
        ["index", "missing-a", "-s", str(store_dir)],
    ]:
        res_err = runner.invoke(app, argv)
        assert res_err.exit_code == 1, f"Expected exit 1 for {argv}: {res_err.output}"


def test_cli_ingest_directory_and_glob(tmp_path: Path) -> None:
    runner = CliRunner()
    empty_res = runner.invoke(app, ["ingest", "-o", str(tmp_path / "empty.jsonl")])
    assert empty_res.exit_code == 1
    assert "--dir" in empty_res.output

    corpus = tmp_path / "cli_corpus"
    corpus.mkdir()
    (corpus / "keep.md").write_text(
        "---\ndate: 2025-01-10\ntags: [cli, ingest]\n---\n\nKept markdown body.",
        encoding="utf-8",
    )
    (corpus / "skip.txt").write_text("Excluded by --glob *.md.", encoding="utf-8")

    out_ckpt = tmp_path / "dir_ingest.jsonl"
    res = runner.invoke(
        app,
        ["ingest", "--dir", str(corpus), "--glob", "*.md", "-o", str(out_ckpt)],
    )
    assert res.exit_code == 0, res.output
    lines = [line for line in out_ckpt.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    assert '"source_type":"markdown"' in lines[0]
    assert '"cli"' in lines[0]
