from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from llm_finops.bigquery.semantic_model_deployer import deploy_m17  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deploy and validate the M17 Power BI semantic layer."
    )
    parser.add_argument("--project-id", default=None)
    args = parser.parse_args()

    manifest = deploy_m17(
        project_root=PROJECT_ROOT,
        config_path=PROJECT_ROOT / "config" / "m17_bigquery.yaml",
        project_id_override=args.project_id,
    )

    print("M17 POWER BI SEMANTIC LAYER PASSED")
    print(
        json.dumps(
            {
                "project_id": manifest["project_id"],
                "created_object_count": len(manifest["created_objects"]),
                "controls_passed": len(manifest["controls"]),
                "pipeline_run_id": manifest["pipeline_run_id"],
            },
            indent=2,
        )
    )

    subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "run_repo_ci.py")],
        cwd=PROJECT_ROOT,
        check=True,
    )


if __name__ == "__main__":
    main()
