from pathlib import Path

import yaml


CONFIG_PATH = Path("config/m8_bigquery.yaml")
MONTHLY_SQL = Path("sql/03_core/01_monthly_usage_cost.sql")
FACT_SQL = Path("sql/03_core/02_cost_reconciliation.sql")


def load_config() -> dict:
    assert CONFIG_PATH.exists(), "config/m8_bigquery.yaml is missing"
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_m8_uses_expected_project_and_location() -> None:
    config = load_config()

    assert config["project_id"] == "finops-learning-lab"
    assert config["location"] == "US"


def test_m8_has_two_ordered_sql_files() -> None:
    sql_files = load_config()["sql_files"]

    assert len(sql_files) == 2
    assert sql_files[0].endswith("01_monthly_usage_cost.sql")
    assert sql_files[1].endswith("02_cost_reconciliation.sql")


def test_every_m8_sql_file_exists() -> None:
    for relative_path in load_config()["sql_files"]:
        assert Path(relative_path).exists(), f"{relative_path} is missing"


def test_monthly_rollup_aggregates_daily_estimates() -> None:
    sql = MONTHLY_SQL.read_text(encoding="utf-8")

    assert "DATE_TRUNC(usage_date, MONTH)" in sql
    assert "SUM(usage_cost_estimate)" in sql
    assert "stg_ai_provider_usage_priced" in sql


def test_reconciliation_preserves_provider_line_item_id() -> None:
    sql = FACT_SQL.read_text(encoding="utf-8")

    assert "provider_line_item_id" in sql
    assert "reconciliation_fact_id" in sql


def test_reconciliation_has_two_separate_variances() -> None:
    sql = FACT_SQL.read_text(encoding="utf-8")

    assert "usage_to_reported_variance" in sql
    assert "reported_to_invoice_variance" in sql
    assert "usage_to_reported_variance_pct" in sql
    assert "reported_to_invoice_variance_pct" in sql


def test_non_usage_lines_do_not_receive_usage_estimates() -> None:
    sql = FACT_SQL.read_text(encoding="utf-8")

    assert "IF(c.line_item_type = 'usage', u.usage_cost_estimate, NULL)" in sql
    assert "WHEN line_item_type != 'usage' THEN 'NOT_APPLICABLE'" in sql


def test_m8_uses_safe_division_and_locked_tolerance() -> None:
    sql = FACT_SQL.read_text(encoding="utf-8")
    tolerance = load_config()["tolerance"]

    assert "SAFE_DIVIDE" in sql
    assert tolerance["absolute_usd"] == 1.0
    assert tolerance["relative_pct"] == 0.01


def test_large_independent_source_difference_is_not_called_rounding() -> None:
    sql = FACT_SQL.read_text(encoding="utf-8")

    assert "INDEPENDENT_SOURCE_ESTIMATE_DIFFERENCE" in sql


def test_m8_runner_and_wrapper_exist() -> None:
    assert Path("scripts/run_m8.py").exists()
    assert Path("scripts/run_m8.ps1").exists()
