from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from llm_finops.bigquery.telemetry_deployer import deploy_m10  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deploy and validate M10 telemetry reconciliation."
    )
    parser.add_argument("--project-id", default=None)
    args = parser.parse_args()

    manifest = deploy_m10(
        project_root=PROJECT_ROOT,
        config_path=PROJECT_ROOT / "config" / "m10_bigquery.yaml",
        project_id_override=args.project_id,
    )

    print("M10 TELEMETRY RECONCILIATION PASSED")
    print(
        json.dumps(
            {
                "project_id": manifest["project_id"],
                "created_object_count": len(manifest["created_objects"]),
                "controls_passed": len(manifest["controls"]),
                "summary": manifest["summary"],
                "pipeline_run_id": manifest["pipeline_run_id"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
