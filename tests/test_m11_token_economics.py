from pathlib import Path

import yaml


CONFIG_PATH = Path("config/m11_bigquery.yaml")
TOKEN_SQL = Path("sql/04_marts/02_token_economics.sql")


def load_config() -> dict:
    assert CONFIG_PATH.exists(), "config/m11_bigquery.yaml is missing"
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_m11_uses_expected_project_and_location() -> None:
    config = load_config()

    assert config["project_id"] == "finops-learning-lab"
    assert config["location"] == "US"


def test_m11_has_one_token_economics_sql_file() -> None:
    assert load_config()["sql_files"] == [
        "sql/04_marts/02_token_economics.sql"
    ]
    assert TOKEN_SQL.exists()


def test_m11_financial_basis_is_estimated_cost() -> None:
    assert load_config()["financial_basis"] == "usage_cost_estimate"


def test_token_economics_uses_normalized_cache_metric() -> None:
    sql = TOKEN_SQL.read_text(encoding="utf-8")

    assert "normalized_cache_read_tokens" in sql
    assert "normalized_total_input_tokens" in sql
    assert "cache_read_share" in sql
    assert "SAFE_DIVIDE" in sql


def test_reasoning_tokens_are_not_added_to_total_tokens() -> None:
    sql = TOKEN_SQL.read_text(encoding="utf-8")

    assert "normalized_total_input_tokens + output_tokens" in sql
    assert "normalized_total_input_tokens + output_tokens + reasoning_tokens" not in sql


def test_reasoning_overhead_uses_output_denominator() -> None:
    sql = TOKEN_SQL.read_text(encoding="utf-8")

    assert "u.reasoning_tokens" in sql
    assert "u.output_tokens" in sql
    assert "reasoning_overhead_pct" in sql


def test_batch_opportunity_uses_matching_historical_batch_rate() -> None:
    sql = TOKEN_SQL.read_text(encoding="utf-8")

    assert "r.is_batch = TRUE" in sql
    assert "u.usage_date BETWEEN r.effective_start AND r.effective_end" in sql
    assert "batch_equivalent_cost_estimate" in sql


def test_failed_and_retry_costs_are_explicitly_estimated() -> None:
    sql = TOKEN_SQL.read_text(encoding="utf-8")

    assert "estimated_failed_attempt_cost" in sql
    assert "estimated_retry_cost" in sql
    assert "'Estimated from request telemetry' AS failure_cost_label" in sql


def test_zero_denominators_use_safe_division() -> None:
    sql = TOKEN_SQL.read_text(encoding="utf-8")

    assert sql.count("SAFE_DIVIDE") >= 7


def test_m11_runner_and_wrapper_exist() -> None:
    assert Path("scripts/run_m11.py").exists()
    assert Path("scripts/run_m11.ps1").exists()
