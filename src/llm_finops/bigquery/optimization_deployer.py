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
        raise FileNotFoundError(f"Missing M13 configuration: {path}")
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
    return value.replace(
        "{{MART_DATASET}}",
        datasets["mart"],
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


def control_queries(
    project_id: str,
    datasets: dict[str, str],
) -> dict[str, str]:
    mart = f"`{project_id}.{datasets['mart']}"

    return {
        "recommendation_grain_is_unique": f"""
          SELECT
            COUNT(*) - COUNT(DISTINCT recommendation_id)
              AS violation_count
          FROM {mart}.mart_ai_optimization`
        """,
        "recommendation_types_are_controlled": f"""
          SELECT COUNTIF(
            optimization_type NOT IN (
              'BATCH_MIGRATION',
              'RETRY_REDUCTION',
              'TELEMETRY_COVERAGE',
              'CACHE_REUSE_ASSESSMENT'
            )
          ) AS violation_count
          FROM {mart}.mart_ai_optimization`
        """,
        "modeled_savings_are_not_negative": f"""
          SELECT COUNTIF(modeled_monthly_savings < 0)
            AS violation_count
          FROM {mart}.mart_ai_optimization`
        """,
        "identified_savings_annualize_monthly_savings": f"""
          SELECT COUNTIF(
            modeled_monthly_savings IS NOT NULL
            AND ABS(
              identified_annualized_savings
              - modeled_monthly_savings * 12
            ) > 0.000001
          ) AS violation_count
          FROM {mart}.mart_ai_optimization`
        """,
        "approved_implemented_realized_are_zero": f"""
          SELECT COUNTIF(
            approved_annualized_savings != 0
            OR implemented_annualized_savings != 0
            OR realized_savings != 0
            OR is_approved
            OR is_implemented
            OR is_realized
          ) AS violation_count
          FROM {mart}.mart_ai_optimization`
        """,
        "batch_savings_match_token_economics": f"""
          SELECT COUNT(*) AS violation_count
          FROM {mart}.mart_ai_optimization` AS o
          JOIN {mart}.mart_ai_token_economics` AS t
            USING (
              billing_month,
              provider,
              provider_project_id,
              model,
              model_snapshot,
              usage_type
            )
          WHERE o.optimization_type = 'BATCH_MIGRATION'
            AND ABS(
              o.modeled_monthly_savings
              - t.estimated_batch_savings_opportunity
            ) > 0.000001
        """,
        "retry_savings_use_50_percent_target": f"""
          SELECT COUNT(*) AS violation_count
          FROM {mart}.mart_ai_optimization` AS o
          JOIN {mart}.mart_ai_token_economics` AS t
            USING (
              billing_month,
              provider,
              provider_project_id,
              model,
              model_snapshot,
              usage_type
            )
          WHERE o.optimization_type = 'RETRY_REDUCTION'
            AND ABS(
              o.modeled_monthly_savings
              - t.estimated_retry_cost * 0.50
            ) > 0.000001
        """,
        "unquantified_recommendations_have_no_modeled_savings": f"""
          SELECT COUNTIF(
            savings_stage = 'UNQUANTIFIED'
            AND (
              modeled_monthly_savings IS NOT NULL
              OR identified_annualized_savings != 0
            )
          ) AS violation_count
          FROM {mart}.mart_ai_optimization`
        """,
        "ready_recommendations_are_quantified": f"""
          SELECT COUNTIF(
            evaluation_gate_status = 'READY_FOR_EVALUATION'
            AND (
              modeled_monthly_savings IS NULL
              OR modeled_monthly_savings <= 0
              OR savings_stage != 'IDENTIFIED'
            )
          ) AS violation_count
          FROM {mart}.mart_ai_optimization`
        """,
        "retry_gate_respects_telemetry_coverage": f"""
          SELECT COUNTIF(
            optimization_type = 'RETRY_REDUCTION'
            AND (
              (
                telemetry_token_coverage_pct >= 0.95
                AND evaluation_gate_status != 'READY_FOR_EVALUATION'
              )
              OR
              (
                telemetry_token_coverage_pct < 0.95
                AND evaluation_gate_status != 'HOLD_FOR_DATA'
              )
            )
          ) AS violation_count
          FROM {mart}.mart_ai_optimization`
        """,
        "telemetry_recommendations_are_data_holds": f"""
          SELECT COUNTIF(
            optimization_type = 'TELEMETRY_COVERAGE'
            AND (
              evaluation_gate_status != 'HOLD_FOR_DATA'
              OR savings_stage != 'UNQUANTIFIED'
              OR modeled_monthly_savings IS NOT NULL
              OR cost_at_risk < 0
              OR NOT requires_telemetry_remediation
            )
          ) AS violation_count
          FROM {mart}.mart_ai_optimization`
        """,
        "cache_recommendations_require_benchmark": f"""
          SELECT COUNTIF(
            optimization_type = 'CACHE_REUSE_ASSESSMENT'
            AND (
              evaluation_gate_status != 'REQUIRES_BENCHMARK'
              OR savings_stage != 'UNQUANTIFIED'
              OR modeled_monthly_savings IS NOT NULL
            )
          ) AS violation_count
          FROM {mart}.mart_ai_optimization`
        """,
        "every_recommendation_has_rationale_and_assumption": f"""
          SELECT COUNTIF(
            recommendation_title IS NULL
            OR recommendation_rationale IS NULL
            OR gate_reason IS NULL
            OR assumption_text IS NULL
            OR LENGTH(TRIM(recommendation_rationale)) = 0
            OR LENGTH(TRIM(assumption_text)) = 0
          ) AS violation_count
          FROM {mart}.mart_ai_optimization`
        """,
        "financial_basis_and_currency_are_valid": f"""
          SELECT COUNTIF(
            financial_basis != 'usage_cost_estimate'
            OR billing_currency != 'USD'
          ) AS violation_count
          FROM {mart}.mart_ai_optimization`
        """,
        "evaluation_ready_flag_matches_gate": f"""
          SELECT COUNTIF(
            evaluation_ready_flag
              != IF(
                evaluation_gate_status = 'READY_FOR_EVALUATION',
                1,
                0
              )
          ) AS violation_count
          FROM {mart}.mart_ai_optimization`
        """,
        "identified_savings_only_come_from_quantified_types": f"""
          SELECT COUNTIF(
            identified_annualized_savings > 0
            AND optimization_type NOT IN (
              'BATCH_MIGRATION',
              'RETRY_REDUCTION'
            )
          ) AS violation_count
          FROM {mart}.mart_ai_optimization`
        """,
    }


def ensure_control_table(
    client: bigquery.Client,
    project_id: str,
    control_dataset: str,
) -> None:
    table = bigquery.Table(
        f"{project_id}.{control_dataset}.m13_optimization_control_result",
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


def optimization_summary(
    client: bigquery.Client,
    project_id: str,
    mart_dataset: str,
    location: str,
) -> dict[str, Any]:
    sql = f"""
      SELECT
        COUNT(*) AS recommendation_rows,
        COUNTIF(evaluation_gate_status = 'READY_FOR_EVALUATION')
          AS ready_for_evaluation_rows,
        COUNTIF(evaluation_gate_status = 'HOLD_FOR_DATA')
          AS hold_for_data_rows,
        COUNTIF(evaluation_gate_status = 'REQUIRES_BENCHMARK')
          AS requires_benchmark_rows,
        SUM(modeled_monthly_savings) AS identified_monthly_savings,
        SUM(identified_annualized_savings)
          AS identified_annualized_savings,
        SUM(approved_annualized_savings)
          AS approved_annualized_savings,
        SUM(implemented_annualized_savings)
          AS implemented_annualized_savings,
        SUM(realized_savings) AS realized_savings,
        SUM(cost_at_risk) AS cost_at_risk
      FROM `{project_id}.{mart_dataset}.mart_ai_optimization`
    """
    rows = list(client.query(sql, location=location).result())
    if len(rows) != 1:
        raise RuntimeError("M13 summary query did not return exactly one row.")
    return {
        key: json_safe(value)
        for key, value in dict(rows[0].items()).items()
    }


def deploy_m13(
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
            "m13_optimization_control_result"
        ),
        control_rows,
    )
    if insert_errors:
        raise RuntimeError(
            f"Could not write M13 control results: {insert_errors}"
        )

    failed = [row for row in control_rows if row["status"] != "PASS"]
    if failed:
        raise RuntimeError(f"M13 controls failed: {failed}")

    summary = optimization_summary(
        client,
        project_id,
        datasets["mart"],
        location,
    )
    completed_at = datetime.now(timezone.utc)

    manifest = {
        "pipeline_run_id": pipeline_run_id,
        "pipeline_name": "M13_OPTIMIZATION_EVALUATION_GATE",
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
        / "m13_optimization_manifest.json"
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
                "pipeline_name": "M13_OPTIMIZATION_EVALUATION_GATE",
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "status": "PASS",
                "loaded_table_count": len(config["expected_objects"]),
                "error_message": None,
            }
        ],
    )
    if run_errors:
        raise RuntimeError(f"Could not write M13 pipeline log: {run_errors}")

    return manifest
