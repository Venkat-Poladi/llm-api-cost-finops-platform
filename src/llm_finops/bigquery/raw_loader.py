from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import csv

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from llm_finops.bigquery.deployment_runner import (
    assert_controls_pass,
    evaluate_controls,
    insert_rows_or_raise,
    write_json_manifest,
    write_pipeline_success,
)
from llm_finops.bigquery.pipeline_logging import (
    current_pipeline_configuration,
    current_pipeline_datasets,
    current_pipeline_project_id,
    current_pipeline_run_id,
    current_pipeline_started_at,
    pipeline_run_guard,
    set_pipeline_loaded_table_count,
)


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

@pipeline_run_guard("M6_BIGQUERY_RAW_LAYER")
def execute_raw_load(
    *,
    project_root: Path,
    config_path: Path,
    project_id_override: str | None = None,
) -> dict[str, Any]:
    config = current_pipeline_configuration()
    project_id = current_pipeline_project_id()
    datasets = current_pipeline_datasets()
    location = config["location"]
    client = bigquery.Client(project=project_id)
    started_at = current_pipeline_started_at()
    pipeline_run_id = current_pipeline_run_id()

    for layer, dataset_name in datasets.items():
        ensure_dataset(client, dataset_name, location, layer)

    ensure_control_tables(client, datasets["control"])

    loaded_tables: list[dict[str, Any]] = []
    reconciliation_rows: list[dict[str, Any]] = []

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
                "table_id": f"{project_id}.{datasets['raw']}.{table_name}",
                "source_row_count": source_row_count,
                "bigquery_row_count": bigquery_row_count,
            }
        )
        set_pipeline_loaded_table_count(len(loaded_tables))

    insert_rows_or_raise(
        client=client,
        table_id=(
            f"{project_id}.{datasets['control']}.raw_load_reconciliation"
        ),
        rows=reconciliation_rows,
        error_message="Could not write raw-load reconciliation rows",
    )
    assert_controls_pass(
        reconciliation_rows,
        pipeline_name="M6_RAW_LOAD_RECONCILIATION",
    )

    control_rows = evaluate_controls(
        client=client,
        query_map=raw_control_queries(project_id, datasets["raw"]),
        location=location,
    )
    insert_rows_or_raise(
        client=client,
        table_id=(
            f"{project_id}.{datasets['control']}.raw_load_control_result"
        ),
        rows=control_rows,
        error_message="Could not write M6 control results",
    )
    assert_controls_pass(
        control_rows,
        pipeline_name="M6_BIGQUERY_RAW_LAYER",
    )

    completed_at = datetime.now(timezone.utc)
    manifest = {
        "pipeline_run_id": pipeline_run_id,
        "project_id": project_id,
        "location": location,
        "status": "PASS",
        "loaded_at": completed_at.isoformat(),
        "loaded_tables": loaded_tables,
        "controls": control_rows,
    }
    write_json_manifest(
        project_root=project_root,
        filename="m6_bigquery_manifest.json",
        manifest=manifest,
    )
    write_pipeline_success(
        client=client,
        project_id=project_id,
        control_dataset=datasets["control"],
        pipeline_name="M6_BIGQUERY_RAW_LAYER",
        started_at=started_at,
        completed_at=completed_at,
        loaded_table_count=len(loaded_tables),
    )

    return manifest
