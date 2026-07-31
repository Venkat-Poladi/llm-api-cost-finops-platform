from __future__ import annotations

from pathlib import Path
from typing import Any

from google.cloud import bigquery

from llm_finops.bigquery.deployment_runner import (
    SqlPipelineSpec,
    json_safe,
    run_sql_pipeline,
)
from llm_finops.bigquery.pipeline_logging import pipeline_run_guard


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


SPEC = SqlPipelineSpec(
    pipeline_name="M8_MONTHLY_COST_RECONCILIATION",
    control_table="m8_reconciliation_control_result",
    manifest_filename="m8_reconciliation_manifest.json",
    summary_dataset_layer="core",
)


@pipeline_run_guard("M8_MONTHLY_COST_RECONCILIATION")


def deploy_m8(
    *,
    project_root: Path,
    config_path: Path,
    project_id_override: str | None = None,
) -> dict[str, Any]:
    return run_sql_pipeline(
        project_root=project_root,
        spec=SPEC,
        control_query_factory=control_queries,
        summary_builder=reconciliation_summary,
    )
