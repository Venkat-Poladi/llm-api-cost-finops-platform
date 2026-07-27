from pathlib import Path

import yaml


CONFIG_PATH = Path("config/m10_bigquery.yaml")
DAILY_SQL = Path("sql/03_core/04_telemetry_reconciliation_daily.sql")
MONTHLY_SQL = Path("sql/04_marts/01_telemetry_coverage_monthly.sql")


def load_config() -> dict:
    assert CONFIG_PATH.exists(), "config/m10_bigquery.yaml is missing"
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_m10_uses_expected_project_and_location() -> None:
    config = load_config()

    assert config["project_id"] == "finops-learning-lab"
    assert config["location"] == "US"


def test_m10_has_two_ordered_sql_files() -> None:
    sql_files = load_config()["sql_files"]

    assert sql_files == [
        "sql/03_core/04_telemetry_reconciliation_daily.sql",
        "sql/04_marts/01_telemetry_coverage_monthly.sql",
    ]


def test_every_m10_sql_file_exists() -> None:
    for relative_path in load_config()["sql_files"]:
        assert Path(relative_path).exists(), f"{relative_path} is missing"


def test_daily_reconciliation_uses_required_matching_grain() -> None:
    sql = DAILY_SQL.read_text(encoding="utf-8")

    for field in (
        "usage_date",
        "provider",
        "provider_project_id",
        "model",
    ):
        assert field in sql


def test_daily_reconciliation_keeps_attempt_and_logical_counts_separate() -> None:
    sql = DAILY_SQL.read_text(encoding="utf-8")

    assert "telemetry_attempt_count" in sql
    assert "telemetry_logical_request_count" in sql
    assert "telemetry_retry_attempt_count" in sql


def test_token_coverage_uses_safe_division() -> None:
    sql = DAILY_SQL.read_text(encoding="utf-8")

    assert "SAFE_DIVIDE" in sql
    assert "telemetry_token_coverage_pct" in sql


def test_untraceable_cost_is_bounded() -> None:
    sql = DAILY_SQL.read_text(encoding="utf-8")

    assert "untraceable_provider_usage_cost_estimate" in sql
    assert "GREATEST" in sql


def test_daily_reconciliation_uses_full_outer_join() -> None:
    sql = DAILY_SQL.read_text(encoding="utf-8")

    assert "FULL OUTER JOIN" in sql
    assert "NO_PROVIDER_USAGE" in sql
    assert "NO_TELEMETRY" in sql


def test_monthly_coverage_is_weighted_from_summed_tokens() -> None:
    sql = MONTHLY_SQL.read_text(encoding="utf-8")

    assert "SUM(telemetry_total_tokens)" in sql
    assert "SUM(provider_total_tokens)" in sql
    assert "AVG(telemetry_token_coverage_pct)" not in sql


def test_m10_runner_and_wrapper_exist() -> None:
    assert Path("scripts/run_m10.py").exists()
    assert Path("scripts/run_m10.ps1").exists()
