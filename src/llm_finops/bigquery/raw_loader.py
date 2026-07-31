from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import csv
import json
import uuid

import yaml
from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from llm_finops.bigquery.identifiers import (
    validate_bigquery_identifiers,
)


def load_configuration(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing BigQuery configuration: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def count_csv_rows(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        next(reader)
        return sum(1 for _ in reader)


def build_schema(rows: list[list[str]]) -> list[bigquery.SchemaField]:
    return [
        bigquery.SchemaField(name, field_type, mode=mode)
        for name, field_type, mode in rows
    ]


def ensure_dataset(
    client: bigquery.Client,
    dataset_name: str,
    location: str,
    layer: str,
) -> None:
    dataset_id = f"{client.project}.{dataset_name}"

    try:
        existing = client.get_dataset(dataset_id)
    except NotFound:
        dataset = bigquery.Dataset(dataset_id)
        dataset.location = location
        dataset.labels = {
            "project": "llm-finops",
            "layer": layer,
        }
        client.create_dataset(dataset)
        return

    if existing.location.upper() != location.upper():
        raise ValueError(
            f"{dataset_id} is in {existing.location}; expected {location}."
        )


def ensure_control_tables(
    client: bigquery.Client,
    control_dataset: str,
) -> None:
    run_table = bigquery.Table(
        f"{client.project}.{control_dataset}.pipeline_run_log",
        schema=[
            bigquery.SchemaField("pipeline_run_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("pipeline_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("started_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("completed_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("loaded_table_count", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("error_message", "STRING", mode="NULLABLE"),
        ],
    )
    client.create_table(run_table, exists_ok=True)

    result_table = bigquery.Table(
        f"{client.project}.{control_dataset}.raw_load_control_result",
        schema=[
            bigquery.SchemaField("pipeline_run_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("control_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("violation_count", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("checked_at", "TIMESTAMP", mode="REQUIRED"),
        ],
    )
    client.create_table(result_table, exists_ok=True)

    reconciliation_table = bigquery.Table(
        f"{client.project}.{control_dataset}.raw_load_reconciliation",
        schema=[
            bigquery.SchemaField("pipeline_run_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("table_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("source_row_count", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("bigquery_row_count", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("row_count_difference", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("checked_at", "TIMESTAMP", mode="REQUIRED"),
        ],
    )
    client.create_table(reconciliation_table, exists_ok=True)


def load_csv_table(
    client: bigquery.Client,
    *,
    source_path: Path,
    table_name: str,
    raw_dataset: str,
    table_config: dict[str, Any],
    location: str,
) -> int:
    table_id = f"{client.project}.{raw_dataset}.{table_name}"

    client.delete_table(table_id, not_found_ok=True)

    job_config = bigquery.LoadJobConfig(
        schema=build_schema(table_config["schema"]),
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        allow_quoted_newlines=True,
        encoding="UTF-8",
        max_bad_records=0,
    )

    partition_field = table_config.get("partition_field")
    if partition_field:
        job_config.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field=partition_field,
        )

    clustering_fields = table_config.get("clustering_fields", [])
    if clustering_fields:
        job_config.clustering_fields = clustering_fields

    with source_path.open("rb") as handle:
        job = client.load_table_from_file(
            handle,
            table_id,
            job_config=job_config,
            location=location,
            size=source_path.stat().st_size,
            rewind=True,
        )
        job.result()

    table = client.get_table(table_id)
    return int(table.num_rows)


def run_query_count(
    client: bigquery.Client,
    sql: str,
    location: str,
) -> int:
    rows = list(client.query(sql, location=location).result())
    if len(rows) != 1:
        raise RuntimeError("A control query did not return exactly one row.")
    return int(rows[0]["violation_count"])


def raw_control_queries(project_id: str, raw_dataset: str) -> dict[str, str]:
    prefix = f"`{project_id}.{raw_dataset}"

    return {
        "usage_grain_unique": f"""
            SELECT
              COUNT(*) - COUNT(DISTINCT TO_JSON_STRING(STRUCT(
                usage_date, provider, usage_type, provider_project_id,
                api_key_id, model, provider_service_tier, is_batch,
                context_window_tier
              ))) AS violation_count
            FROM {prefix}.raw_ai_provider_usage`
        """,
        "cost_grain_unique": f"""
            SELECT
              COUNT(*) - COUNT(DISTINCT TO_JSON_STRING(STRUCT(
                billing_period, provider, provider_project_id, model,
                line_item_type, provider_line_item_id
              ))) AS violation_count
            FROM {prefix}.raw_ai_provider_cost`
        """,
        "telemetry_attempt_grain_unique": f"""
            SELECT
              COUNT(*) - COUNT(DISTINCT provider_request_id) AS violation_count
            FROM {prefix}.fct_ai_request_telemetry`
        """,
        "usage_reasoning_not_above_output": f"""
            SELECT COUNTIF(COALESCE(reasoning_tokens, 0) > output_tokens)
              AS violation_count
            FROM {prefix}.raw_ai_provider_usage`
        """,
        "telemetry_reasoning_not_above_output": f"""
            SELECT COUNTIF(reasoning_tokens > output_tokens) AS violation_count
            FROM {prefix}.fct_ai_request_telemetry`
        """,
        "openai_cached_input_not_above_input": f"""
            SELECT COUNTIF(
              provider = 'openai'
              AND COALESCE(cached_input_tokens, 0) > input_tokens
            ) AS violation_count
            FROM {prefix}.raw_ai_provider_usage`
        """,
        "allocation_not_above_100_percent": f"""
            SELECT COUNT(*) AS violation_count
            FROM (
              SELECT
                provider,
                provider_project_id,
                api_key_id,
                effective_start_date,
                effective_end_date,
                SUM(allocation_percentage) AS allocation_total
              FROM {prefix}.bridge_ai_usage_attribution`
              GROUP BY 1, 2, 3, 4, 5
              HAVING allocation_total > 1.000000001
            )
        """,
        "all_cost_records_are_usd": f"""
            SELECT COUNTIF(UPPER(billing_currency) != 'USD') AS violation_count
            FROM {prefix}.raw_ai_provider_cost`
        """,
        "all_experiment_limits_are_usd": f"""
            SELECT COUNTIF(UPPER(limit_currency) != 'USD') AS violation_count
            FROM {prefix}.dim_ai_experiment_control`
        """,
        "all_rows_are_marked_synthetic": f"""
            SELECT
              (
                SELECT COUNTIF(NOT is_synthetic)
                FROM {prefix}.raw_ai_provider_usage`
              )
              +
              (
                SELECT COUNTIF(NOT is_synthetic)
                FROM {prefix}.raw_ai_provider_cost`
              )
              +
              (
                SELECT COUNTIF(NOT is_synthetic)
                FROM {prefix}.fct_ai_request_telemetry`
              ) AS violation_count
        """,
    }


def execute_raw_load(
    *,
    project_root: Path,
    config_path: Path,
    project_id_override: str | None = None,
) -> dict[str, Any]:
    config = load_configuration(config_path)
    project_id = project_id_override or config["project_id"]
    location = config["location"]
    datasets = config["datasets"]

    validate_bigquery_identifiers(
        project_id,
        datasets,
        table_names=config.get("tables", {}).keys(),
    )

    client = bigquery.Client(project=project_id)
    started_at = datetime.now(timezone.utc)
    pipeline_run_id = str(uuid.uuid4())

    for layer, dataset_name in datasets.items():
        ensure_dataset(client, dataset_name, location, layer)

    ensure_control_tables(client, datasets["control"])

    loaded_tables: list[dict[str, Any]] = []
    reconciliation_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []

    try:
        for table_name, table_config in config["tables"].items():
            source_path = project_root / table_config["source_file"]
            if not source_path.exists():
                raise FileNotFoundError(
                    f"Source file is missing for {table_name}: {source_path}"
                )

            source_row_count = count_csv_rows(source_path)
            bigquery_row_count = load_csv_table(
                client,
                source_path=source_path,
                table_name=table_name,
                raw_dataset=datasets["raw"],
                table_config=table_config,
                location=location,
            )

            difference = bigquery_row_count - source_row_count
            status = "PASS" if difference == 0 else "FAIL"
            reconciliation_rows.append(
                {
                    "pipeline_run_id": pipeline_run_id,
                    "table_name": table_name,
                    "source_row_count": source_row_count,
                    "bigquery_row_count": bigquery_row_count,
                    "row_count_difference": difference,
                    "status": status,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            loaded_tables.append(
                {
                    "table_name": table_name,
                    "table_id": (
                        f"{project_id}.{datasets['raw']}.{table_name}"
                    ),
                    "source_row_count": source_row_count,
                    "bigquery_row_count": bigquery_row_count,
                }
            )

        reconciliation_errors = client.insert_rows_json(
            (
                f"{project_id}.{datasets['control']}."
                "raw_load_reconciliation"
            ),
            reconciliation_rows,
        )
        if reconciliation_errors:
            raise RuntimeError(
                f"Could not write reconciliation rows: {reconciliation_errors}"
            )

        failed_reconciliations = [
            row for row in reconciliation_rows if row["status"] != "PASS"
        ]
        if failed_reconciliations:
            raise RuntimeError(
                f"Row counts did not reconcile: {failed_reconciliations}"
            )

        for control_name, sql in raw_control_queries(
            project_id,
            datasets["raw"],
        ).items():
            violation_count = run_query_count(client, sql, location)
            status = "PASS" if violation_count == 0 else "FAIL"
            control_rows.append(
                {
                    "pipeline_run_id": pipeline_run_id,
                    "control_name": control_name,
                    "violation_count": violation_count,
                    "status": status,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        control_errors = client.insert_rows_json(
            (
                f"{project_id}.{datasets['control']}."
                "raw_load_control_result"
            ),
            control_rows,
        )
        if control_errors:
            raise RuntimeError(
                f"Could not write control results: {control_errors}"
            )

        failed_controls = [
            row for row in control_rows if row["status"] != "PASS"
        ]
        if failed_controls:
            raise RuntimeError(f"Raw controls failed: {failed_controls}")

        completed_at = datetime.now(timezone.utc)
        run_row = {
            "pipeline_run_id": pipeline_run_id,
            "pipeline_name": "M6_BIGQUERY_RAW_LAYER",
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "status": "PASS",
            "loaded_table_count": len(loaded_tables),
            "error_message": None,
        }
        run_errors = client.insert_rows_json(
            f"{project_id}.{datasets['control']}.pipeline_run_log",
            [run_row],
        )
        if run_errors:
            raise RuntimeError(f"Could not write run log: {run_errors}")

        manifest = {
            "pipeline_run_id": pipeline_run_id,
            "project_id": project_id,
            "location": location,
            "status": "PASS",
            "loaded_at": completed_at.isoformat(),
            "loaded_tables": loaded_tables,
            "controls": control_rows,
        }
        manifest_path = (
            project_root / "data" / "generated" / "m6_bigquery_manifest.json"
        )
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return manifest

    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        failure_row = {
            "pipeline_run_id": pipeline_run_id,
            "pipeline_name": "M6_BIGQUERY_RAW_LAYER",
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "status": "FAIL",
            "loaded_table_count": len(loaded_tables),
            "error_message": str(exc)[:1000],
        }
        client.insert_rows_json(
            f"{project_id}.{datasets['control']}.pipeline_run_log",
            [failure_row],
        )
        raise
