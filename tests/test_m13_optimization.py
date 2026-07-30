from pathlib import Path

import yaml


CONFIG_PATH = Path("config/m13_bigquery.yaml")
OPTIMIZATION_SQL = Path("sql/04_marts/04_optimization.sql")


def load_config() -> dict:
    assert CONFIG_PATH.exists(), "config/m13_bigquery.yaml is missing"
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_m13_uses_expected_project_and_estimated_basis() -> None:
    config = load_config()

    assert config["project_id"] == "finops-learning-lab"
    assert config["location"] == "US"
    assert config["financial_basis"] == "usage_cost_estimate"


def test_m13_has_one_optimization_sql_file() -> None:
    assert load_config()["sql_files"] == [
        "sql/04_marts/04_optimization.sql"
    ]
    assert OPTIMIZATION_SQL.exists()


def test_retry_target_and_telemetry_gate_are_locked() -> None:
    policies = load_config()["policies"]

    assert policies["retry_reduction_target_pct"] == 0.50
    assert policies["telemetry_minimum_coverage_pct"] == 0.95
    assert policies["annualization_months"] == 12


def test_optimization_has_four_controlled_recommendation_types() -> None:
    sql = OPTIMIZATION_SQL.read_text(encoding="utf-8")

    required = [
        "BATCH_MIGRATION",
        "RETRY_REDUCTION",
        "TELEMETRY_COVERAGE",
        "CACHE_REUSE_ASSESSMENT",
    ]
    for recommendation_type in required:
        assert recommendation_type in sql


def test_retry_savings_are_modeled_at_50_percent() -> None:
    sql = OPTIMIZATION_SQL.read_text(encoding="utf-8")

    assert "estimated_retry_cost * 0.50 AS modeled_monthly_savings" in sql
    assert "Assumption-based model" in sql


def test_unquantified_recommendations_have_null_modeled_savings() -> None:
    sql = OPTIMIZATION_SQL.read_text(encoding="utf-8")

    assert sql.count("CAST(NULL AS NUMERIC) AS modeled_monthly_savings") == 2
    assert sql.count("'UNQUANTIFIED' AS savings_stage") == 2


def test_approval_implementation_and_realization_are_false() -> None:
    sql = OPTIMIZATION_SQL.read_text(encoding="utf-8")

    assert sql.count("FALSE AS is_approved") == 4
    assert sql.count("FALSE AS is_implemented") == 4
    assert sql.count("FALSE AS is_realized") == 4


def test_all_savings_stages_are_separate_columns() -> None:
    sql = OPTIMIZATION_SQL.read_text(encoding="utf-8")

    required = [
        "identified_annualized_savings",
        "approved_annualized_savings",
        "implemented_annualized_savings",
        "realized_savings",
    ]
    for field in required:
        assert field in sql


def test_evaluation_gate_statuses_are_explicit() -> None:
    sql = OPTIMIZATION_SQL.read_text(encoding="utf-8")

    assert "READY_FOR_EVALUATION" in sql
    assert "HOLD_FOR_DATA" in sql
    assert "REQUIRES_BENCHMARK" in sql


def test_m13_runner_and_wrapper_exist() -> None:
    assert Path("scripts/run_m13.py").exists()
    assert Path("scripts/run_m13.ps1").exists()
