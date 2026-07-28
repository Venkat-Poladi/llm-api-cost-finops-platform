from pathlib import Path

import yaml


CONFIG_PATH = Path("config/m12_bigquery.yaml")
DRIVER_SQL = Path(
    "sql/02_staging/06_application_invoice_driver_monthly.sql"
)
MART_SQL = Path("sql/04_marts/03_application_cost.sql")


def load_config() -> dict:
    assert CONFIG_PATH.exists(), "config/m12_bigquery.yaml is missing"
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_m12_uses_expected_project_and_invoice_basis() -> None:
    config = load_config()

    assert config["project_id"] == "finops-learning-lab"
    assert config["location"] == "US"
    assert config["financial_basis"] == "invoice_billed_cost"


def test_m12_has_two_ordered_sql_files() -> None:
    assert load_config()["sql_files"] == [
        "sql/02_staging/06_application_invoice_driver_monthly.sql",
        "sql/04_marts/03_application_cost.sql",
    ]
    assert DRIVER_SQL.exists()
    assert MART_SQL.exists()


def test_driver_aggregates_daily_usage_before_invoice_join() -> None:
    sql = DRIVER_SQL.read_text(encoding="utf-8")

    assert "DATE_TRUNC(usage_date, MONTH)" in sql
    assert "fct_ai_usage_daily" in sql
    assert "driver_usage_cost_estimate" in sql


def test_application_cost_joins_invoice_to_monthly_driver() -> None:
    sql = MART_SQL.read_text(encoding="utf-8")

    assert "stg_ai_application_invoice_driver_monthly" in sql
    assert "fct_ai_usage_daily" not in sql


def test_usage_allocation_uses_estimate_share_inside_scope() -> None:
    sql = MART_SQL.read_text(encoding="utf-8")

    assert "financial_allocation_share" in sql
    assert "SAFE_DIVIDE" in sql
    assert "eligible_driver_denominator" in sql


def test_zero_denominator_is_fully_unallocated() -> None:
    sql = MART_SQL.read_text(encoding="utf-8")

    assert "'no_eligible_driver' AS allocation_method" in sql
    assert "source_invoice_billed_cost AS unallocated_invoice_billed_cost" in sql


def test_non_usage_lines_remain_at_financial_scope() -> None:
    sql = MART_SQL.read_text(encoding="utf-8")

    assert "WHERE line_item_type != 'usage'" in sql
    assert "'Financial scope retained' AS allocation_status" in sql
    assert "'scope_retained' AS allocation_method" in sql


def test_source_allocated_and_unallocated_costs_are_separate() -> None:
    sql = MART_SQL.read_text(encoding="utf-8")

    required = [
        "source_invoice_billed_cost",
        "allocated_invoice_billed_cost",
        "unallocated_invoice_billed_cost",
        "source_provider_reported_cost",
        "allocated_provider_reported_cost",
        "unallocated_provider_reported_cost",
    ]
    for field in required:
        assert field in sql


def test_application_cost_preserves_confidence_and_restatement() -> None:
    sql = MART_SQL.read_text(encoding="utf-8")

    assert "allocation_confidence" in sql
    assert "is_historical_restatement" in sql


def test_m12_runner_and_wrapper_exist() -> None:
    assert Path("scripts/run_m12.py").exists()
    assert Path("scripts/run_m12.ps1").exists()
