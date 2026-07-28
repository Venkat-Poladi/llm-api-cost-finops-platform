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
        raise FileNotFoundError(f"Missing M12 configuration: {path}")
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
    core = f"`{project_id}.llm_finops_core"
    mart = f"`{project_id}.llm_finops_mart"

    return {
        "application_cost_grain_is_unique": f"""
          SELECT
            COUNT(*) - COUNT(DISTINCT application_cost_id)
              AS violation_count
          FROM {mart}.mart_ai_application_cost`
        """,
        "every_financial_scope_has_one_source_anchor": f"""
          SELECT COUNT(*) AS violation_count
          FROM (
            SELECT
              financial_source_scope_id,
              COUNTIF(source_measure_anchor_flag) AS anchor_count
            FROM {mart}.mart_ai_application_cost`
            GROUP BY financial_source_scope_id
            HAVING anchor_count != 1
          )
        """,
        "source_invoice_total_reconciles": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(source_invoice_billed_cost)
                FROM {mart}.mart_ai_application_cost`
              )
              -
              (
                SELECT SUM(invoice_billed_cost)
                FROM {core}.fct_ai_cost_reconciliation`
              )
            ) <= 0.000001,
            0,
            1
          ) AS violation_count
        """,
        "source_reported_total_reconciles": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(source_provider_reported_cost)
                FROM {mart}.mart_ai_application_cost`
              )
              -
              (
                SELECT SUM(provider_reported_cost)
                FROM {core}.fct_ai_cost_reconciliation`
              )
            ) <= 0.000001,
            0,
            1
          ) AS violation_count
        """,
        "source_usage_estimate_reconciles": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(source_usage_cost_estimate)
                FROM {mart}.mart_ai_application_cost`
                WHERE line_item_type = 'usage'
              )
              -
              (
                SELECT SUM(usage_cost_estimate)
                FROM {core}.fct_ai_cost_reconciliation`
                WHERE line_item_type = 'usage'
              )
            ) <= 0.000001,
            0,
            1
          ) AS violation_count
        """,
        "invoice_allocation_reconciles_by_scope": f"""
          SELECT COUNT(*) AS violation_count
          FROM (
            SELECT
              financial_source_scope_id,
              SUM(source_invoice_billed_cost) AS source_cost,
              SUM(allocated_invoice_billed_cost)
                + SUM(unallocated_invoice_billed_cost) AS distributed_cost
            FROM {mart}.mart_ai_application_cost`
            GROUP BY financial_source_scope_id
            HAVING ABS(source_cost - distributed_cost) > 0.000001
          )
        """,
        "reported_allocation_reconciles_by_scope": f"""
          SELECT COUNT(*) AS violation_count
          FROM (
            SELECT
              financial_source_scope_id,
              SUM(source_provider_reported_cost) AS source_cost,
              SUM(allocated_provider_reported_cost)
                + SUM(unallocated_provider_reported_cost)
                  AS distributed_cost
            FROM {mart}.mart_ai_application_cost`
            GROUP BY financial_source_scope_id
            HAVING ABS(source_cost - distributed_cost) > 0.000001
          )
        """,
        "usage_estimate_allocation_reconciles_by_scope": f"""
          SELECT COUNT(*) AS violation_count
          FROM (
            SELECT
              financial_source_scope_id,
              SUM(source_usage_cost_estimate) AS source_cost,
              SUM(allocated_usage_cost_estimate)
                + SUM(unallocated_usage_cost_estimate)
                  AS distributed_cost
            FROM {mart}.mart_ai_application_cost`
            WHERE line_item_type = 'usage'
            GROUP BY financial_source_scope_id
            HAVING ABS(source_cost - distributed_cost) > 0.000001
          )
        """,
        "usage_driver_shares_sum_to_one": f"""
          SELECT COUNT(*) AS violation_count
          FROM (
            SELECT
              financial_source_scope_id,
              SUM(financial_allocation_share) AS allocation_share
            FROM {mart}.mart_ai_application_cost`
            WHERE line_item_type = 'usage'
              AND eligible_driver_denominator > 0
            GROUP BY financial_source_scope_id
            HAVING ABS(allocation_share - 1) > 0.000000001
          )
        """,
        "allocation_status_matches_cost_columns": f"""
          SELECT COUNTIF(
            (
              allocation_status = 'Allocated'
              AND unallocated_invoice_billed_cost != 0
            )
            OR
            (
              allocation_status = 'Unallocated'
              AND allocated_invoice_billed_cost != 0
            )
            OR
            (
              allocation_status = 'Financial scope retained'
              AND allocated_invoice_billed_cost != 0
            )
          ) AS violation_count
          FROM {mart}.mart_ai_application_cost`
        """,
        "non_usage_lines_remain_scope_retained": f"""
          SELECT COUNTIF(
            line_item_type != 'usage'
            AND (
              application_name != 'Unallocated'
              OR department_name != 'Unallocated'
              OR cost_center != 'UNALLOCATED'
              OR allocation_status != 'Financial scope retained'
              OR allocation_method != 'scope_retained'
              OR allocated_invoice_billed_cost != 0
            )
          ) AS violation_count
          FROM {mart}.mart_ai_application_cost`
        """,
        "every_usage_financial_scope_is_represented": f"""
          SELECT COUNT(*) AS violation_count
          FROM (
            SELECT DISTINCT
              billing_month,
              provider,
              provider_project_id,
              model,
              line_item_scope,
              line_item_type
            FROM {core}.fct_ai_cost_reconciliation`
            WHERE line_item_type = 'usage'
          ) AS source
          LEFT JOIN (
            SELECT DISTINCT
              billing_month,
              provider,
              provider_project_id,
              model,
              line_item_scope,
              line_item_type
            FROM {mart}.mart_ai_application_cost`
            WHERE line_item_type = 'usage'
          ) AS target
          USING (
            billing_month,
            provider,
            provider_project_id,
            model,
            line_item_scope,
            line_item_type
          )
          WHERE target.provider IS NULL
        """,
        "line_item_type_totals_reconcile": f"""
          SELECT COUNT(*) AS violation_count
          FROM (
            SELECT
              line_item_type,
              SUM(invoice_billed_cost) AS source_cost
            FROM {core}.fct_ai_cost_reconciliation`
            GROUP BY line_item_type
          ) AS source
          FULL OUTER JOIN (
            SELECT
              line_item_type,
              SUM(allocated_invoice_billed_cost)
                + SUM(unallocated_invoice_billed_cost)
                  AS distributed_cost
            FROM {mart}.mart_ai_application_cost`
            GROUP BY line_item_type
          ) AS target
          USING (line_item_type)
          WHERE ABS(
            COALESCE(source.source_cost, 0)
            - COALESCE(target.distributed_cost, 0)
          ) > 0.000001
        """,
        "unallocated_cost_is_visible": f"""
          SELECT IF(
            COUNTIF(
              allocation_status IN (
                'Unallocated',
                'Financial scope retained'
              )
            ) > 0,
            0,
            1
          ) AS violation_count
          FROM {mart}.mart_ai_application_cost`
        """,
        "allocation_confidence_is_visible": f"""
          SELECT IF(
            COUNTIF(allocation_confidence = 'medium') > 0,
            0,
            1
          ) AS violation_count
          FROM {mart}.mart_ai_application_cost`
        """,
        "currency_basis_and_synthetic_flag_are_valid": f"""
          SELECT COUNTIF(
            billing_currency != 'USD'
            OR financial_basis != 'invoice_billed_cost'
            OR NOT is_synthetic
          ) AS violation_count
          FROM {mart}.mart_ai_application_cost`
        """,
    }


def ensure_control_table(
    client: bigquery.Client,
    project_id: str,
) -> None:
    table = bigquery.Table(
        f"{project_id}.llm_finops_control.m12_application_cost_control_result",
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


def application_cost_summary(
    client: bigquery.Client,
    project_id: str,
    location: str,
) -> dict[str, Any]:
    sql = f"""
      SELECT
        COUNT(*) AS application_cost_rows,
        COUNT(DISTINCT financial_source_scope_id)
          AS financial_source_scopes,
        SUM(source_invoice_billed_cost) AS source_invoice_billed_cost,
        SUM(allocated_invoice_billed_cost)
          AS allocated_invoice_billed_cost,
        SUM(unallocated_invoice_billed_cost)
          AS unallocated_invoice_billed_cost,
        SUM(
          IF(
            line_item_type = 'usage',
            unallocated_invoice_billed_cost,
            0
          )
        ) AS unallocated_usage_invoice_cost,
        SUM(
          IF(
            line_item_type != 'usage',
            unallocated_invoice_billed_cost,
            0
          )
        ) AS scope_retained_non_usage_invoice_cost,
        SAFE_DIVIDE(
          SUM(
            IF(
              line_item_type = 'usage',
              unallocated_invoice_billed_cost,
              0
            )
          ),
          SUM(
            IF(
              line_item_type = 'usage',
              source_invoice_billed_cost,
              0
            )
          )
        ) AS unallocated_usage_invoice_pct,
        COUNTIF(allocation_confidence = 'medium')
          AS medium_confidence_rows,
        COUNTIF(is_historical_restatement)
          AS historical_restatement_rows
      FROM `{project_id}.llm_finops_mart.mart_ai_application_cost`
    """
    rows = list(client.query(sql, location=location).result())
    if len(rows) != 1:
        raise RuntimeError("M12 summary query did not return exactly one row.")
    return {
        key: json_safe(value)
        for key, value in dict(rows[0].items()).items()
    }


def deploy_m12(
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
        f"{project_id}.llm_finops_control.m12_application_cost_control_result",
        control_rows,
    )
    if insert_errors:
        raise RuntimeError(
            f"Could not write M12 control results: {insert_errors}"
        )

    failed = [row for row in control_rows if row["status"] != "PASS"]
    if failed:
        raise RuntimeError(f"M12 controls failed: {failed}")

    summary = application_cost_summary(client, project_id, location)
    completed_at = datetime.now(timezone.utc)

    manifest = {
        "pipeline_run_id": pipeline_run_id,
        "pipeline_name": "M12_APPLICATION_COST_CHARGEBACK",
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
        / "m12_application_cost_manifest.json"
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
                "pipeline_name": "M12_APPLICATION_COST_CHARGEBACK",
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "status": "PASS",
                "loaded_table_count": len(config["expected_objects"]),
                "error_message": None,
            }
        ],
    )
    if run_errors:
        raise RuntimeError(f"Could not write M12 pipeline log: {run_errors}")

    return manifest
