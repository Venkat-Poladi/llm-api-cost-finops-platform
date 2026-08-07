from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_finops.foundation import write_foundation_evidence  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate the M21 enterprise foundation."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/m21/m21_foundation_summary.json"),
    )
    args = parser.parse_args()

    summary = write_foundation_evidence(ROOT, ROOT / args.output)

    print("M21 ENTERPRISE FOUNDATION PASSED")
    print(f"Provider channels: {summary['provider_channel_count']}")
    print(f"Production workloads: {summary['production_workload_count']}")
    print(f"Controlled experiments: {summary['experiment_count']}")
    print(f"Risk controls: {summary['risk_control_count']}")
    print(f"Evidence: {args.output.as_posix()}")


if __name__ == "__main__":
    main()
