from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from llm_finops.bigquery.identifiers import (
    validate_bigquery_identifiers,
    validate_dataset_id,
    validate_project_id,
    validate_table_id,
)


def test_valid_repository_identifiers_are_accepted() -> None:
    validate_bigquery_identifiers(
        "finops-learning-lab",
        {
            "raw": "llm_finops_raw",
            "staging": "llm_finops_staging",
            "core": "llm_finops_core",
            "mart": "llm_finops_mart",
            "control": "llm_finops_control",
        },
        table_names=[
            "raw_ai_provider_usage",
            "pipeline_run_log",
        ],
    )


@pytest.mark.parametrize(
    "project_id",
    [
        "UPPERCASE-project",
        "project_with_underscore",
        "-leading-hyphen",
        "trailing-hyphen-",
        "short",
        "project`; DROP TABLE x; --",
        "",
    ],
)
def test_unsafe_project_ids_are_rejected(
    project_id: str,
) -> None:
    with pytest.raises(ValueError, match="Unsafe BigQuery project ID"):
        validate_project_id(project_id)


@pytest.mark.parametrize(
    "dataset_id",
    [
        "dataset-with-hyphen",
        "dataset.name",
        "dataset`",
        "dataset name",
        "",
    ],
)
def test_unsafe_dataset_ids_are_rejected(
    dataset_id: str,
) -> None:
    with pytest.raises(ValueError, match="Unsafe BigQuery dataset"):
        validate_dataset_id(dataset_id)


@pytest.mark.parametrize(
    "table_id",
    [
        "table-with-hyphen",
        "table.name",
        "table`",
        "table name",
        "",
    ],
)
def test_unsafe_table_ids_are_rejected(
    table_id: str,
) -> None:
    with pytest.raises(ValueError, match="Unsafe BigQuery table"):
        validate_table_id(table_id)


def test_all_bigquery_configs_use_safe_identifiers() -> None:
    project_root = Path(__file__).parents[1]
    config_paths = sorted(
        (project_root / "config").glob("*bigquery*.yaml")
    )

    assert config_paths

    for config_path in config_paths:
        config = yaml.safe_load(
            config_path.read_text(encoding="utf-8")
        )

        validate_bigquery_identifiers(
            config["project_id"],
            config["datasets"],
            table_names=config.get("tables", {}).keys(),
        )


def test_m6_and_shared_guard_call_identifier_validation() -> None:
    source_root = (
        Path(__file__).parents[1]
        / "src"
        / "llm_finops"
        / "bigquery"
    )

    raw_loader = (source_root / "raw_loader.py").read_text(
        encoding="utf-8"
    )
    pipeline_logging = (
        source_root / "pipeline_logging.py"
    ).read_text(encoding="utf-8")

    assert "validate_bigquery_identifiers(" in raw_loader
    assert "table_names=config.get(" in raw_loader
    assert "validate_bigquery_identifiers(" in pipeline_logging
