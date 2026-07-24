from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path
import csv

import yaml


CONFIG = Path("config")
PERIOD_START = date(2025, 1, 1)
PERIOD_END = date(2026, 6, 30)


def read_csv(filename: str) -> list[dict[str, str]]:
    path = CONFIG / filename
    assert path.exists(), f"{path} is missing"
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def test_reporting_period_is_18_complete_months() -> None:
    design = yaml.safe_load(
        (CONFIG / "synthetic_design.yaml").read_text(encoding="utf-8")
    )
    period = design["reporting_period"]

    assert str(period["start_date"]) == "2025-01-01"
    assert str(period["end_date"]) == "2026-06-30"
    assert period["complete_months"] == 18
    assert period["reporting_currency"] == "USD"


def test_random_streams_are_separate_and_repeatable() -> None:
    design = yaml.safe_load(
        (CONFIG / "synthetic_design.yaml").read_text(encoding="utf-8")
    )
    streams = list(design["randomness"]["streams"].values())

    assert design["randomness"]["master_seed"] == 42
    assert len(streams) == len(set(streams))


def test_workload_ids_are_unique() -> None:
    rows = read_csv("workload_population.csv")
    ids = [row["workload_id"] for row in rows]

    assert len(rows) == 12
    assert len(ids) == len(set(ids))


def test_workloads_use_allowed_provider_and_usage_combinations() -> None:
    rows = read_csv("workload_population.csv")
    combinations = {(row["provider"], row["usage_type"]) for row in rows}

    assert combinations == {
        ("openai", "text_generation"),
        ("openai", "embedding"),
        ("anthropic", "text_generation"),
    }


def test_workload_dates_are_inside_the_reporting_period() -> None:
    for row in read_csv("workload_population.csv"):
        start = parse_date(row["active_start"])
        end = parse_date(row["active_end"])

        assert PERIOD_START <= start <= end <= PERIOD_END


def test_every_workload_model_is_valid_for_its_active_window() -> None:
    model_rows = read_csv("model_map.csv")
    model_windows: dict[tuple[str, str, str], list[tuple[date, date]]] = defaultdict(list)

    for row in model_rows:
        key = (
            row["provider"],
            row["usage_type"],
            row["provider_model_name"],
        )
        model_windows[key].append(
            (parse_date(row["effective_start"]), parse_date(row["effective_end"]))
        )

    for workload in read_csv("workload_population.csv"):
        key = (
            workload["provider"],
            workload["usage_type"],
            workload["provider_model_name"],
        )
        active_start = parse_date(workload["active_start"])
        active_end = parse_date(workload["active_end"])

        assert any(
            model_start <= active_start and active_end <= model_end
            for model_start, model_end in model_windows[key]
        ), f"No model-map window covers {workload['workload_id']}"


def test_every_workload_has_a_rate_combination() -> None:
    service_tiers = yaml.safe_load(
        (CONFIG / "service_tier_map.yaml").read_text(encoding="utf-8")
    )
    normalization = {
        (row["provider"], row["provider_service_tier"]): (
            row["normalized_processing_tier"],
            str(row["is_batch_rule"]).lower(),
        )
        for row in service_tiers["normalization"]
        if row["used_in_v1"]
    }

    model_map = {
        (row["provider"], row["usage_type"], row["provider_model_name"]): row[
            "model_snapshot"
        ]
        for row in read_csv("model_map.csv")
    }

    rates = {
        (
            row["provider"],
            row["usage_type"],
            row["model_snapshot"],
            row["normalized_processing_tier"],
            row["is_batch"],
            row["context_window_tier"],
        )
        for row in read_csv("model_rates.csv")
    }

    for workload in read_csv("workload_population.csv"):
        normalized_tier, _ = normalization[
            (workload["provider"], workload["provider_service_tier"])
        ]
        snapshot = model_map[
            (
                workload["provider"],
                workload["usage_type"],
                workload["provider_model_name"],
            )
        ]
        rate_key = (
            workload["provider"],
            workload["usage_type"],
            snapshot,
            normalized_tier,
            workload["is_batch"],
            workload["context_window_tier"],
        )
        assert rate_key in rates, f"No rate combination for {workload['workload_id']}"


def test_embedding_and_reasoning_rules_are_explicit() -> None:
    rows = read_csv("workload_population.csv")

    for row in rows:
        if row["usage_type"] == "embedding":
            assert row["provider"] == "openai"
            assert float(row["median_output_tokens"]) == 0
            assert float(row["reasoning_share_of_output"]) == 0

        if float(row["reasoning_share_of_output"]) > 0:
            assert row["provider_model_name"] == "gpt-5"


def test_batch_workloads_have_no_cache_share() -> None:
    for row in read_csv("workload_population.csv"):
        if row["is_batch"] == "true":
            assert float(row["cache_read_share"]) == 0
            assert float(row["cache_write_5m_share"]) == 0
            assert float(row["cache_write_1h_share"]) == 0


def test_telemetry_rates_and_coverage_are_valid() -> None:
    for row in read_csv("workload_population.csv"):
        assert 0 < float(row["telemetry_coverage_pct"]) <= 1
        assert 0 <= float(row["failure_rate"]) < 1
        assert 0 <= float(row["retry_rate"]) < 1


def test_attribution_percentages_do_not_overallocate() -> None:
    grouped: dict[tuple[str, ...], float] = defaultdict(float)

    for row in read_csv("attribution_scenarios.csv"):
        key = (
            row["provider"],
            row["provider_project_id"],
            row["api_key_id"],
            row["effective_start_date"],
            row["effective_end_date"],
        )
        grouped[key] += float(row["allocation_percentage"])

    for key, total in grouped.items():
        assert total <= 1.0 + 1e-12, f"Overallocation for {key}: {total}"


def test_required_attribution_imperfections_exist() -> None:
    mappings = read_csv("attribution_scenarios.csv")
    workloads = read_csv("workload_population.csv")

    shared_total = sum(
        float(row["allocation_percentage"])
        for row in mappings
        if row["api_key_id"] == "oa-key-shared"
    )
    assert abs(shared_total - 0.90) < 1e-12

    developer_rows = [
        row for row in mappings if row["api_key_id"] == "an-key-developer"
    ]
    assert len(developer_rows) == 2
    assert {row["cost_center"] for row in developer_rows} == {"CC400", "CC410"}

    late_mapping = next(
        row for row in mappings if row["mapping_status"] == "late_restatement"
    )
    assert parse_date(late_mapping["mapping_recorded_date"]) > parse_date(
        late_mapping["effective_start_date"]
    )

    mapped_keys = {
        (row["provider"], row["provider_project_id"], row["api_key_id"])
        for row in mappings
    }
    assert any(
        (
            row["provider"],
            row["provider_project_id"],
            row["api_key_id"],
        )
        not in mapped_keys
        for row in workloads
    )


def test_known_usage_events_are_valid_and_cross_provider() -> None:
    events = read_csv("known_usage_events.csv")
    workloads = {
        row["workload_id"]: row for row in read_csv("workload_population.csv")
    }

    assert len(events) == 6
    assert len({row["event_id"] for row in events}) == len(events)

    providers = set()
    for event in events:
        event_date = parse_date(event["event_date"])
        workload = workloads[event["workload_id"]]
        providers.add(workload["provider"])

        assert parse_date(workload["active_start"]) <= event_date <= parse_date(
            workload["active_end"]
        )
        assert float(event["multiplier"]) > 0
        assert int(event["duration_days"]) >= 1

    assert providers == {"openai", "anthropic"}


def test_cost_divergence_design_has_required_line_types_and_exceptions() -> None:
    rows = read_csv("cost_divergence_events.csv")
    non_usage_types = {
        row["line_item_type"] for row in rows if row["line_item_type"] != "usage"
    }

    assert non_usage_types == {
        "credit",
        "commitment_true_up",
        "correction",
        "adjustment",
        "tax",
    }

    exceptions = [
        row for row in rows if row["expected_tolerance_status"] == "exception"
    ]
    assert len(exceptions) >= 2
    assert all(row["variance_reason_code"] for row in exceptions)


def test_experiment_controls_are_valid() -> None:
    design = yaml.safe_load(
        (CONFIG / "synthetic_design.yaml").read_text(encoding="utf-8")
    )
    allowed_periods = set(
        design["experiment_generation"]["allowed_limit_periods"]
    )

    controls = read_csv("experiment_controls.csv")
    assert len(controls) == 4

    for row in controls:
        assert row["spending_limit_period"] in allowed_periods
        assert row["limit_currency"] == "USD"
        assert float(row["spending_limit"]) > 0
        assert 0 < float(row["warning_threshold"]) < float(
            row["hard_stop_threshold"]
        ) <= 1
        assert parse_date(row["start_date"]) <= parse_date(row["planned_end_date"])


def test_experiment_decision_history_is_chronological_and_chained() -> None:
    design = yaml.safe_load(
        (CONFIG / "synthetic_design.yaml").read_text(encoding="utf-8")
    )
    allowed_decisions = set(
        design["experiment_generation"]["allowed_decisions"]
    )
    controls = {
        row["experiment_id"]: row for row in read_csv("experiment_controls.csv")
    }

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv("experiment_decisions.csv"):
        assert row["decision"] in allowed_decisions
        grouped[row["experiment_id"]].append(row)

    assert set(grouped) == set(controls)

    for experiment_id, rows in grouped.items():
        ordered = sorted(rows, key=lambda row: row["decision_date"])

        assert ordered[0]["previous_status"] == "planned"

        for previous, current in zip(ordered, ordered[1:]):
            assert parse_date(previous["decision_date"]) < parse_date(
                current["decision_date"]
            )
            assert current["previous_status"] == previous["new_status"]

        assert controls[experiment_id]["current_status"] == ordered[-1]["new_status"]
