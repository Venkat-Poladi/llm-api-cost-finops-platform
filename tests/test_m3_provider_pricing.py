from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path
import csv
import json

import yaml


CONFIG = Path("config")


def read_csv(name: str) -> list[dict[str, str]]:
    path = CONFIG / name
    assert path.exists(), f"{path} is missing"
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def test_focus_version_is_pinned_to_1_4() -> None:
    config = yaml.safe_load((CONFIG / "focus_version.yaml").read_text(encoding="utf-8"))
    assert config["focus_version"] == "1.4"
    assert config["status"] == "published"


def test_usage_type_is_part_of_required_grains() -> None:
    contracts = yaml.safe_load((CONFIG / "table_contracts.yaml").read_text(encoding="utf-8"))
    tables = contracts["tables"]

    for table_name in (
        "raw_ai_provider_usage",
        "dim_ai_model_map",
        "dim_ai_model_rate",
        "fct_ai_usage_daily",
    ):
        assert "usage_type" in tables[table_name]["grain"], (
            f"{table_name} must include usage_type in its grain"
        )


def test_model_map_rows_are_unique() -> None:
    rows = read_csv("model_map.csv")
    key_columns = (
        "provider",
        "usage_type",
        "provider_model_name",
        "model_snapshot",
        "effective_start",
        "effective_end",
    )
    keys = [tuple(row[column] for column in key_columns) for row in rows]
    assert len(keys) == len(set(keys))


def test_model_map_windows_do_not_overlap() -> None:
    rows = read_csv("model_map.csv")
    grouped: dict[tuple[str, str, str], list[tuple[date, date]]] = defaultdict(list)

    for row in rows:
        group = (row["provider"], row["usage_type"], row["provider_model_name"])
        grouped[group].append(
            (parse_date(row["effective_start"]), parse_date(row["effective_end"]))
        )

    for group, windows in grouped.items():
        ordered = sorted(windows)
        for previous, current in zip(ordered, ordered[1:]):
            assert current[0] > previous[1], f"Overlapping model-map windows for {group}"


def test_rate_rows_are_unique() -> None:
    rows = read_csv("model_rates.csv")
    key_columns = (
        "provider",
        "usage_type",
        "model_snapshot",
        "normalized_processing_tier",
        "is_batch",
        "context_window_tier",
        "effective_start",
        "effective_end",
    )
    keys = [tuple(row[column] for column in key_columns) for row in rows]
    assert len(keys) == len(set(keys))


def test_rate_windows_do_not_overlap() -> None:
    rows = read_csv("model_rates.csv")
    grouped: dict[tuple[str, ...], list[tuple[date, date]]] = defaultdict(list)

    group_columns = (
        "provider",
        "usage_type",
        "model_snapshot",
        "normalized_processing_tier",
        "is_batch",
        "context_window_tier",
    )

    for row in rows:
        group = tuple(row[column] for column in group_columns)
        grouped[group].append(
            (parse_date(row["effective_start"]), parse_date(row["effective_end"]))
        )

    for group, windows in grouped.items():
        ordered = sorted(windows)
        for previous, current in zip(ordered, ordered[1:]):
            assert current[0] > previous[1], f"Overlapping rate windows for {group}"


def test_all_rate_rows_are_usd() -> None:
    assert {row["rate_currency"] for row in read_csv("model_rates.csv")} == {"USD"}


def test_every_model_snapshot_has_a_standard_nonbatch_rate() -> None:
    model_rows = read_csv("model_map.csv")
    rate_rows = read_csv("model_rates.csv")

    available = {
        (row["provider"], row["usage_type"], row["model_snapshot"])
        for row in rate_rows
        if row["normalized_processing_tier"] == "standard"
        and row["is_batch"] == "false"
        and row["context_window_tier"] == "standard"
    }

    for row in model_rows:
        key = (row["provider"], row["usage_type"], row["model_snapshot"])
        assert key in available, f"No standard nonbatch rate for {key}"


def test_embeddings_are_openai_only_in_v1() -> None:
    embedding_providers = {
        row["provider"]
        for row in read_csv("model_map.csv")
        if row["usage_type"] == "embedding"
    }
    assert embedding_providers == {"openai"}


def test_only_selected_reasoning_model_is_marked_capable() -> None:
    rows = read_csv("model_map.csv")
    reasoning_models = {
        row["model_snapshot"]
        for row in rows
        if row["reasoning_capable"] == "true"
    }
    assert reasoning_models == {"gpt-5-2025-08-07"}


def test_batch_rows_have_no_cache_rates_in_v1() -> None:
    for row in read_csv("model_rates.csv"):
        if row["is_batch"] == "true":
            assert row["cached_input_rate_per_million"] == ""
            assert row["cache_write_5m_rate_per_million"] == ""
            assert row["cache_write_1h_rate_per_million"] == ""


def test_provider_field_map_uses_verified_openai_cache_names() -> None:
    config = yaml.safe_load(
        (CONFIG / "provider_field_map.yaml").read_text(encoding="utf-8")
    )
    openai = config["providers"]["openai"]

    assert (
        openai["usage_sources"]["text_generation"]["cached_input_tokens"]
        == "input_cached_tokens"
    )
    assert (
        openai["request_telemetry"]["cached_input_tokens"]
        == "usage.input_tokens_details.cached_tokens"
    )


def test_evidence_examples_are_valid_json() -> None:
    evidence_dir = Path("evidence")
    files = sorted(evidence_dir.glob("*.example.json"))
    assert len(files) == 4

    for path in files:
        json.loads(path.read_text(encoding="utf-8"))
