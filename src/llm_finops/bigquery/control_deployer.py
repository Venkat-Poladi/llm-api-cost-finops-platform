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


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing configuration: {path}")
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
        "{{CONTROL_DATASET}}": datasets["control"],
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
        "{{MART_DATASET}}": datasets["mart"],
        "{{CONTROL_DATASET}}": datasets["control"],
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


def end_to_end_queries(
    project_id: str,
    datasets: dict[str, str],
) -> dict[str, str]:
    raw = f"`{project_id}.{datasets['raw']}"
    staging = f"`{project_id}.{datasets['staging']}"
    core = f"`{project_id}.{datasets['core']}"
    mart = f"`{project_id}.{datasets['mart']}"
    control = f"`{project_id}.{datasets['control']}"

    return {
        "E2E-01": f"""
          SELECT ABS(
            (SELECT COUNT(*) FROM {raw}.raw_ai_provider_usage`)
            -
            (SELECT COUNT(*) FROM {staging}.stg_ai_provider_usage_priced`)
          ) AS violation_count
        """,
        "E2E-02": f"""
          SELECT ABS(
            (SELECT COUNT(*) FROM {raw}.raw_ai_provider_cost`)
            -
            (SELECT COUNT(*) FROM {core}.fct_ai_cost_reconciliation`)
          ) AS violation_count
        """,
        "E2E-03": f"""
          SELECT ABS(
            (SELECT COUNT(*) FROM {raw}.fct_ai_request_telemetry`)
            -
            (SELECT COUNT(*) FROM {staging}.stg_ai_request_telemetry`)
          ) AS violation_count
        """,
        "E2E-04": f"""
          SELECT
            COUNT(*) - COUNT(DISTINCT TO_JSON_STRING(STRUCT(
              usage_date,
              provider,
              usage_type,
              provider_project_id,
              api_key_id,
              model,
              provider_service_tier,
              is_batch,
              context_window_tier
            ))) AS violation_count
          FROM {raw}.raw_ai_provider_usage`
        """,
        "E2E-05": f"""
          SELECT
            COUNT(*) - COUNT(DISTINCT TO_JSON_STRING(STRUCT(
              billing_period,
              provider,
              provider_project_id,
              model,
              line_item_type,
              provider_line_item_id
            ))) AS violation_count
          FROM {raw}.raw_ai_provider_cost`
        """,
        "E2E-06": f"""
          SELECT
            COUNT(*) - COUNT(DISTINCT provider_request_id)
              AS violation_count
          FROM {raw}.fct_ai_request_telemetry`
        """,
        "E2E-07": f"""
          SELECT COUNTIF(
            model_map_match_count != 1
            OR service_tier_match_count != 1
            OR rate_match_count != 1
            OR token_validation_status != 'Valid'
            OR pricing_status != 'Priced'
            OR usage_cost_estimate IS NULL
            OR usage_cost_estimate < 0
            OR usage_date NOT BETWEEN
              model_map_effective_start AND model_map_effective_end
            OR usage_date NOT BETWEEN
              rate_effective_start AND rate_effective_end
          ) AS violation_count
          FROM {staging}.stg_ai_provider_usage_priced`
        """,
        "E2E-08": f"""
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
                FROM {staging}.stg_ai_provider_usage_priced`
                WHERE pricing_status = 'Priced'
              )
            ) <= 0.000001,
            0,
            1
          ) AS violation_count
        """,
        "E2E-09": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(provider_reported_cost)
                FROM {core}.fct_ai_cost_reconciliation`
              )
              -
              (
                SELECT SUM(provider_reported_cost)
                FROM {raw}.raw_ai_provider_cost`
              )
            ) <= 0.000001,
            0,
            1
          ) AS violation_count
        """,
        "E2E-10": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(invoice_billed_cost)
                FROM {core}.fct_ai_cost_reconciliation`
              )
              -
              (
                SELECT SUM(invoice_billed_cost)
                FROM {raw}.raw_ai_provider_cost`
              )
            ) <= 0.000001,
            0,
            1
          ) AS violation_count
        """,
        "E2E-11": f"""
          SELECT COUNT(*) AS violation_count
          FROM (
            SELECT
              source_usage_key,
              SUM(source_usage_cost_estimate) AS source_cost,
              SUM(allocated_usage_cost_estimate)
                + SUM(unallocated_usage_cost_estimate) AS distributed_cost
            FROM {core}.fct_ai_usage_daily`
            GROUP BY source_usage_key
            HAVING ABS(source_cost - distributed_cost) > 0.000000001
          )
        """,
        "E2E-12": f"""
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
        "E2E-13": f"""
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
            ) <= 0.000001
            AND
            (
              SELECT SUM(total_tokens)
              FROM {mart}.mart_ai_token_economics`
            )
            =
            (
              SELECT SUM(
                normalized_total_input_tokens + output_tokens
              )
              FROM {staging}.stg_ai_provider_usage_priced`
              WHERE pricing_status = 'Priced'
            ),
            0,
            1
          ) AS violation_count
        """,
        "E2E-14": f"""
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
        "E2E-15": f"""
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
        "E2E-16": f"""
          SELECT
            (
              SELECT IF(
                ABS(
                  SUM(invoice_billed_usage_cost)
                  -
                  (
                    SELECT SUM(invoice_billed_cost)
                    FROM {core}.fct_ai_cost_reconciliation`
                    WHERE line_item_type = 'usage'
                  )
                ) <= 0.000001,
                0,
                1
              )
              FROM {mart}.mart_ai_unit_economics`
            )
            +
            (
              SELECT COUNTIF(
                measurement_quality_status = 'INSUFFICIENT'
                AND (
                  governed_invoice_cost_per_logical_request IS NOT NULL
                  OR governed_invoice_cost_per_successful_request IS NOT NULL
                  OR governed_retry_cost_per_successful_request IS NOT NULL
                )
              )
              FROM {mart}.mart_ai_unit_economics`
            ) AS violation_count
        """,
        "E2E-17": f"""
          SELECT
            (
              SELECT COUNT(*)
              FROM {raw}.dim_ai_experiment_control` AS c
              LEFT JOIN (
                SELECT DISTINCT experiment_id
                FROM {mart}.mart_ai_experiments`
              ) AS m
              USING (experiment_id)
              WHERE m.experiment_id IS NULL
            )
            +
            (
              SELECT COUNTIF(
                governance_exception_status = 'EXCEPTION'
                AND governance_exception_reason IS NULL
              )
              FROM {mart}.mart_ai_experiments`
            ) AS violation_count
        """,
        "E2E-18": f"""
          WITH expected AS (
            SELECT pipeline_name
            FROM UNNEST([
              'M6_BIGQUERY_RAW_LAYER',
              'M7_STAGING_NORMALIZATION_PRICING',
              'M8_MONTHLY_COST_RECONCILIATION',
              'M9_DAILY_USAGE_ALLOCATION',
              'M10_TELEMETRY_RECONCILIATION',
              'M11_TOKEN_ECONOMICS',
              'M12_APPLICATION_COST_CHARGEBACK',
              'M13_OPTIMIZATION_EVALUATION_GATE',
              'M14_UNIT_ECONOMICS',
              'M15_EXPERIMENT_GOVERNANCE'
            ]) AS pipeline_name
          ),
          latest AS (
            SELECT
              pipeline_name,
              status,
              ROW_NUMBER() OVER (
                PARTITION BY pipeline_name
                ORDER BY completed_at DESC, pipeline_run_id DESC
              ) AS latest_row_number
            FROM {control}.pipeline_run_log`
          )
          SELECT COUNTIF(
            l.pipeline_name IS NULL OR l.status != 'PASS'
          ) AS violation_count
          FROM expected AS e
          LEFT JOIN latest AS l
            ON e.pipeline_name = l.pipeline_name
            AND l.latest_row_number = 1
        """,
    }


def replace_control_catalog(
    client: bigquery.Client,
    project_id: str,
    control_dataset: str,
    controls: list[dict[str, Any]],
) -> None:
    table_id = f"{project_id}.{control_dataset}.dim_ai_control_catalog"
    client.delete_table(table_id, not_found_ok=True)
    table = bigquery.Table(
        table_id,
        schema=[
            bigquery.SchemaField("control_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("control_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("control_domain", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("severity", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("data_layer", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("description", "STRING", mode="REQUIRED"),
        ],
    )
    client.create_table(table)
    errors = client.insert_rows_json(table_id, controls)
    if errors:
        raise RuntimeError(f"Could not write control catalog: {errors}")


def ensure_result_table(
    client: bigquery.Client,
    project_id: str,
    control_dataset: str,
) -> None:
    table = bigquery.Table(
        f"{project_id}.{control_dataset}.m16_end_to_end_control_result",
        schema=[
            bigquery.SchemaField("pipeline_run_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("control_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("violation_count", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("checked_at", "TIMESTAMP", mode="REQUIRED"),
        ],
    )
    client.create_table(table, exists_ok=True)


@pipeline_run_guard("M16_AUTOMATED_CONTROLS_CI")
def deploy_m16(
    *,
    project_root: Path,
    config_path: Path,
    registry_path: Path,
    project_id_override: str | None = None,
) -> dict[str, Any]:
    config = load_yaml(config_path)
    registry = load_yaml(registry_path)
    project_id = project_id_override or config["project_id"]
    location = config["location"]
    datasets = config["datasets"]
    client = bigquery.Client(project=project_id)

    catalog_rows = registry["controls"]
    query_map = end_to_end_queries(project_id, datasets)
    catalog_ids = [row["control_id"] for row in catalog_rows]

    if len(catalog_ids) != 18 or len(set(catalog_ids)) != 18:
        raise ValueError("The M16 control registry must contain exactly 18 unique controls.")
    if set(catalog_ids) != set(query_map):
        raise ValueError("The control registry and executable query map do not match.")

    pipeline_run_id = current_pipeline_run_id()
    started_at = current_pipeline_started_at()

    replace_control_catalog(
        client,
        project_id,
        datasets["control"],
        catalog_rows,
    )
    ensure_result_table(
        client,
        project_id,
        datasets["control"],
    )

    checked_at = datetime.now(timezone.utc)
    result_rows: list[dict[str, Any]] = []

    for control_id in catalog_ids:
        violation_count = query_scalar(
            client,
            query_map[control_id],
            location,
        )
        result_rows.append(
            {
                "pipeline_run_id": pipeline_run_id,
                "control_id": control_id,
                "violation_count": violation_count,
                "status": "PASS" if violation_count == 0 else "FAIL",
                "checked_at": checked_at.isoformat(),
            }
        )

    insert_errors = client.insert_rows_json(
        (
            f"{project_id}.{datasets['control']}."
            "m16_end_to_end_control_result"
        ),
        result_rows,
    )
    if insert_errors:
        raise RuntimeError(
            f"Could not write M16 control results: {insert_errors}"
        )

    failed = [row for row in result_rows if row["status"] != "PASS"]
    if failed:
        raise RuntimeError(f"M16 controls failed: {failed}")

    for relative_path in config["sql_files"]:
        client.query(
            render_sql(
                project_root / relative_path,
                project_id,
                datasets,
            ),
            location=location,
        ).result()

    completed_at = datetime.now(timezone.utc)
    run_errors = client.insert_rows_json(
        f"{project_id}.{datasets['control']}.pipeline_run_log",
        [
            {
                "pipeline_run_id": pipeline_run_id,
                "pipeline_name": "M16_AUTOMATED_CONTROLS_CI",
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "status": "PASS",
                "loaded_table_count": len(config["expected_objects"]),
                "error_message": None,
            }
        ],
    )
    if run_errors:
        raise RuntimeError(f"Could not write M16 pipeline log: {run_errors}")

    summary = {
        "registered_control_count": len(catalog_rows),
        "executed_control_count": len(result_rows),
        "passed_control_count": sum(
            row["status"] == "PASS" for row in result_rows
        ),
        "failed_control_count": sum(
            row["status"] == "FAIL" for row in result_rows
        ),
    }

    manifest = {
        "pipeline_run_id": pipeline_run_id,
        "pipeline_name": "M16_AUTOMATED_CONTROLS_CI",
        "project_id": project_id,
        "location": location,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "status": "PASS",
        "created_objects": [
            render_object_name(object_name, datasets)
            for object_name in config["expected_objects"]
        ],
        "controls": result_rows,
        "summary": summary,
    }

    manifest_path = (
        project_root
        / "data"
        / "generated"
        / "m16_automated_controls_manifest.json"
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest
