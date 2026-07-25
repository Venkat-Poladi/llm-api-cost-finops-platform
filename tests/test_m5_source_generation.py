from __future__ import annotations

import csv
import json
from pathlib import Path

from llm_finops.generators.generate_sources import ConfigBundle, SourceGenerator
from llm_finops.validation.generated_sources import validate_generated_sources


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
OUTPUT_DIR = PROJECT_ROOT / "data" / "generated"


def load_manifest() -> dict:
    path = OUTPUT_DIR / "generation_manifest.json"
    assert path.exists(), "Run python scripts/generate_sources.py --overwrite first"
    return json.loads(path.read_text(encoding="utf-8"))


def test_full_generated_sources_pass_validation() -> None:
    report = validate_generated_sources(OUTPUT_DIR, CONFIG_DIR)
    assert set(report["checks"].values()) == {"PASS"}


def test_full_manifest_uses_locked_seed_and_period() -> None:
    manifest = load_manifest()

    assert manifest["profile"] == "full"
    assert manifest["master_seed"] == 42
    assert manifest["reporting_period"] == {
        "start_date": "2025-01-01",
        "end_date": "2026-06-30",
    }


def test_full_row_counts_are_within_locked_size_targets() -> None:
    manifest = load_manifest()
    usage_rows = manifest["files"]["raw_ai_provider_usage.csv"]["row_count"]
    telemetry_rows = manifest["files"]["fct_ai_request_telemetry.csv"]["row_count"]

    assert 4000 <= usage_rows <= 9000
    assert 150000 <= telemetry_rows <= 450000


def test_estimated_reported_and_invoiced_costs_disagree() -> None:
    manifest = load_manifest()
    estimated = manifest["files"]["fct_ai_request_telemetry.csv"][
        "usage_cost_estimate"
    ]
    reported = manifest["files"]["raw_ai_provider_cost.csv"][
        "provider_reported_cost"
    ]
    invoiced = manifest["files"]["raw_ai_provider_cost.csv"]["invoice_billed_cost"]

    assert estimated != reported
    assert reported != invoiced
    assert estimated != invoiced


def test_full_cost_source_contains_all_locked_line_types() -> None:
    with (OUTPUT_DIR / "raw_ai_provider_cost.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        line_types = {row["line_item_type"] for row in csv.DictReader(handle)}

    assert line_types == {
        "usage",
        "credit",
        "commitment_true_up",
        "correction",
        "adjustment",
        "tax",
    }


def test_raw_usage_contains_no_cost_column() -> None:
    with (OUTPUT_DIR / "raw_ai_provider_usage.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        fields = set(csv.DictReader(handle).fieldnames or [])

    assert "usage_cost_estimate" not in fields
    assert "provider_reported_cost" not in fields
    assert "invoice_billed_cost" not in fields


def test_small_profile_is_reproducible(tmp_path: Path) -> None:
    config = ConfigBundle.load(CONFIG_DIR)
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    first = SourceGenerator(config, first_dir, profile="test").generate_all()
    second = SourceGenerator(config, second_dir, profile="test").generate_all()

    first_hashes = {
        filename: details["sha256"] for filename, details in first["files"].items()
    }
    second_hashes = {
        filename: details["sha256"] for filename, details in second["files"].items()
    }
    assert first_hashes == second_hashes


def test_independent_sources_have_distinct_file_hashes() -> None:
    manifest = load_manifest()
    hashes = [
        manifest["files"][filename]["sha256"]
        for filename in (
            "raw_ai_provider_usage.csv",
            "raw_ai_provider_cost.csv",
            "fct_ai_request_telemetry.csv",
        )
    ]

    assert len(hashes) == len(set(hashes))
