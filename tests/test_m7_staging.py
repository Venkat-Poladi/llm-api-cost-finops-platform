from pathlib import Path

import yaml


CONFIG_PATH = Path("config/m7_bigquery.yaml")


def load_config() -> dict:
    assert CONFIG_PATH.exists(), "config/m7_bigquery.yaml is missing"
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_m7_uses_expected_bigquery_project_and_location() -> None:
    config = load_config()

    assert config["project_id"] == "finops-learning-lab"
    assert config["location"] == "US"


def test_m7_has_five_ordered_sql_files() -> None:
    sql_files = load_config()["sql_files"]

    assert len(sql_files) == 5
    assert sql_files[0].endswith("01_service_tier_map.sql")
    assert sql_files[-1].endswith("05_request_telemetry.sql")


def test_every_m7_sql_file_exists() -> None:
    for relative_path in load_config()["sql_files"]:
        assert Path(relative_path).exists(), f"{relative_path} is missing"


def test_m7_expected_objects_are_unique() -> None:
    objects = load_config()["expected_objects"]

    assert len(objects) == 5
    assert len(objects) == len(set(objects))


def test_usage_normalization_sql_contains_provider_specific_logic() -> None:
    sql = Path(
        "sql/02_staging/02_usage_normalized.sql"
    ).read_text(encoding="utf-8")

    assert "provider = 'openai'" in sql
    assert "provider = 'anthropic'" in sql
    assert "normalized_total_input_tokens" in sql
    assert "visible_output_tokens" in sql


def test_usage_pricing_sql_does_not_bill_reasoning_twice() -> None:
    sql = Path(
        "sql/02_staging/03_usage_priced.sql"
    ).read_text(encoding="utf-8")

    assert "reasoning_tokens *" not in sql
    assert "output_tokens" in sql
    assert "usage_cost_estimate" in sql


def test_usage_pricing_uses_effective_dated_rate_window() -> None:
    sql = Path(
        "sql/02_staging/03_usage_priced.sql"
    ).read_text(encoding="utf-8")

    assert "usage_date BETWEEN r.effective_start AND r.effective_end" in sql


def test_m7_runner_and_powershell_wrapper_exist() -> None:
    assert Path("scripts/run_m7.py").exists()
    assert Path("scripts/run_m7.ps1").exists()
