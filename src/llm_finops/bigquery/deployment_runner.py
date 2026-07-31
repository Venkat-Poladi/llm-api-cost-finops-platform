from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable
import json

import yaml
from google.cloud import bigquery

from llm_finops.bigquery.pipeline_logging import (
    current_pipeline_configuration,
    current_pipeline_datasets,
    current_pipeline_project_id,
    current_pipeline_run_id,
    current_pipeline_started_at,
    set_pipeline_loaded_table_count,
)


ControlQueryFactory = Callable[[str, dict[str, str]], dict[str, str]]
SummaryBuilder = Callable[
    [bigquery.Client, str, str, str],
    dict[str, Any],
]


@dataclass(frozen=True)
class SqlPipelineSpec:
    pipeline_name: str
    control_table: str
    manifest_filename: str
    summary_dataset_layer: str | None = None


def load_yaml_document(path: Path, *, label: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")

    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"{label} must be a YAML mapping.")

    return document


def render_sql_template(
    path: Path,
    project_id: str,
    datasets: dict[str, str],
) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing SQL file: {path}")

    replacements = {"{{PROJECT_ID}}": project_id}
    replacements.update(
        {
            f"{{{{{layer.upper()}_DATASET}}}}": dataset_id
            for layer, dataset_id in datasets.items()
        }
    )

    sql = path.read_text(encoding="utf-8")
    for placeholder, value in replacements.items():
        sql = sql.replace(placeholder, value)

    return sql


def render_object_name(
    object_name: str,
    datasets: dict[str, str],
) -> str:
    rendered = object_name
    for layer, dataset_id in datasets.items():
        rendered = rendered.replace(
            f"{{{{{layer.upper()}_DATASET}}}}",
            dataset_id,
        )
    return rendered


def query_scalar(
    client: bigquery.Client,
    sql: str,
    location: str,
) -> int:
    rows = list(client.query(sql, location=location).result())
    if len(rows) != 1:
        raise RuntimeError("Control query did not return exactly one row.")
    return int(rows[0]["violation_count"])


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def execute_sql_files(
    *,
    client: bigquery.Client,
    project_root: Path,
    relative_paths: list[str],
    project_id: str,
    datasets: dict[str, str],
    location: str,
) -> None:
    for relative_path in relative_paths:
        sql = render_sql_template(
            project_root / relative_path,
            project_id,
            datasets,
        )
        client.query(sql, location=location).result()


def ensure_standard_control_table(
    *,
    client: bigquery.Client,
    project_id: str,
    control_dataset: str,
    table_name: str,
    control_key: str = "control_name",
) -> None:
    table = bigquery.Table(
        f"{project_id}.{control_dataset}.{table_name}",
        schema=[
            bigquery.SchemaField("pipeline_run_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField(control_key, "STRING", mode="REQUIRED"),
            bigquery.SchemaField("violation_count", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("checked_at", "TIMESTAMP", mode="REQUIRED"),
        ],
    )
    client.create_table(table, exists_ok=True)


def evaluate_controls(
    *,
    client: bigquery.Client,
    query_map: dict[str, str],
    location: str,
    control_key: str = "control_name",
) -> list[dict[str, Any]]:
    checked_at = datetime.now(timezone.utc).isoformat()
    pipeline_run_id = current_pipeline_run_id()
    rows: list[dict[str, Any]] = []

    for control_name, sql in query_map.items():
        violation_count = query_scalar(client, sql, location)
        rows.append(
            {
                "pipeline_run_id": pipeline_run_id,
                control_key: control_name,
                "violation_count": violation_count,
                "status": "PASS" if violation_count == 0 else "FAIL",
                "checked_at": checked_at,
            }
        )

    return rows


def insert_rows_or_raise(
    *,
    client: bigquery.Client,
    table_id: str,
    rows: list[dict[str, Any]],
    error_message: str,
) -> None:
    errors = client.insert_rows_json(table_id, rows)
    if errors:
        raise RuntimeError(f"{error_message}: {errors}")


def assert_controls_pass(
    rows: list[dict[str, Any]],
    *,
    pipeline_name: str,
) -> None:
    failed = [row for row in rows if row["status"] != "PASS"]
    if failed:
        raise RuntimeError(f"{pipeline_name} controls failed: {failed}")


def write_json_manifest(
    *,
    project_root: Path,
    filename: str,
    manifest: dict[str, Any],
) -> None:
    manifest_path = project_root / "data" / "generated" / filename
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_pipeline_success(
    *,
    client: bigquery.Client,
    project_id: str,
    control_dataset: str,
    pipeline_name: str,
    started_at: datetime,
    completed_at: datetime,
    loaded_table_count: int,
) -> None:
    set_pipeline_loaded_table_count(loaded_table_count)
    insert_rows_or_raise(
        client=client,
        table_id=f"{project_id}.{control_dataset}.pipeline_run_log",
        rows=[
            {
                "pipeline_run_id": current_pipeline_run_id(),
                "pipeline_name": pipeline_name,
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "status": "PASS",
                "loaded_table_count": loaded_table_count,
                "error_message": None,
            }
        ],
        error_message=f"Could not write {pipeline_name} pipeline log",
    )


def run_sql_pipeline(
    *,
    project_root: Path,
    spec: SqlPipelineSpec,
    control_query_factory: ControlQueryFactory,
    summary_builder: SummaryBuilder | None = None,
) -> dict[str, Any]:
    config = current_pipeline_configuration()
    project_id = current_pipeline_project_id()
    datasets = current_pipeline_datasets()
    location = config["location"]
    client = bigquery.Client(project=project_id)
    started_at = current_pipeline_started_at()

    execute_sql_files(
        client=client,
        project_root=project_root,
        relative_paths=config["sql_files"],
        project_id=project_id,
        datasets=datasets,
        location=location,
    )

    created_objects = [
        render_object_name(object_name, datasets)
        for object_name in config["expected_objects"]
    ]
    set_pipeline_loaded_table_count(len(created_objects))

    ensure_standard_control_table(
        client=client,
        project_id=project_id,
        control_dataset=datasets["control"],
        table_name=spec.control_table,
    )

    control_rows = evaluate_controls(
        client=client,
        query_map=control_query_factory(project_id, datasets),
        location=location,
    )
    insert_rows_or_raise(
        client=client,
        table_id=(
            f"{project_id}.{datasets['control']}.{spec.control_table}"
        ),
        rows=control_rows,
        error_message=f"Could not write {spec.pipeline_name} controls",
    )
    assert_controls_pass(control_rows, pipeline_name=spec.pipeline_name)

    summary = None
    if summary_builder is not None:
        if spec.summary_dataset_layer is None:
            raise ValueError(
                "A summary dataset layer is required when a summary builder is set."
            )
        summary = summary_builder(
            client,
            project_id,
            datasets[spec.summary_dataset_layer],
            location,
        )

    completed_at = datetime.now(timezone.utc)
    manifest: dict[str, Any] = {
        "pipeline_run_id": current_pipeline_run_id(),
        "pipeline_name": spec.pipeline_name,
        "project_id": project_id,
        "location": location,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "status": "PASS",
        "created_objects": created_objects,
        "controls": control_rows,
    }
    if summary is not None:
        manifest["summary"] = summary

    write_json_manifest(
        project_root=project_root,
        filename=spec.manifest_filename,
        manifest=manifest,
    )
    write_pipeline_success(
        client=client,
        project_id=project_id,
        control_dataset=datasets["control"],
        pipeline_name=spec.pipeline_name,
        started_at=started_at,
        completed_at=completed_at,
        loaded_table_count=len(created_objects),
    )

    return manifest
