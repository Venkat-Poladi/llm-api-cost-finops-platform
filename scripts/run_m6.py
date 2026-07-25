from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from llm_finops.bigquery.raw_loader import execute_raw_load  # noqa: E402


def run_command(arguments: list[str]) -> None:
    subprocess.run(arguments, cwd=PROJECT_ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run M6: validate M5 and load the raw BigQuery layer."
    )
    parser.add_argument("--project-id", default=None)
    args = parser.parse_args()

    generated_dir = PROJECT_ROOT / "data" / "generated"
    required_source = generated_dir / "generation_manifest.json"

    if not required_source.exists():
        print("M5 output is missing. Generating it now...")
        run_command(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "generate_sources.py"),
                "--overwrite",
            ]
        )

    print("Validating local M5 sources...")
    run_command(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "validate_generated_sources.py"),
        ]
    )

    print("Loading eight raw objects to BigQuery...")
    manifest = execute_raw_load(
        project_root=PROJECT_ROOT,
        config_path=PROJECT_ROOT / "config" / "bigquery_load.yaml",
        project_id_override=args.project_id,
    )

    print("M6 BIGQUERY RAW LAYER PASSED")
    print(
        json.dumps(
            {
                "project_id": manifest["project_id"],
                "loaded_table_count": len(manifest["loaded_tables"]),
                "controls_passed": len(manifest["controls"]),
                "pipeline_run_id": manifest["pipeline_run_id"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
