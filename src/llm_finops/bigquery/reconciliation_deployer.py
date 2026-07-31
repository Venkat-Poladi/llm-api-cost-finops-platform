from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
import json
import uuid

import yaml
from google.cloud import bigquery


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing M8 configuration: {path}")
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
        "{{STAGING_DATASET}}": datasets["staging"],
        "{{CORE_DATASET}}": datasets["core"],
    }

    sql = path.read_text(encoding="utf-8")

    for placeholder, value in replacements.items():
        sql = sql.replace(placeholder, value)

    return sql


def render_object_name(
    value: str,
    datasets: dict[str, str],
) -> str:
    replacements = {
        "{{STAGING_DATASET}}": datasets["staging"],
        "{{CORE_DATASET}}": datasets["core"],
    }

    for placeholder, replacement in replacements.items():
        value = value.replace(placeholder, replacement)

    return value


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
    staging = f"`{project_id}.{datasets['staging']}"
    core = f"`{project_id}.{datasets['core']}"

    return {
        "fact_row_count_matches_cost_source": f"""
          SELECT ABS(
            (SELECT COUNT(*) FROM {core}.fct_ai_cost_reconciliation`)
            -
            (SELECT COUNT(*) FROM {staging}.stg_ai_provider_cost`)
          ) AS violation_count
        """,
        "reconciliation_fact_grain_is_unique": f"""
          SELECT
            COUNT(*) - COUNT(DISTINCT reconciliation_fact_id)
              AS violation_count
          FROM {core}.fct_ai_cost_reconciliation`
        """,
        "every_usage_line_has_one_monthly_rollup": f"""
          SELECT COUNTIF(
            line_item_type = 'usage'
            AND usage_rollup_match_count != 1
          ) AS violation_count
          FROM {core}.fct_ai_cost_reconciliation`
        """,
        "non_usage_lines_have_no_usage_estimate": f"""
          SELECT COUNTIF(
            line_item_type != 'usage'
            AND (
              usage_cost_estimate IS NOT NULL
              OR usage_to_reported_variance IS NOT NULL
              OR usage_to_reported_variance_pct IS NOT NULL
              OR usage_reconciliation_status != 'NOT_APPLICABLE'
            )
          ) AS violation_count
          FROM {core}.fct_ai_cost_reconciliation`
        """,
        "all_reconciliation_exceptions_have_reason_codes": f"""
          SELECT COUNTIF(
            exception_status = 'EXCEPTION'
            AND variance_reason_code IS NULL
          ) AS violation_count
          FROM {core}.fct_ai_cost_reconciliation`
        """,
        "provider_reported_total_reconciles": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(provider_reported_cost)
                FROM {core}.fct_ai_cost_reconciliation`
              )
              -
              (
                SELECT SUM(provider_reported_cost)
                FROM {staging}.stg_ai_provider_cost`
              )
            ) <= 0.000001,
            0,
            1
          ) AS violation_count
        """,
        "invoice_billed_total_reconciles": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(invoice_billed_cost)
                FROM {core}.fct_ai_cost_reconciliation`
              )
              -
              (
                SELECT SUM(invoice_billed_cost)
                FROM {staging}.stg_ai_provider_cost`
              )
            ) <= 0.000001,
            0,
            1
          ) AS violation_count
        """,
        "usage_estimate_total_reconciles": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(usage_cost_estimate)
                FROM {core}.fct_ai_cost_reconciliation`
                WHERE line_item_type = 'usage'
              )
              -
              (
                SELECT SUM(usage_cost_estimate)
                FROM {staging}.stg_ai_usage_cost_monthly`
              )
            ) <= 0.000001,
            0,
            1
          ) AS violation_count
        """,
        "no_unpriced_daily_rows_reach_reconciliation": f"""
          SELECT COUNTIF(
            line_item_type = 'usage'
            AND COALESCE(unpriced_daily_row_count, 0) != 0
          ) AS violation_count
          FROM {core}.fct_ai_cost_reconciliation`
        """,
        "all_reconciliation_currency_is_usd": f"""
          SELECT COUNTIF(
            billing_currency != 'USD'
            OR (
              line_item_type = 'usage'
              AND estimate_currency != 'USD'
            )
          ) AS violation_count
          FROM {core}.fct_ai_cost_reconciliation`
        """,
        "monthly_usage_rollup_has_no_orphans": f"""
          SELECT COUNT(*) AS violation_count
          FROM {staging}.stg_ai_usage_cost_monthly` AS u
          LEFT JOIN {staging}.stg_ai_provider_cost` AS c
            ON c.line_item_type = 'usage'
            AND c.billing_month = u.billing_month
            AND c.provider = u.provider
            AND c.provider_project_id = u.provider_project_id
            AND c.model = u.model
          WHERE c.provider_line_item_id IS NULL
        """,
        "status_values_are_controlled": f"""
          SELECT COUNTIF(
            usage_reconciliation_status
              NOT IN ('PASS', 'EXCEPTION', 'NOT_APPLICABLE')
            OR invoice_reconciliation_status
              NOT IN ('PASS', 'EXCEPTION')
            OR exception_status NOT IN ('PASS', 'EXCEPTION')
          ) AS violation_count
          FROM {core}.fct_ai_cost_reconciliation`
        """,
    }


def ensure_control_table(
    client: bigquery.Client,
    project_id: str,
    control_dataset: str,
) -> None:
    table = bigquery.Table(
        f"{project_id}.{control_dataset}.m8_reconciliation_control_result",
        schema=[
            bigquery.SchemaField("pipeline_run_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("control_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("violation_count", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("checked_at", "TIMESTAMP", mode="REQUIRED"),
        ],
    )
    client.create_table(table, exists_ok=True)


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    return value


def reconciliation_summary(
    client: bigquery.Client,
    project_id: str,
    core_dataset: str,
    location: str,
) -> dict[str, Any]:
    sql = f"""
      SELECT
        COUNT(*) AS reconciliation_rows,
        COUNTIF(line_item_type = 'usage') AS usage_rows,
        COUNTIF(line_item_type != 'usage') AS non_usage_rows,
        COUNTIF(usage_reconciliation_status = 'EXCEPTION')
          AS usage_exceptions,
        COUNTIF(invoice_reconciliation_status = 'EXCEPTION')
          AS invoice_exceptions,
        SUM(usage_cost_estimate) AS usage_cost_estimate,
        SUM(provider_reported_cost) AS provider_reported_cost,
        SUM(invoice_billed_cost) AS invoice_billed_cost
      FROM `{project_id}.{core_dataset}.fct_ai_cost_reconciliation`
    """
    rows = list(client.query(sql, location=location).result())
    if len(rows) != 1:
        raise RuntimeError("M8 summary query did not return exactly one row.")
    return {
        key: json_safe(value)
        for key, value in dict(rows[0].items()).items()
    }


def deploy_m8(
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

    pipeline_run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    for relative_path in config["sql_files"]:
        sql_path = project_root / relative_path
        client.query(
            render_sql(sql_path, project_id, datasets),
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

    insert_errors = client.insert_rows_json(
        (
            f"{project_id}.{datasets['control']}."
            "m8_reconciliation_control_result"
        ),
        control_rows,
    )
    if insert_errors:
        raise RuntimeError(
            f"Could not write M8 control results: {insert_errors}"
        )

    failed = [row for row in control_rows if row["status"] != "PASS"]
    if failed:
        raise RuntimeError(f"M8 controls failed: {failed}")

    summary = reconciliation_summary(
        client,
        project_id,
        datasets["core"],
        location,
    )
    completed_at = datetime.now(timezone.utc)

    manifest = {
        "pipeline_run_id": pipeline_run_id,
        "pipeline_name": "M8_MONTHLY_COST_RECONCILIATION",
        "project_id": project_id,
        "location": location,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "status": "PASS",
        "created_objects": [
            render_object_name(object_name, datasets)
            for object_name in config["expected_objects"]
        ],
        "controls": control_rows,
        "summary": summary,
    }

    manifest_path = (
        project_root / "data" / "generated" / "m8_reconciliation_manifest.json"
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
                "pipeline_name": "M8_MONTHLY_COST_RECONCILIATION",
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "status": "PASS",
                "loaded_table_count": len(config["expected_objects"]),
                "error_message": None,
            }
        ],
    )
    if run_errors:
        raise RuntimeError(f"Could not write M8 pipeline log: {run_errors}")

    return manifest
