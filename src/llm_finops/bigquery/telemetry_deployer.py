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
        raise FileNotFoundError(f"Missing M10 configuration: {path}")
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
        "{{MART_DATASET}}": datasets["mart"],
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
        "{{CORE_DATASET}}": datasets["core"],
        "{{MART_DATASET}}": datasets["mart"],
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
    mart = f"`{project_id}.{datasets['mart']}"

    return {
        "daily_reconciliation_grain_is_unique": f"""
          SELECT
            COUNT(*) - COUNT(DISTINCT telemetry_reconciliation_id)
              AS violation_count
          FROM {core}.fct_ai_telemetry_reconciliation_daily`
        """,
        "all_provider_usage_groups_are_represented": f"""
          SELECT COUNT(*) AS violation_count
          FROM (
            SELECT usage_date, provider, provider_project_id, model
            FROM {staging}.stg_ai_provider_usage_priced`
            WHERE pricing_status = 'Priced'
            GROUP BY 1, 2, 3, 4
          ) AS p
          LEFT JOIN {core}.fct_ai_telemetry_reconciliation_daily` AS r
            USING (usage_date, provider, provider_project_id, model)
          WHERE r.telemetry_reconciliation_id IS NULL
        """,
        "all_telemetry_groups_are_represented": f"""
          SELECT COUNT(*) AS violation_count
          FROM (
            SELECT usage_date, provider, provider_project_id, model
            FROM {staging}.stg_ai_request_telemetry`
            WHERE telemetry_validation_status = 'Valid'
            GROUP BY 1, 2, 3, 4
          ) AS t
          LEFT JOIN {core}.fct_ai_telemetry_reconciliation_daily` AS r
            USING (usage_date, provider, provider_project_id, model)
          WHERE r.telemetry_reconciliation_id IS NULL
        """,
        "provider_request_total_reconciles": f"""
          SELECT IF(
            (
              SELECT SUM(provider_request_count)
              FROM {core}.fct_ai_telemetry_reconciliation_daily`
            )
            =
            (
              SELECT SUM(request_count)
              FROM {staging}.stg_ai_provider_usage_priced`
              WHERE pricing_status = 'Priced'
            ),
            0,
            1
          ) AS violation_count
        """,
        "provider_token_total_reconciles": f"""
          SELECT IF(
            (
              SELECT SUM(provider_total_tokens)
              FROM {core}.fct_ai_telemetry_reconciliation_daily`
            )
            =
            (
              SELECT SUM(normalized_total_input_tokens + output_tokens)
              FROM {staging}.stg_ai_provider_usage_priced`
              WHERE pricing_status = 'Priced'
            ),
            0,
            1
          ) AS violation_count
        """,
        "provider_cost_total_reconciles": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(provider_usage_cost_estimate)
                FROM {core}.fct_ai_telemetry_reconciliation_daily`
              )
              -
              (
                SELECT SUM(usage_cost_estimate)
                FROM {staging}.stg_ai_provider_usage_priced`
                WHERE pricing_status = 'Priced'
              )
            ) <= 0.000001,
            0,
            1
          ) AS violation_count
        """,
        "telemetry_attempt_total_reconciles": f"""
          SELECT IF(
            (
              SELECT SUM(telemetry_attempt_count)
              FROM {core}.fct_ai_telemetry_reconciliation_daily`
            )
            =
            (
              SELECT COUNT(*)
              FROM {staging}.stg_ai_request_telemetry`
              WHERE telemetry_validation_status = 'Valid'
            ),
            0,
            1
          ) AS violation_count
        """,
        "telemetry_token_total_reconciles": f"""
          SELECT IF(
            (
              SELECT SUM(telemetry_total_tokens)
              FROM {core}.fct_ai_telemetry_reconciliation_daily`
            )
            =
            (
              SELECT SUM(normalized_total_input_tokens + output_tokens)
              FROM {staging}.stg_ai_request_telemetry`
              WHERE telemetry_validation_status = 'Valid'
            ),
            0,
            1
          ) AS violation_count
        """,
        "logical_requests_have_one_final_attempt": f"""
          SELECT COUNTIF(
            has_telemetry
            AND telemetry_logical_request_count
              != telemetry_final_attempt_count
          ) AS violation_count
          FROM {core}.fct_ai_telemetry_reconciliation_daily`
        """,
        "successful_requests_do_not_exceed_logical_requests": f"""
          SELECT COUNTIF(
            telemetry_successful_logical_request_count
              > telemetry_logical_request_count
          ) AS violation_count
          FROM {core}.fct_ai_telemetry_reconciliation_daily`
        """,
        "zero_provider_tokens_have_null_coverage": f"""
          SELECT COUNTIF(
            COALESCE(provider_total_tokens, 0) = 0
            AND telemetry_token_coverage_pct IS NOT NULL
          ) AS violation_count
          FROM {core}.fct_ai_telemetry_reconciliation_daily`
        """,
        "untraceable_cost_is_valid": f"""
          SELECT COUNTIF(
            untraceable_provider_usage_cost_estimate < 0
            OR untraceable_provider_usage_cost_estimate
              > provider_usage_cost_estimate + 0.000000001
          ) AS violation_count
          FROM {core}.fct_ai_telemetry_reconciliation_daily`
        """,
        "exceptions_have_reason_codes": f"""
          SELECT COUNTIF(
            reconciliation_status = 'EXCEPTION'
            AND variance_reason_code IS NULL
          ) AS violation_count
          FROM {core}.fct_ai_telemetry_reconciliation_daily`
        """,
        "monthly_summary_reconciles_to_daily": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(provider_usage_cost_estimate)
                FROM {mart}.mart_ai_telemetry_coverage_monthly`
              )
              -
              (
                SELECT SUM(provider_usage_cost_estimate)
                FROM {core}.fct_ai_telemetry_reconciliation_daily`
              )
            ) <= 0.000001
            AND
            (
              SELECT SUM(telemetry_attempt_count)
              FROM {mart}.mart_ai_telemetry_coverage_monthly`
            )
            =
            (
              SELECT SUM(telemetry_attempt_count)
              FROM {core}.fct_ai_telemetry_reconciliation_daily`
            ),
            0,
            1
          ) AS violation_count
        """,
    }


def ensure_control_table(
    client: bigquery.Client,
    project_id: str,
    control_dataset: str,
) -> None:
    table = bigquery.Table(
        f"{project_id}.{control_dataset}.m10_telemetry_control_result",
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


def telemetry_summary(
    client: bigquery.Client,
    project_id: str,
    core_dataset: str,
    location: str,
) -> dict[str, Any]:
    sql = f"""
      SELECT
        COUNT(*) AS reconciliation_rows,
        SUM(provider_request_count) AS provider_request_count,
        SUM(telemetry_attempt_count) AS telemetry_attempt_count,
        SUM(telemetry_logical_request_count)
          AS telemetry_logical_request_count,
        SUM(telemetry_retry_attempt_count) AS telemetry_retry_attempt_count,
        SUM(provider_total_tokens) AS provider_total_tokens,
        SUM(telemetry_total_tokens) AS telemetry_total_tokens,
        SAFE_DIVIDE(
          SUM(telemetry_total_tokens),
          SUM(provider_total_tokens)
        ) AS overall_token_coverage_pct,
        SUM(untraceable_provider_usage_cost_estimate)
          AS untraceable_provider_usage_cost_estimate,
        COUNTIF(reconciliation_status = 'EXCEPTION')
          AS exception_rows
      FROM
        `{project_id}.{core_dataset}.fct_ai_telemetry_reconciliation_daily`
    """
    rows = list(client.query(sql, location=location).result())
    if len(rows) != 1:
        raise RuntimeError("M10 summary query did not return exactly one row.")
    return {
        key: json_safe(value)
        for key, value in dict(rows[0].items()).items()
    }


def deploy_m10(
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

    insert_errors = client.insert_rows_json(
        (
            f"{project_id}.{datasets['control']}."
            "m10_telemetry_control_result"
        ),
        control_rows,
    )
    if insert_errors:
        raise RuntimeError(
            f"Could not write M10 control results: {insert_errors}"
        )

    failed = [row for row in control_rows if row["status"] != "PASS"]
    if failed:
        raise RuntimeError(f"M10 controls failed: {failed}")

    summary = telemetry_summary(
        client,
        project_id,
        datasets["core"],
        location,
    )
    completed_at = datetime.now(timezone.utc)

    manifest = {
        "pipeline_run_id": pipeline_run_id,
        "pipeline_name": "M10_TELEMETRY_RECONCILIATION",
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
        project_root
        / "data"
        / "generated"
        / "m10_telemetry_reconciliation_manifest.json"
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
                "pipeline_name": "M10_TELEMETRY_RECONCILIATION",
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "status": "PASS",
                "loaded_table_count": len(config["expected_objects"]),
                "error_message": None,
            }
        ],
    )
    if run_errors:
        raise RuntimeError(f"Could not write M10 pipeline log: {run_errors}")

    return manifest
