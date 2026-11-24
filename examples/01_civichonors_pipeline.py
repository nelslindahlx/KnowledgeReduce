"""Example 1: Offline multi-source CivicHonors knowledge reduction into DuckDB + Parquet."""

from __future__ import annotations

import tempfile
from pathlib import Path

from knowledgereduce import (
    ConflictStrategy,
    DuckDBParquetStore,
    IntegrityValidator,
    LocalFileSourceConfig,
    PipelineConfig,
    PipelineRunner,
)


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    fixtures_dir = repo_root / "tests" / "fixtures"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        prose_file = tmp_path / "civichonors_prose.txt"
        prose_file.write_text(
            "Civic Honors was published in 2006 in Denver, Colorado.\n"
            "Dr. Nels Lindahl studied at University of Kansas under Dr. H. George Frederickson.\n"
            "Civic Honors was published in 2020 in Denver, Colorado.\n",
            encoding="utf-8",
        )

        store_dir = tmp_path / "store"
        ckpt_dir = tmp_path / "checkpoints"
        config = PipelineConfig(
            layer_id="civichonors-demo",
            layer_name="Civic Honors Demo Layer",
            store_dir=str(store_dir),
            checkpoint_dir=str(ckpt_dir),
            local_files=[
                LocalFileSourceConfig(
                    path=str(fixtures_dir / "civichonors_facts.csv"),
                    source_id="csv_curated",
                    trust_weight=0.95,
                ),
                LocalFileSourceConfig(
                    path=str(fixtures_dir / "civichonors_notes.json"),
                    source_id="json_notes",
                    trust_weight=0.90,
                ),
                LocalFileSourceConfig(
                    path=str(prose_file),
                    source_id="prose_excerpt",
                    trust_weight=0.65,
                ),
            ],
            conflict_strategy=ConflictStrategy.PRESERVE_DISPUTE,
            min_sentence_length=20,
        )

        layer_data = PipelineRunner().run(config)
        store = DuckDBParquetStore(store_dir)
        report = IntegrityValidator().validate(store.load_layer("civichonors-demo"), strict=True)

        assert report.valid
        assert len(layer_data.relations) > 0
        assert len(layer_data.conflicts) >= 1
        print("Layer stats:", layer_data.layer.stats)
        print("Validation metrics:", report.metrics)


if __name__ == "__main__":
    main()
