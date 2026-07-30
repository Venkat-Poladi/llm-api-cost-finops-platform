from pathlib import Path

import yaml


CONFIG_PATH = Path("config/m14_bigquery.yaml")
UNIT_SQL = Path("sql/04_marts/05_unit_economics.sql")


def load_config() -> dict:
    assert CONFIG_PATH.exists(), "config/m14_bigquery.yaml is missing"
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_m14_uses_expected_project_and_financial_bases() -> None:
    config = load_config()

    assert config["project_id"] == "finops-learning-lab"
    assert config["location"] == "US"
    assert config["financial_basis"] == "invoice_billed_cost_usage_lines"
    assert config["operational_basis"] == "usage_cost_estimate"


def test_m14_has_one_unit_economics_sql_file() -> None:
    assert load_config()["sql_files"] == [
        "sql/04_marts/05_unit_economics.sql"
    ]
    assert UNIT_SQL.exists()


def test_m14_telemetry_quality_gate_is_locked() -> None:
    gate = load_config()["telemetry_quality_gate"]

    assert gate["minimum_token_coverage_pct"] == 0.95
    assert gate["maximum_token_coverage_pct"] == 1.05


def test_unit_economics_uses_usage_invoice_lines_only() -> None:
    sql = UNIT_SQL.read_text(encoding="utf-8")

    assert "WHERE line_item_type = 'usage'" in sql
    assert "invoice_billed_usage_cost" in sql


def test_provider_unit_costs_use_safe_division() -> None:
    sql = UNIT_SQL.read_text(encoding="utf-8")

    assert "invoice_cost_per_provider_request" in sql
    assert "invoice_cost_per_million_total_tokens" in sql
    assert sql.count("SAFE_DIVIDE") >= 15


def test_telemetry_dependent_costs_are_governed() -> None:
    sql = UNIT_SQL.read_text(encoding="utf-8")

    assert "telemetry_quality_gate_passed" in sql
    assert "governed_invoice_cost_per_logical_request" in sql
    assert "governed_invoice_cost_per_successful_request" in sql
    assert "ELSE NULL" in sql


def test_measurement_quality_statuses_are_explicit() -> None:
    sql = UNIT_SQL.read_text(encoding="utf-8")

    assert "'SUFFICIENT'" in sql
    assert "'INSUFFICIENT'" in sql
    assert "'PUBLISHABLE'" in sql
    assert "'LIMITED_TELEMETRY'" in sql


def test_request_attempt_and_success_metrics_remain_separate() -> None:
    sql = UNIT_SQL.read_text(encoding="utf-8")

    required = [
        "telemetry_attempt_count",
        "telemetry_logical_request_count",
        "successful_logical_request_count",
        "observed_retry_attempt_rate",
        "observed_failed_attempt_rate",
    ]
    for field in required:
        assert field in sql


def test_retry_and_failure_costs_are_labeled_estimates() -> None:
    sql = UNIT_SQL.read_text(encoding="utf-8")

    assert "estimated_retry_cost" in sql
    assert "estimated_failed_attempt_cost" in sql
    assert "'Estimated from request telemetry'" in sql


def test_m14_runner_and_wrapper_exist() -> None:
    assert Path("scripts/run_m14.py").exists()
    assert Path("scripts/run_m14.ps1").exists()
