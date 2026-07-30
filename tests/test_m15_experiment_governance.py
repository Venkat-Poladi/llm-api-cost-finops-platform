from pathlib import Path

import yaml


CONFIG_PATH = Path("config/m15_bigquery.yaml")
DRIVER_SQL = Path(
    "sql/02_staging/07_experiment_invoice_driver_daily.sql"
)
MART_SQL = Path("sql/04_marts/06_experiments.sql")


def load_config() -> dict:
    assert CONFIG_PATH.exists(), "config/m15_bigquery.yaml is missing"
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_m15_uses_expected_project_and_financial_bases() -> None:
    config = load_config()

    assert config["project_id"] == "finops-learning-lab"
    assert config["location"] == "US"
    assert (
        config["financial_basis"]
        == "allocated_invoice_billed_cost_usage_lines_only"
    )
    assert (
        config["operational_basis"]
        == "request_telemetry_usage_cost_estimate"
    )


def test_m15_has_two_ordered_sql_files() -> None:
    assert load_config()["sql_files"] == [
        "sql/02_staging/07_experiment_invoice_driver_daily.sql",
        "sql/04_marts/06_experiments.sql",
    ]
    assert DRIVER_SQL.exists()
    assert MART_SQL.exists()


def test_experiment_driver_uses_only_tagged_valid_telemetry() -> None:
    sql = DRIVER_SQL.read_text(encoding="utf-8")

    assert "telemetry_validation_status = 'Valid'" in sql
    assert "experiment_id IS NOT NULL" in sql


def test_experiment_invoice_cost_uses_usage_lines_only() -> None:
    sql = DRIVER_SQL.read_text(encoding="utf-8")

    assert "WHERE line_item_type = 'usage'" in sql
    assert "allocated_invoice_billed_experiment_cost" in sql


def test_experiment_driver_uses_safe_financial_share() -> None:
    sql = DRIVER_SQL.read_text(encoding="utf-8")

    assert "SAFE_DIVIDE" in sql
    assert "financial_allocation_share" in sql


def test_experiment_mart_supports_all_limit_periods() -> None:
    sql = MART_SQL.read_text(encoding="utf-8")

    assert "spending_limit_period = 'day'" in sql
    assert "spending_limit_period = 'month'" in sql
    assert "spending_limit_period = 'lifetime'" in sql


def test_experiment_mart_generates_complete_calendar() -> None:
    sql = MART_SQL.read_text(encoding="utf-8")

    assert "GENERATE_DATE_ARRAY" in sql
    assert "COALESCE(SUM(d.allocated_invoice_billed_experiment_cost), 0)" in sql


def test_experiment_thresholds_and_actions_are_explicit() -> None:
    sql = MART_SQL.read_text(encoding="utf-8")

    assert "warning_spend_threshold" in sql
    assert "hard_stop_spend_threshold" in sql
    assert "HARD_STOP_ACTION_REQUIRED" in sql
    assert "WARNING_REVIEW_REQUIRED" in sql


def test_decision_financial_evidence_mismatch_is_audited() -> None:
    sql = MART_SQL.read_text(encoding="utf-8")

    assert "FINANCIAL_EVIDENCE_MISMATCH" in sql
    assert "governance_exception_reason" in sql
    assert "max_period_spend_to_date" in sql


def test_m15_runner_and_wrapper_exist() -> None:
    assert Path("scripts/run_m15.py").exists()
    assert Path("scripts/run_m15.ps1").exists()
