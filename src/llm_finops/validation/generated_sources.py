from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "generated"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class ValidationReport:
    checks: dict[str, str] = field(default_factory=dict)
    statistics: dict[str, Any] = field(default_factory=dict)

    def passed(self, check: str) -> None:
        self.checks[check] = "PASS"

    def as_dict(self) -> dict[str, Any]:
        return {"checks": self.checks, "statistics": self.statistics}


class GeneratedSourceValidator:
    required_files = {
        "raw_ai_provider_usage.csv",
        "raw_ai_provider_cost.csv",
        "fct_ai_request_telemetry.csv",
        "bridge_ai_usage_attribution.csv",
        "dim_ai_experiment_control.csv",
        "fct_ai_experiment_decision.csv",
        "generation_manifest.json",
    }

    def __init__(self, output_dir: Path, config_dir: Path) -> None:
        self.output_dir = output_dir
        self.config_dir = config_dir
        self.design = yaml.safe_load(
            (config_dir / "synthetic_design.yaml").read_text(encoding="utf-8")
        )
        self.manifest = json.loads(
            (output_dir / "generation_manifest.json").read_text(encoding="utf-8")
        )
        self.report = ValidationReport()

    def validate_required_files(self) -> None:
        present = {path.name for path in self.output_dir.iterdir() if path.is_file()}
        missing = self.required_files - present
        assert not missing, f"Missing generated files: {sorted(missing)}"
        self.report.passed("required_files")

    def validate_manifest_hashes(self) -> None:
        for filename, details in self.manifest["files"].items():
            path = self.output_dir / filename
            assert path.exists(), f"Manifest file is missing: {filename}"
            assert file_sha256(path) == details["sha256"], f"Hash mismatch: {filename}"
        self.report.passed("manifest_hashes")

    def validate_usage(self) -> None:
        path = self.output_dir / "raw_ai_provider_usage.csv"
        expected_fields = {
            "usage_date",
            "provider",
            "usage_type",
            "provider_project_id",
            "api_key_id",
            "model",
            "provider_service_tier",
            "is_batch",
            "context_window_tier",
            "request_count",
            "input_tokens",
            "output_tokens",
            "reasoning_tokens",
            "cached_input_tokens",
            "uncached_input_tokens",
            "cache_read_input_tokens",
            "cache_creation_5m_tokens",
            "cache_creation_1h_tokens",
            "is_synthetic",
        }
        grain_fields = (
            "usage_date",
            "provider",
            "usage_type",
            "provider_project_id",
            "api_key_id",
            "model",
            "provider_service_tier",
            "is_batch",
            "context_window_tier",
        )
        seen: set[tuple[str, ...]] = set()
        providers: set[str] = set()
        usage_types: set[tuple[str, str]] = set()
        row_count = 0
        minimum_date: date | None = None
        maximum_date: date | None = None

        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            assert set(reader.fieldnames or []) == expected_fields
            assert "usage_cost_estimate" not in (reader.fieldnames or [])

            for row in reader:
                row_count += 1
                key = tuple(row[field] for field in grain_fields)
                assert key not in seen, f"Duplicate usage grain: {key}"
                seen.add(key)
                assert row["is_synthetic"] == "true"
                assert row["reasoning_tokens"] == ""
                current = date.fromisoformat(row["usage_date"])
                minimum_date = current if minimum_date is None else min(minimum_date, current)
                maximum_date = current if maximum_date is None else max(maximum_date, current)
                providers.add(row["provider"])
                usage_types.add((row["provider"], row["usage_type"]))

                output_tokens = int(row["output_tokens"] or 0)
                assert output_tokens >= 0

                if row["provider"] == "openai":
                    input_tokens = int(row["input_tokens"] or 0)
                    cached_tokens = int(row["cached_input_tokens"] or 0)
                    assert row["request_count"] != ""
                    assert 0 <= cached_tokens <= input_tokens
                    assert row["uncached_input_tokens"] == ""
                    assert row["cache_read_input_tokens"] == ""
                    assert row["cache_creation_5m_tokens"] == ""
                    assert row["cache_creation_1h_tokens"] == ""
                    if row["usage_type"] == "embedding":
                        assert output_tokens == 0
                else:
                    assert row["request_count"] == ""
                    assert row["input_tokens"] == ""
                    assert row["cached_input_tokens"] == ""
                    for field in (
                        "uncached_input_tokens",
                        "cache_read_input_tokens",
                        "cache_creation_5m_tokens",
                        "cache_creation_1h_tokens",
                    ):
                        assert int(row[field] or 0) >= 0

                if row["is_batch"] == "true":
                    assert int(row["cached_input_tokens"] or 0) == 0
                    assert int(row["cache_read_input_tokens"] or 0) == 0
                    assert int(row["cache_creation_5m_tokens"] or 0) == 0
                    assert int(row["cache_creation_1h_tokens"] or 0) == 0

        target = self.design["source_targets"]["provider_usage_daily_rows"]
        if self.manifest["profile"] == "full":
            assert target["minimum"] <= row_count <= target["maximum"]
            assert minimum_date == date(2025, 1, 1)
            assert maximum_date == date(2026, 6, 30)
            assert providers == {"openai", "anthropic"}
            assert usage_types == {
                ("openai", "text_generation"),
                ("openai", "embedding"),
                ("anthropic", "text_generation"),
            }

        assert row_count == self.manifest["files"][path.name]["row_count"]
        self.report.statistics["usage_rows"] = row_count
        self.report.passed("usage_grain_and_token_rules")

    def validate_cost(self) -> None:
        path = self.output_dir / "raw_ai_provider_cost.csv"
        grain_fields = (
            "billing_period",
            "provider",
            "provider_project_id",
            "model",
            "line_item_type",
            "provider_line_item_id",
        )
        allowed_types = {
            "usage",
            "credit",
            "commitment_true_up",
            "correction",
            "adjustment",
            "tax",
        }
        seen: set[tuple[str, ...]] = set()
        line_types: set[str] = set()
        row_count = 0
        reported_total = 0.0
        invoice_total = 0.0

        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                row_count += 1
                key = tuple(row[field] for field in grain_fields)
                assert key not in seen, f"Duplicate cost grain: {key}"
                seen.add(key)
                assert row["billing_currency"] == "USD"
                assert row["is_synthetic"] == "true"
                assert row["line_item_type"] in allowed_types
                assert row["adjustment_reason"]
                line_types.add(row["line_item_type"])
                reported_total += float(row["provider_reported_cost"])
                invoice_total += float(row["invoice_billed_cost"])

                if row["line_item_type"] == "usage":
                    assert row["line_item_scope"] == "model"
                    assert row["model"]
                else:
                    assert row["model"] == ""
                    assert float(row["provider_reported_cost"]) == 0

                if row["line_item_type"] == "credit":
                    assert float(row["credit_amount"]) < 0
                    assert float(row["invoice_billed_cost"]) < 0
                else:
                    assert float(row["credit_amount"]) == 0

        if self.manifest["profile"] == "full":
            assert line_types == allowed_types
            assert not math_is_close(reported_total, invoice_total)
        assert row_count == self.manifest["files"][path.name]["row_count"]
        self.report.statistics["cost_rows"] = row_count
        self.report.statistics["provider_reported_cost"] = round(reported_total, 6)
        self.report.statistics["invoice_billed_cost"] = round(invoice_total, 6)
        self.report.passed("cost_grain_and_financial_rules")

    def validate_telemetry(self) -> None:
        path = self.output_dir / "fct_ai_request_telemetry.csv"
        provider_ids: set[str] = set()
        row_count = 0
        logical_count = 0
        current_logical = ""
        current_attempt = 0
        current_final_status = ""
        current_has_final = False
        retry_attempts = 0
        reasoning_rows = 0
        pre_processing_cost = 0.0
        mid_generation_cost = 0.0

        def close_logical_request() -> None:
            if current_logical:
                assert current_has_final, f"No final attempt for {current_logical}"

        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                row_count += 1
                provider_request_id = row["provider_request_id"]
                assert provider_request_id not in provider_ids
                provider_ids.add(provider_request_id)
                assert row["is_synthetic"] == "true"

                if row["logical_request_id"] != current_logical:
                    close_logical_request()
                    current_logical = row["logical_request_id"]
                    current_attempt = 0
                    current_final_status = row["final_request_status"]
                    current_has_final = False
                    logical_count += 1

                current_attempt += 1
                assert int(row["attempt_number"]) == current_attempt
                assert row["final_request_status"] == current_final_status
                is_final = row["is_final_attempt"] == "true"
                if is_final:
                    assert not current_has_final
                    current_has_final = True
                    assert row["retry_reason"] == ""
                else:
                    retry_attempts += 1
                    assert row["retry_reason"]

                input_tokens = int(row["input_tokens"] or 0)
                output_tokens = int(row["output_tokens"] or 0)
                reasoning_tokens = int(row["reasoning_tokens"] or 0)
                assert 0 <= reasoning_tokens <= output_tokens
                if reasoning_tokens > 0:
                    reasoning_rows += 1
                    assert row["provider"] == "openai"
                    assert row["model"] == "gpt-5"

                estimated_cost = float(row["usage_cost_estimate"])
                assert estimated_cost >= 0
                if row["failure_stage"] == "rejected_pre_processing":
                    assert input_tokens == 0
                    assert output_tokens == 0
                    assert estimated_cost == 0
                    pre_processing_cost += estimated_cost
                elif row["failure_stage"] == "mid_generation_error":
                    mid_generation_cost += estimated_cost

                if row["provider"] == "openai":
                    assert int(row["cached_input_tokens"] or 0) <= input_tokens
                    assert int(row["uncached_input_tokens"] or 0) == 0
                else:
                    assert input_tokens == 0
                    assert int(row["cached_input_tokens"] or 0) == 0

                if row["attempt_status"] == "success":
                    assert row["failure_stage"] == ""
                else:
                    assert row["failure_stage"] in {
                        "rejected_pre_processing",
                        "mid_generation_error",
                    }

        close_logical_request()
        target = self.design["source_targets"]["request_telemetry_attempt_rows"]
        if self.manifest["profile"] == "full":
            assert target["minimum"] <= row_count <= target["maximum"]
            assert reasoning_rows > 0
            assert mid_generation_cost > 0
            assert pre_processing_cost == 0

        details = self.manifest["files"][path.name]
        assert row_count == details["row_count"]
        assert logical_count == details["logical_request_count"]
        assert retry_attempts == details["retry_attempt_count"]
        self.report.statistics["telemetry_rows"] = row_count
        self.report.statistics["logical_requests"] = logical_count
        self.report.statistics["retry_attempts"] = retry_attempts
        self.report.passed("telemetry_attempt_and_token_rules")

    def validate_attribution(self) -> None:
        rows = read_csv(self.output_dir / "bridge_ai_usage_attribution.csv")
        grouped: dict[tuple[str, ...], float] = defaultdict(float)
        for row in rows:
            key = (
                row["provider"],
                row["provider_project_id"],
                row["api_key_id"],
                row["effective_start_date"],
                row["effective_end_date"],
            )
            grouped[key] += float(row["allocation_percentage"])
            assert row["is_synthetic"] == "true"
        assert all(total <= 1.0 + 1e-12 for total in grouped.values())
        if self.manifest["profile"] == "full":
            shared_total = sum(
                float(row["allocation_percentage"])
                for row in rows
                if row["api_key_id"] == "oa-key-shared"
            )
            assert abs(shared_total - 0.90) < 1e-12
            assert any(row["mapping_status"] == "late_restatement" for row in rows)
        self.report.passed("attribution_rules")

    def validate_experiments(self) -> None:
        controls = {
            row["experiment_id"]: row
            for row in read_csv(self.output_dir / "dim_ai_experiment_control.csv")
        }
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in read_csv(self.output_dir / "fct_ai_experiment_decision.csv"):
            grouped[row["experiment_id"]].append(row)
        assert set(controls) == set(grouped)
        for experiment_id, rows in grouped.items():
            ordered = sorted(rows, key=lambda item: item["decision_date"])
            assert ordered[0]["previous_status"] == "planned"
            for previous, current in zip(ordered, ordered[1:]):
                assert current["previous_status"] == previous["new_status"]
            assert controls[experiment_id]["current_status"] == ordered[-1]["new_status"]
            assert controls[experiment_id]["limit_currency"] == "USD"
        self.report.passed("experiment_history")

    def validate_known_events_have_source_rows(self) -> None:
        workloads = {
            row["workload_id"]: row
            for row in read_csv(self.config_dir / "workload_population.csv")
        }
        usage_keys: set[tuple[str, ...]] = set()
        with (self.output_dir / "raw_ai_provider_usage.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            for row in csv.DictReader(handle):
                usage_keys.add(
                    (
                        row["usage_date"],
                        row["provider"],
                        row["provider_project_id"],
                        row["api_key_id"],
                        row["model"],
                    )
                )
        if self.manifest["profile"] == "full":
            for event in read_csv(self.config_dir / "known_usage_events.csv"):
                workload = workloads[event["workload_id"]]
                key = (
                    event["event_date"],
                    workload["provider"],
                    workload["provider_project_id"],
                    workload["api_key_id"],
                    workload["provider_model_name"],
                )
                assert key in usage_keys, f"No generated usage row for event {event['event_id']}"
        self.report.passed("known_event_source_rows")

    def validate_all(self) -> ValidationReport:
        self.validate_required_files()
        self.validate_manifest_hashes()
        self.validate_usage()
        self.validate_cost()
        self.validate_telemetry()
        self.validate_attribution()
        self.validate_experiments()
        self.validate_known_events_have_source_rows()
        return self.report


def math_is_close(left: float, right: float) -> bool:
    return abs(left - right) <= max(0.01, abs(left) * 1e-9)


def validate_generated_sources(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    config_dir: Path = DEFAULT_CONFIG_DIR,
) -> dict[str, Any]:
    validator = GeneratedSourceValidator(output_dir, config_dir)
    return validator.validate_all().as_dict()
