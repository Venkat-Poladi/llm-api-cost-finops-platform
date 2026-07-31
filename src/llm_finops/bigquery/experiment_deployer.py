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
        raise FileNotFoundError(f"Missing M15 configuration: {path}")
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
        "{{STAGING_DATASET}}": datasets["staging"],
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
    raw = f"`{project_id}.{datasets['raw']}"
    staging = f"`{project_id}.{datasets['staging']}"
    mart = f"`{project_id}.{datasets['mart']}"

    return {
        "experiment_driver_grain_is_unique": f"""
          SELECT
            COUNT(*) - COUNT(DISTINCT experiment_driver_id)
              AS violation_count
          FROM {staging}.stg_ai_experiment_invoice_driver_daily`
        """,
        "experiment_governance_grain_is_unique": f"""
          SELECT
            COUNT(*) - COUNT(DISTINCT experiment_governance_id)
              AS violation_count
          FROM {mart}.mart_ai_experiments`
        """,
        "all_controlled_experiments_are_present": f"""
          SELECT COUNT(*) AS violation_count
          FROM {raw}.dim_ai_experiment_control` AS c
          LEFT JOIN (
            SELECT DISTINCT experiment_id
            FROM {mart}.mart_ai_experiments`
          ) AS m
          USING (experiment_id)
          WHERE m.experiment_id IS NULL
        """,
        "driver_operational_cost_reconciles_to_experiment_telemetry": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(experiment_driver_cost_estimate)
                FROM {staging}.stg_ai_experiment_invoice_driver_daily`
              )
              -
              (
                SELECT SUM(usage_cost_estimate)
                FROM {staging}.stg_ai_request_telemetry`
                WHERE telemetry_validation_status = 'Valid'
                  AND experiment_id IS NOT NULL
              )
            ) <= 0.000001,
            0,
            1
          ) AS violation_count
        """,
        "experiment_driver_shares_are_valid": f"""
          SELECT COUNTIF(
            financial_allocation_share < 0
            OR financial_allocation_share > 1
          ) AS violation_count
          FROM {staging}.stg_ai_experiment_invoice_driver_daily`
        """,
        "experiment_shares_do_not_overallocate_financial_scope": f"""
          SELECT COUNT(*) AS violation_count
          FROM (
            SELECT
              billing_month,
              provider,
              provider_project_id,
              model,
              SUM(financial_allocation_share) AS total_share
            FROM {staging}.stg_ai_experiment_invoice_driver_daily`
            GROUP BY 1, 2, 3, 4
            HAVING total_share > 1.000000001
          )
        """,
        "experiment_invoice_cost_does_not_exceed_usage_invoice": f"""
          SELECT COUNT(*) AS violation_count
          FROM (
            SELECT
              d.billing_month,
              d.provider,
              d.provider_project_id,
              d.model,
              SUM(d.allocated_invoice_billed_experiment_cost)
                AS experiment_invoice_cost,
              ANY_VALUE(d.monthly_invoice_billed_usage_cost)
                AS source_invoice_cost
            FROM {staging}.stg_ai_experiment_invoice_driver_daily` AS d
            GROUP BY 1, 2, 3, 4
            HAVING experiment_invoice_cost
              > source_invoice_cost + 0.000001
          )
        """,
        "experiment_driver_formula_is_correct": f"""
          SELECT COUNTIF(
            ABS(
              allocated_invoice_billed_experiment_cost
              - monthly_invoice_billed_usage_cost
                * financial_allocation_share
            ) > 0.000001
          ) AS violation_count
          FROM {staging}.stg_ai_experiment_invoice_driver_daily`
        """,
        "evaluation_dates_respect_control_window": f"""
          SELECT COUNTIF(
            evaluation_date < start_date
            OR evaluation_date > planned_end_date
            OR period_start_date < start_date
            OR period_end_date > planned_end_date
            OR period_start_date > period_end_date
          ) AS violation_count
          FROM {mart}.mart_ai_experiments`
        """,
        "limit_period_shapes_are_correct": f"""
          SELECT COUNTIF(
            (
              spending_limit_period = 'day'
              AND (
                period_start_date != evaluation_date
                OR period_end_date != evaluation_date
              )
            )
            OR
            (
              spending_limit_period = 'lifetime'
              AND period_start_date != start_date
            )
            OR spending_limit_period NOT IN ('day', 'month', 'lifetime')
          ) AS violation_count
          FROM {mart}.mart_ai_experiments`
        """,
        "threshold_formulas_are_correct": f"""
          SELECT COUNTIF(
            ABS(
              warning_spend_threshold
              - spending_limit * warning_threshold
            ) > 0.000001
            OR ABS(
              hard_stop_spend_threshold
              - spending_limit * hard_stop_threshold
            ) > 0.000001
          ) AS violation_count
          FROM {mart}.mart_ai_experiments`
        """,
        "threshold_status_matches_spend": f"""
          SELECT COUNTIF(
            (
              period_invoice_billed_experiment_cost
                >= hard_stop_spend_threshold
              AND threshold_status != 'HARD_STOP'
            )
            OR
            (
              period_invoice_billed_experiment_cost
                < hard_stop_spend_threshold
              AND period_invoice_billed_experiment_cost
                >= warning_spend_threshold
              AND threshold_status != 'WARNING'
            )
            OR
            (
              period_invoice_billed_experiment_cost
                < warning_spend_threshold
              AND threshold_status != 'WITHIN_LIMIT'
            )
          ) AS violation_count
          FROM {mart}.mart_ai_experiments`
        """,
        "decision_as_of_date_is_not_from_the_future": f"""
          SELECT COUNTIF(
            latest_decision_date > evaluation_date
          ) AS violation_count
          FROM {mart}.mart_ai_experiments`
        """,
        "final_decision_status_aligns_with_control": f"""
          SELECT COUNTIF(
            evaluation_date = planned_end_date
            AND decision_status_as_of_date != source_current_status
          ) AS violation_count
          FROM {mart}.mart_ai_experiments`
        """,
        "governance_exceptions_have_reasons": f"""
          SELECT COUNTIF(
            governance_exception_status = 'EXCEPTION'
            AND governance_exception_reason IS NULL
          ) AS violation_count
          FROM {mart}.mart_ai_experiments`
        """,
        "hard_stop_action_status_is_consistent": f"""
          SELECT COUNTIF(
            (
              threshold_status = 'HARD_STOP'
              AND decision_status_as_of_date = 'stopped'
              AND governance_action_status != 'HARD_STOP_COMPLIANT'
            )
            OR
            (
              threshold_status = 'HARD_STOP'
              AND COALESCE(decision_status_as_of_date, '') != 'stopped'
              AND governance_action_status != 'HARD_STOP_ACTION_REQUIRED'
            )
          ) AS violation_count
          FROM {mart}.mart_ai_experiments`
        """,
        "decision_financial_mismatch_is_explicit": f"""
          SELECT COUNTIF(
            decision_financial_evidence_status
              = 'FINANCIAL_EVIDENCE_MISMATCH'
            AND governance_exception_status != 'EXCEPTION'
          ) AS violation_count
          FROM {mart}.mart_ai_experiments`
        """,
        "financial_basis_currency_and_nonusage_exclusion_are_valid": f"""
          SELECT COUNTIF(
            financial_basis
              != 'allocated_invoice_billed_cost_usage_lines_only'
            OR operational_basis
              != 'request_telemetry_usage_cost_estimate'
            OR limit_currency != 'USD'
          ) AS violation_count
          FROM {mart}.mart_ai_experiments`
        """,
    }


def ensure_control_table(
    client: bigquery.Client,
    project_id: str,
    control_dataset: str,
) -> None:
    table = bigquery.Table(
        f"{project_id}.{control_dataset}.m15_experiment_control_result",
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


def experiment_summary(
    client: bigquery.Client,
    project_id: str,
    mart_dataset: str,
    location: str,
) -> dict[str, Any]:
    sql = f"""
      SELECT
        COUNT(*) AS experiment_governance_rows,
        COUNT(DISTINCT experiment_id) AS experiment_count,
        COUNTIF(threshold_status = 'WARNING') AS warning_rows,
        COUNTIF(threshold_status = 'HARD_STOP') AS hard_stop_rows,
        COUNTIF(
          governance_action_status = 'HARD_STOP_ACTION_REQUIRED'
        ) AS hard_stop_action_required_rows,
        COUNTIF(
          decision_financial_evidence_status
            = 'FINANCIAL_EVIDENCE_MISMATCH'
        ) AS financial_evidence_mismatch_rows,
        COUNTIF(period_measurement_quality_status = 'LIMITED')
          AS limited_measurement_rows,
        MAX(period_invoice_billed_experiment_cost)
          AS maximum_period_invoice_billed_experiment_cost,
        MAX(spend_to_limit_pct) AS maximum_spend_to_limit_pct
      FROM `{project_id}.{mart_dataset}.mart_ai_experiments`
    """
    rows = list(client.query(sql, location=location).result())
    if len(rows) != 1:
        raise RuntimeError("M15 summary query did not return exactly one row.")
    return {
        key: json_safe(value)
        for key, value in dict(rows[0].items()).items()
    }


def deploy_m15(
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
            "m15_experiment_control_result"
        ),
        control_rows,
    )
    if insert_errors:
        raise RuntimeError(
            f"Could not write M15 control results: {insert_errors}"
        )

    failed = [row for row in control_rows if row["status"] != "PASS"]
    if failed:
        raise RuntimeError(f"M15 controls failed: {failed}")

    summary = experiment_summary(
        client,
        project_id,
        datasets["mart"],
        location,
    )
    completed_at = datetime.now(timezone.utc)

    manifest = {
        "pipeline_run_id": pipeline_run_id,
        "pipeline_name": "M15_EXPERIMENT_GOVERNANCE",
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
        / "m15_experiment_governance_manifest.json"
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
                "pipeline_name": "M15_EXPERIMENT_GOVERNANCE",
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "status": "PASS",
                "loaded_table_count": len(config["expected_objects"]),
                "error_message": None,
            }
        ],
    )
    if run_errors:
        raise RuntimeError(f"Could not write M15 pipeline log: {run_errors}")

    return manifest
