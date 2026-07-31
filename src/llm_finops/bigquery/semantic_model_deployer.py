from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json

import yaml
from google.cloud import bigquery

from llm_finops.bigquery.pipeline_logging import (
    current_pipeline_run_id,
    current_pipeline_started_at,
    pipeline_run_guard,
)


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing M17 configuration: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def render_sql(
    path: Path,
    project_id: str,
    datasets: dict[str, str],
) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing SQL file: {path}")

    replacements = {
        "{{PROJECT_ID}}": project_id,
        "{{RAW_DATASET}}": datasets["raw"],
        "{{MART_DATASET}}": datasets["mart"],
    }

    sql = path.read_text(encoding="utf-8")

    for placeholder, value in replacements.items():
        sql = sql.replace(placeholder, value)

    return sql


def query_scalar(
    client: bigquery.Client,
    sql: str,
    location: str,
) -> int:
    rows = list(client.query(sql, location=location).result())
    if len(rows) != 1:
        raise RuntimeError("Control query did not return exactly one row.")
    return int(rows[0]["violation_count"])


def control_queries(
    project_id: str,
    datasets: dict[str, str],
) -> dict[str, str]:
    mart = f"`{project_id}.{datasets['mart']}"

    return {
        "date_dimension_is_unique_and_complete": f"""
          SELECT
            (
              SELECT COUNT(*) - COUNT(DISTINCT date_key)
              FROM {mart}.dim_ai_date`
            )
            +
            ABS(
              (
                SELECT COUNT(*)
                FROM {mart}.dim_ai_date`
              )
              -
              DATE_DIFF(DATE '2026-06-30', DATE '2025-01-01', DAY)
              - 1
            ) AS violation_count
        """,
        "provider_dimension_key_is_unique": f"""
          SELECT COUNT(*) - COUNT(DISTINCT provider_key) AS violation_count
          FROM {mart}.dim_ai_provider`
        """,
        "model_dimension_key_is_unique": f"""
          SELECT COUNT(*) - COUNT(DISTINCT model_key) AS violation_count
          FROM {mart}.dim_ai_model`
        """,
        "application_dimension_key_is_unique": f"""
          SELECT COUNT(*) - COUNT(DISTINCT application_key) AS violation_count
          FROM {mart}.dim_ai_application`
        """,
        "experiment_dimension_key_is_unique": f"""
          SELECT COUNT(*) - COUNT(DISTINCT experiment_key) AS violation_count
          FROM {mart}.dim_ai_experiment`
        """,
        "financial_fact_reconciles_to_application_cost": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(invoice_billed_cost)
                FROM {mart}.fact_ai_financial_monthly`
              )
              -
              (
                SELECT SUM(
                  allocated_invoice_billed_cost
                  + unallocated_invoice_billed_cost
                )
                FROM {mart}.mart_ai_application_cost`
              )
            ) <= 0.000001,
            0,
            1
          ) AS violation_count
        """,
        "usage_fact_reconciles_to_token_economics": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(usage_cost_estimate)
                FROM {mart}.fact_ai_usage_monthly`
              )
              -
              (
                SELECT SUM(usage_cost_estimate)
                FROM {mart}.mart_ai_token_economics`
              )
            ) <= 0.000001,
            0,
            1
          ) AS violation_count
        """,
        "unit_economics_fact_reconciles": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(invoice_billed_usage_cost)
                FROM {mart}.fact_ai_unit_economics_monthly`
              )
              -
              (
                SELECT SUM(invoice_billed_usage_cost)
                FROM {mart}.mart_ai_unit_economics`
              )
            ) <= 0.000001,
            0,
            1
          ) AS violation_count
        """,
        "optimization_fact_reconciles": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(identified_annualized_savings)
                FROM {mart}.fact_ai_optimization_monthly`
              )
              -
              (
                SELECT SUM(identified_annualized_savings)
                FROM {mart}.mart_ai_optimization`
              )
            ) <= 0.000001,
            0,
            1
          ) AS violation_count
        """,
        "experiment_current_has_one_row_per_experiment": f"""
          SELECT
            COUNT(*) - COUNT(DISTINCT experiment_key) AS violation_count
          FROM {mart}.fact_ai_experiment_current`
        """,
        "all_fact_provider_keys_resolve": f"""
          SELECT
            (
              SELECT COUNT(*)
              FROM {mart}.fact_ai_financial_monthly` AS f
              LEFT JOIN {mart}.dim_ai_provider` AS d
                USING (provider_key)
              WHERE d.provider_key IS NULL
            )
            +
            (
              SELECT COUNT(*)
              FROM {mart}.fact_ai_usage_monthly` AS f
              LEFT JOIN {mart}.dim_ai_provider` AS d
                USING (provider_key)
              WHERE d.provider_key IS NULL
            )
            +
            (
              SELECT COUNT(*)
              FROM {mart}.fact_ai_unit_economics_monthly` AS f
              LEFT JOIN {mart}.dim_ai_provider` AS d
                USING (provider_key)
              WHERE d.provider_key IS NULL
            )
            +
            (
              SELECT COUNT(*)
              FROM {mart}.fact_ai_optimization_monthly` AS f
              LEFT JOIN {mart}.dim_ai_provider` AS d
                USING (provider_key)
              WHERE d.provider_key IS NULL
            ) AS violation_count
        """,
        "all_fact_model_keys_resolve": f"""
          SELECT
            (
              SELECT COUNT(*)
              FROM {mart}.fact_ai_financial_monthly` AS f
              LEFT JOIN {mart}.dim_ai_model` AS d
                USING (model_key)
              WHERE d.model_key IS NULL
            )
            +
            (
              SELECT COUNT(*)
              FROM {mart}.fact_ai_usage_monthly` AS f
              LEFT JOIN {mart}.dim_ai_model` AS d
                USING (model_key)
              WHERE d.model_key IS NULL
            )
            +
            (
              SELECT COUNT(*)
              FROM {mart}.fact_ai_unit_economics_monthly` AS f
              LEFT JOIN {mart}.dim_ai_model` AS d
                USING (model_key)
              WHERE d.model_key IS NULL
            )
            +
            (
              SELECT COUNT(*)
              FROM {mart}.fact_ai_optimization_monthly` AS f
              LEFT JOIN {mart}.dim_ai_model` AS d
                USING (model_key)
              WHERE d.model_key IS NULL
            ) AS violation_count
        """,
    }


def ensure_control_table(
    client: bigquery.Client,
    project_id: str,
    control_dataset: str,
) -> None:
    table = bigquery.Table(
        f"{project_id}.{control_dataset}.m17_semantic_control_result",
        schema=[
            bigquery.SchemaField("pipeline_run_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("control_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("violation_count", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("checked_at", "TIMESTAMP", mode="REQUIRED"),
        ],
    )
    client.create_table(table, exists_ok=True)


@pipeline_run_guard("M17_POWER_BI_SEMANTIC_MODEL")
def deploy_m17(
    *,
    project_root: Path,
    config_path: Path,
    project_id_override: str | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    project_id = project_id_override or config["project_id"]
    location = config["location"]
    datasets = config["datasets"]
    client = bigquery.Client(project=project_id)

    pipeline_run_id = current_pipeline_run_id()
    started_at = current_pipeline_started_at()

    for relative_path in config["sql_files"]:
        client.query(
            render_sql(
                project_root / relative_path,
                project_id,
                datasets,
            ),
            location=location,
        ).result()

    ensure_control_table(
        client,
        project_id,
        datasets["control"],
    )

    checked_at = datetime.now(timezone.utc)
    control_rows: list[dict[str, Any]] = []

    for control_name, sql in control_queries(
        project_id,
        datasets,
    ).items():
        violation_count = query_scalar(client, sql, location)
        control_rows.append(
            {
                "pipeline_run_id": pipeline_run_id,
                "control_name": control_name,
                "violation_count": violation_count,
                "status": "PASS" if violation_count == 0 else "FAIL",
                "checked_at": checked_at.isoformat(),
            }
        )

    errors = client.insert_rows_json(
        (
            f"{project_id}.{datasets['control']}."
            "m17_semantic_control_result"
        ),
        control_rows,
    )
    if errors:
        raise RuntimeError(f"Could not write M17 controls: {errors}")

    failed = [row for row in control_rows if row["status"] != "PASS"]
    if failed:
        raise RuntimeError(f"M17 controls failed: {failed}")

    completed_at = datetime.now(timezone.utc)
    manifest = {
        "pipeline_run_id": pipeline_run_id,
        "pipeline_name": "M17_POWER_BI_SEMANTIC_MODEL",
        "project_id": project_id,
        "location": location,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "status": "PASS",
        "created_objects": config["expected_objects"],
        "controls": control_rows,
    }

    manifest_path = (
        project_root
        / "data"
        / "generated"
        / "m17_semantic_model_manifest.json"
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    run_errors = client.insert_rows_json(
        f"{project_id}.{datasets['control']}.pipeline_run_log",
        [
            {
                "pipeline_run_id": pipeline_run_id,
                "pipeline_name": "M17_POWER_BI_SEMANTIC_MODEL",
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "status": "PASS",
                "loaded_table_count": len(config["expected_objects"]),
                "error_message": None,
            }
        ],
    )
    if run_errors:
        raise RuntimeError(f"Could not write M17 pipeline log: {run_errors}")

    return manifest
