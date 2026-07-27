from pathlib import Path

import yaml


CONFIG_PATH = Path("config/m9_bigquery.yaml")
ALLOCATION_SQL = Path("sql/03_core/03_usage_daily_allocation.sql")


def load_config() -> dict:
    assert CONFIG_PATH.exists(), "config/m9_bigquery.yaml is missing"
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_m9_uses_expected_project_and_location() -> None:
    config = load_config()

    assert config["project_id"] == "finops-learning-lab"
    assert config["location"] == "US"


def test_m9_has_one_allocation_sql_file() -> None:
    sql_files = load_config()["sql_files"]

    assert sql_files == ["sql/03_core/03_usage_daily_allocation.sql"]
    assert ALLOCATION_SQL.exists()


def test_m9_creates_the_daily_usage_fact() -> None:
    assert load_config()["expected_objects"] == [
        "llm_finops_core.fct_ai_usage_daily"
    ]


def test_allocation_sql_creates_explicit_unallocated_rows() -> None:
    sql = ALLOCATION_SQL.read_text(encoding="utf-8")

    assert "'Unallocated' AS application_name" in sql
    assert "'UNALLOCATED' AS cost_center" in sql
    assert "'unallocated_residual'" in sql
    assert "'no_mapping'" in sql


def test_allocation_sql_uses_effective_dated_mapping() -> None:
    sql = ALLOCATION_SQL.read_text(encoding="utf-8")

    assert "u.usage_date BETWEEN" in sql
    assert "b.effective_start_date AND b.effective_end_date" in sql


def test_allocation_sql_has_a_single_source_measure_anchor() -> None:
    sql = ALLOCATION_SQL.read_text(encoding="utf-8")

    assert "source_measure_anchor_number" in sql
    assert "source_measure_anchor_flag" in sql
    assert "IF(source_measure_anchor_number = 1" in sql


def test_allocation_sql_keeps_source_allocated_and_unallocated_cost() -> None:
    sql = ALLOCATION_SQL.read_text(encoding="utf-8")

    assert "source_usage_cost_estimate" in sql
    assert "allocated_usage_cost_estimate" in sql
    assert "unallocated_usage_cost_estimate" in sql


def test_allocation_sql_splits_every_additive_measure() -> None:
    sql = ALLOCATION_SQL.read_text(encoding="utf-8")

    required = [
        "allocated_request_count",
        "allocated_total_input_tokens",
        "allocated_output_tokens",
        "allocated_reasoning_tokens",
        "unallocated_request_count",
        "unallocated_total_input_tokens",
        "unallocated_output_tokens",
        "unallocated_reasoning_tokens",
    ]
    for column in required:
        assert column in sql


def test_allocation_sql_flags_historical_restatements() -> None:
    sql = ALLOCATION_SQL.read_text(encoding="utf-8")

    assert "is_historical_restatement" in sql
    assert "mapping_recorded_date > b.effective_start_date" in sql


def test_m9_runner_and_wrapper_exist() -> None:
    assert Path("scripts/run_m9.py").exists()
    assert Path("scripts/run_m9.ps1").exists()
