from pathlib import Path

import yaml


CONFIG_PATH = Path("config/bigquery_load.yaml")
EXPECTED_TABLES = {
    "raw_ai_provider_usage",
    "raw_ai_provider_cost",
    "fct_ai_request_telemetry",
    "bridge_ai_usage_attribution",
    "dim_ai_experiment_control",
    "fct_ai_experiment_decision",
    "dim_ai_model_map",
    "dim_ai_model_rate",
}


def load_config() -> dict:
    assert CONFIG_PATH.exists(), "config/bigquery_load.yaml is missing"
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_m6_has_all_five_datasets() -> None:
    assert set(load_config()["datasets"]) == {
        "raw",
        "staging",
        "core",
        "mart",
        "control",
    }


def test_m6_has_exactly_eight_raw_objects() -> None:
    assert set(load_config()["tables"]) == EXPECTED_TABLES


def test_every_m6_table_has_a_nonempty_unique_schema() -> None:
    for table_name, table in load_config()["tables"].items():
        schema = table["schema"]
        names = [field[0] for field in schema]

        assert schema, f"{table_name} has no schema"
        assert len(names) == len(set(names)), (
            f"{table_name} repeats a schema column"
        )


def test_partition_fields_exist_and_are_dates() -> None:
    for table_name, table in load_config()["tables"].items():
        partition_field = table["partition_field"]
        if partition_field is None:
            continue

        types = {name: field_type for name, field_type, _ in table["schema"]}
        assert partition_field in types, (
            f"{table_name} partition field is missing from the schema"
        )
        assert types[partition_field] == "DATE"


def test_clustering_fields_exist_and_do_not_exceed_four() -> None:
    for table_name, table in load_config()["tables"].items():
        clustering_fields = table["clustering_fields"]
        schema_fields = {field[0] for field in table["schema"]}

        assert len(clustering_fields) <= 4
        assert set(clustering_fields) <= schema_fields, (
            f"{table_name} has an invalid clustering field"
        )


def test_all_m6_source_paths_are_csv_files() -> None:
    for table in load_config()["tables"].values():
        assert table["source_file"].endswith(".csv")


def test_m6_uses_the_existing_bigquery_project_and_us_location() -> None:
    config = load_config()

    assert config["project_id"] == "finops-learning-lab"
    assert config["location"] == "US"
