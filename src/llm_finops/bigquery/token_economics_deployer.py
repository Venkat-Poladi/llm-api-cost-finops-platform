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
        raise FileNotFoundError(f"Missing M11 configuration: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def render_sql(path: Path, project_id: str) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing SQL file: {path}")
    return path.read_text(encoding="utf-8").replace(
        "{{PROJECT_ID}}",
        project_id,
    )


def query_scalar(
    client: bigquery.Client,
    sql: str,
    location: str,
) -> int:
    rows = list(client.query(sql, location=location).result())
    if len(rows) != 1:
        raise RuntimeError("Control query did not return exactly one row.")
    return int(rows[0]["violation_count"])


def control_queries(project_id: str) -> dict[str, str]:
    staging = f"`{project_id}.llm_finops_staging"
    mart = f"`{project_id}.llm_finops_mart"

    return {
        "token_economics_grain_is_unique": f"""
          SELECT
            COUNT(*) - COUNT(DISTINCT token_economics_id)
              AS violation_count
          FROM {mart}.mart_ai_token_economics`
        """,
        "usage_cost_total_reconciles": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(usage_cost_estimate)
                FROM {mart}.mart_ai_token_economics`
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
        "request_total_reconciles": f"""
          SELECT IF(
            (
              SELECT SUM(request_count)
              FROM {mart}.mart_ai_token_economics`
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
        "input_token_total_reconciles": f"""
          SELECT IF(
            (
              SELECT SUM(normalized_total_input_tokens)
              FROM {mart}.mart_ai_token_economics`
            )
            =
            (
              SELECT SUM(normalized_total_input_tokens)
              FROM {staging}.stg_ai_provider_usage_priced`
              WHERE pricing_status = 'Priced'
            ),
            0,
            1
          ) AS violation_count
        """,
        "output_and_reasoning_totals_reconcile": f"""
          SELECT IF(
            (
              SELECT SUM(output_tokens)
              FROM {mart}.mart_ai_token_economics`
            )
            =
            (
              SELECT SUM(output_tokens)
              FROM {staging}.stg_ai_provider_usage_priced`
              WHERE pricing_status = 'Priced'
            )
            AND
            (
              SELECT SUM(reasoning_tokens)
              FROM {mart}.mart_ai_token_economics`
            )
            =
            (
              SELECT SUM(reasoning_tokens)
              FROM {staging}.stg_ai_provider_usage_priced`
              WHERE pricing_status = 'Priced'
            ),
            0,
            1
          ) AS violation_count
        """,
        "reasoning_tokens_do_not_exceed_output": f"""
          SELECT COUNTIF(reasoning_tokens > output_tokens)
            AS violation_count
          FROM {mart}.mart_ai_token_economics`
        """,
        "cache_share_is_null_or_between_zero_and_one": f"""
          SELECT COUNTIF(
            (normalized_total_input_tokens = 0
              AND cache_read_share IS NOT NULL)
            OR cache_read_share < 0
            OR cache_read_share > 1
          ) AS violation_count
          FROM {mart}.mart_ai_token_economics`
        """,
        "reasoning_overhead_is_null_or_between_zero_and_one": f"""
          SELECT COUNTIF(
            (output_tokens = 0 AND reasoning_overhead_pct IS NOT NULL)
            OR reasoning_overhead_pct < 0
            OR reasoning_overhead_pct > 1
          ) AS violation_count
          FROM {mart}.mart_ai_token_economics`
        """,
        "batch_adoption_is_null_or_between_zero_and_one": f"""
          SELECT COUNTIF(
            (request_count = 0 AND batch_adoption_pct IS NOT NULL)
            OR batch_adoption_pct < 0
            OR batch_adoption_pct > 1
          ) AS violation_count
          FROM {mart}.mart_ai_token_economics`
        """,
        "cost_per_token_metrics_are_valid": f"""
          SELECT COUNTIF(
            cost_per_million_input_tokens < 0
            OR cost_per_million_output_tokens < 0
            OR cost_per_million_total_tokens < 0
            OR estimated_cost_per_provider_request < 0
          ) AS violation_count
          FROM {mart}.mart_ai_token_economics`
        """,
        "cache_savings_is_nonnegative_and_bounded": f"""
          SELECT COUNTIF(
            estimated_cache_savings < 0
            OR estimated_cache_savings
              > no_cache_baseline_cost + 0.000000001
          ) AS violation_count
          FROM {mart}.mart_ai_token_economics`
        """,
        "batch_savings_is_nonnegative": f"""
          SELECT COUNTIF(
            estimated_batch_savings_opportunity < 0
            OR nonbatch_rows_without_one_batch_rate != 0
          ) AS violation_count
          FROM {mart}.mart_ai_token_economics`
        """,
        "telemetry_failure_and_retry_costs_reconcile": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(estimated_failed_attempt_cost)
                FROM {mart}.mart_ai_token_economics`
              )
              -
              (
                SELECT SUM(
                  IF(attempt_status = 'failed', usage_cost_estimate, 0)
                )
                FROM {staging}.stg_ai_request_telemetry`
                WHERE telemetry_validation_status = 'Valid'
              )
            ) <= 0.000001
            AND
            ABS(
              (
                SELECT SUM(estimated_retry_cost)
                FROM {mart}.mart_ai_token_economics`
              )
              -
              (
                SELECT SUM(
                  IF(is_retry_attempt, usage_cost_estimate, 0)
                )
                FROM {staging}.stg_ai_request_telemetry`
                WHERE telemetry_validation_status = 'Valid'
              )
            ) <= 0.000001,
            0,
            1
          ) AS violation_count
        """,
        "financial_basis_and_currency_are_labeled": f"""
          SELECT COUNTIF(
            financial_basis != 'usage_cost_estimate'
            OR billing_currency != 'USD'
            OR failure_cost_label != 'Estimated from request telemetry'
          ) AS violation_count
          FROM {mart}.mart_ai_token_economics`
        """,
    }


def ensure_control_table(
    client: bigquery.Client,
    project_id: str,
) -> None:
    table = bigquery.Table(
        f"{project_id}.llm_finops_control.m11_token_control_result",
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


def token_summary(
    client: bigquery.Client,
    project_id: str,
    location: str,
) -> dict[str, Any]:
    sql = f"""
      SELECT
        COUNT(*) AS token_economics_rows,
        SUM(request_count) AS request_count,
        SUM(total_tokens) AS total_tokens,
        SUM(usage_cost_estimate) AS usage_cost_estimate,
        SAFE_DIVIDE(
          SUM(normalized_cache_read_tokens),
          SUM(normalized_total_input_tokens)
        ) AS overall_cache_read_share,
        SAFE_DIVIDE(
          SUM(reasoning_tokens),
          SUM(output_tokens)
        ) AS overall_reasoning_overhead_pct,
        SAFE_DIVIDE(
          SUM(batch_request_count),
          SUM(request_count)
        ) AS overall_batch_adoption_pct,
        SUM(estimated_cache_savings) AS estimated_cache_savings,
        SUM(estimated_batch_savings_opportunity)
          AS estimated_batch_savings_opportunity,
        SUM(estimated_failed_attempt_cost)
          AS estimated_failed_attempt_cost,
        SUM(estimated_retry_cost) AS estimated_retry_cost
      FROM `{project_id}.llm_finops_mart.mart_ai_token_economics`
    """
    rows = list(client.query(sql, location=location).result())
    if len(rows) != 1:
        raise RuntimeError("M11 summary query did not return exactly one row.")
    return {
        key: json_safe(value)
        for key, value in dict(rows[0].items()).items()
    }


def deploy_m11(
    *,
    project_root: Path,
    config_path: Path,
    project_id_override: str | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    project_id = project_id_override or config["project_id"]
    location = config["location"]
    client = bigquery.Client(project=project_id)

    pipeline_run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    for relative_path in config["sql_files"]:
        client.query(
            render_sql(project_root / relative_path, project_id),
            location=location,
        ).result()

    ensure_control_table(client, project_id)

    checked_at = datetime.now(timezone.utc)
    control_rows: list[dict[str, Any]] = []

    for control_name, sql in control_queries(project_id).items():
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
        f"{project_id}.llm_finops_control.m11_token_control_result",
        control_rows,
    )
    if insert_errors:
        raise RuntimeError(
            f"Could not write M11 control results: {insert_errors}"
        )

    failed = [row for row in control_rows if row["status"] != "PASS"]
    if failed:
        raise RuntimeError(f"M11 controls failed: {failed}")

    summary = token_summary(client, project_id, location)
    completed_at = datetime.now(timezone.utc)

    manifest = {
        "pipeline_run_id": pipeline_run_id,
        "pipeline_name": "M11_TOKEN_ECONOMICS",
        "project_id": project_id,
        "location": location,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "status": "PASS",
        "created_objects": config["expected_objects"],
        "controls": control_rows,
        "summary": summary,
    }

    manifest_path = (
        project_root
        / "data"
        / "generated"
        / "m11_token_economics_manifest.json"
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    run_errors = client.insert_rows_json(
        f"{project_id}.llm_finops_control.pipeline_run_log",
        [
            {
                "pipeline_run_id": pipeline_run_id,
                "pipeline_name": "M11_TOKEN_ECONOMICS",
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "status": "PASS",
                "loaded_table_count": len(config["expected_objects"]),
                "error_message": None,
            }
        ],
    )
    if run_errors:
        raise RuntimeError(f"Could not write M11 pipeline log: {run_errors}")

    return manifest
