from pathlib import Path
import csv

import yaml


CONFIG_PATH = Path("config/m17_bigquery.yaml")
RELATIONSHIPS_PATH = Path("powerbi/semantic_model/relationships.csv")
MEASURES_PATH = Path("powerbi/semantic_model/measures.dax")


def load_config() -> dict:
    assert CONFIG_PATH.exists(), "config/m17_bigquery.yaml is missing"
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_m17_creates_five_dimensions_and_five_facts() -> None:
    objects = load_config()["expected_objects"]

    assert len(objects) == 10
    assert sum(name.startswith("dim_") for name in objects) == 5
    assert sum(name.startswith("fact_") for name in objects) == 5


def test_every_m17_sql_file_exists() -> None:
    for relative_path in load_config()["sql_files"]:
        assert Path(relative_path).exists(), f"{relative_path} is missing"


def test_relationships_are_one_to_many_single_direction() -> None:
    with RELATIONSHIPS_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    assert all(row["cardinality"] == "1:*" for row in rows)
    assert all(row["cross_filter_direction"] == "Single" for row in rows)
    assert all(row["status"] == "Active" for row in rows)


def test_relationships_do_not_link_fact_to_fact() -> None:
    with RELATIONSHIPS_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    for row in rows:
        assert row["from_table"].startswith("dim_")
        assert row["to_table"].startswith("fact_")


def test_relationship_definitions_are_unique() -> None:
    with RELATIONSHIPS_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    keys = [
        (
            row["from_table"],
            row["from_column"],
            row["to_table"],
            row["to_column"],
        )
        for row in rows
    ]
    assert len(keys) == len(set(keys))


def test_measures_use_explicit_divide_for_ratios() -> None:
    dax = MEASURES_PATH.read_text(encoding="utf-8")

    required = [
        "Allocation Coverage %",
        "Invoice vs Estimate Variance %",
        "Cache Read Share",
        "Batch Adoption %",
        "Invoice Cost per Provider Request",
        "Invoice Cost per Million Tokens",
        "Control Pass %",
    ]
    for measure in required:
        assert measure in dax

    assert "DIVIDE(" in dax


def test_savings_stages_remain_separate_measures() -> None:
    dax = MEASURES_PATH.read_text(encoding="utf-8")

    required = [
        "Identified Annualized Savings",
        "Approved Annualized Savings",
        "Implemented Annualized Savings",
        "Realized Savings",
    ]
    for measure in required:
        assert measure in dax


def test_semantic_rules_prohibit_fact_relationships() -> None:
    rules = load_config()["semantic_rules"]

    assert rules["fact_to_fact_relationships"] == "prohibited"
    assert rules["relationship_direction"] == "single"
    assert rules["explicit_measures_only"] is True


def test_m17_powerbi_support_files_exist() -> None:
    required = [
        "powerbi/semantic_model/relationships.csv",
        "powerbi/semantic_model/measures.dax",
        "powerbi/semantic_model/measure_formatting.csv",
        "powerbi/semantic_model/hidden_columns.csv",
    ]
    for relative_path in required:
        assert Path(relative_path).exists()


def test_m17_runner_and_wrapper_exist() -> None:
    assert Path("scripts/run_m17.py").exists()
    assert Path("scripts/run_m17.ps1").exists()
