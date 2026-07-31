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
    core = f"`{project_id}.{datasets['core']}"
    mart = f"`{project_id}.{datasets['mart']}"

    return {
        "unit_economics_grain_is_unique": f"""
          SELECT
            COUNT(*) - COUNT(DISTINCT unit_economics_id)
              AS violation_count
          FROM {mart}.mart_ai_unit_economics`
        """,
        "every_token_economics_row_is_represented": f"""
          SELECT ABS(
            (
              SELECT COUNT(*)
              FROM {mart}.mart_ai_unit_economics`
            )
            -
            (
              SELECT COUNT(*)
              FROM {mart}.mart_ai_token_economics`
            )
          ) AS violation_count
        """,
        "estimated_usage_cost_reconciles": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(usage_cost_estimate)
                FROM {mart}.mart_ai_unit_economics`
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
        "invoice_usage_cost_reconciles": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(invoice_billed_usage_cost)
                FROM {mart}.mart_ai_unit_economics`
              )
              -
              (
                SELECT SUM(invoice_billed_cost)
                FROM {core}.fct_ai_cost_reconciliation`
                WHERE line_item_type = 'usage'
              )
            ) <= 0.000001,
            0,
            1
          ) AS violation_count
        """,
        "provider_reported_usage_cost_reconciles": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(provider_reported_usage_cost)
                FROM {mart}.mart_ai_unit_economics`
              )
              -
              (
                SELECT SUM(provider_reported_cost)
                FROM {core}.fct_ai_cost_reconciliation`
                WHERE line_item_type = 'usage'
              )
            ) <= 0.000001,
            0,
            1
          ) AS violation_count
        """,
        "request_and_token_totals_reconcile": f"""
          SELECT IF(
            (
              SELECT SUM(provider_request_count)
              FROM {mart}.mart_ai_unit_economics`
            )
            =
            (
              SELECT SUM(request_count)
              FROM {mart}.mart_ai_token_economics`
            )
            AND
            (
              SELECT SUM(total_tokens)
              FROM {mart}.mart_ai_unit_economics`
            )
            =
            (
              SELECT SUM(total_tokens)
              FROM {mart}.mart_ai_token_economics`
            ),
            0,
            1
          ) AS violation_count
        """,
        "telemetry_counts_reconcile": f"""
          SELECT IF(
            (
              SELECT SUM(telemetry_attempt_count)
              FROM {mart}.mart_ai_unit_economics`
            )
            =
            (
              SELECT SUM(telemetry_attempt_count)
              FROM {mart}.mart_ai_token_economics`
            )
            AND
            (
              SELECT SUM(telemetry_logical_request_count)
              FROM {mart}.mart_ai_unit_economics`
            )
            =
            (
              SELECT SUM(telemetry_logical_request_count)
              FROM {mart}.mart_ai_token_economics`
            )
            AND
            (
              SELECT SUM(successful_logical_request_count)
              FROM {mart}.mart_ai_unit_economics`
            )
            =
            (
              SELECT SUM(successful_logical_request_count)
              FROM {mart}.mart_ai_token_economics`
            ),
            0,
            1
          ) AS violation_count
        """,
        "provider_request_unit_cost_formula_is_correct": f"""
          SELECT COUNTIF(
            (
              provider_request_count = 0
              AND invoice_cost_per_provider_request IS NOT NULL
            )
            OR
            (
              provider_request_count > 0
              AND ABS(
                invoice_cost_per_provider_request
                - invoice_billed_usage_cost / provider_request_count
              ) > 0.000000001
            )
          ) AS violation_count
          FROM {mart}.mart_ai_unit_economics`
        """,
        "million_token_unit_cost_formula_is_correct": f"""
          SELECT COUNTIF(
            (
              total_tokens = 0
              AND invoice_cost_per_million_total_tokens IS NOT NULL
            )
            OR
            (
              total_tokens > 0
              AND ABS(
                invoice_cost_per_million_total_tokens
                - invoice_billed_usage_cost * 1000000 / total_tokens
              ) > 0.000000001
            )
          ) AS violation_count
          FROM {mart}.mart_ai_unit_economics`
        """,
        "insufficient_coverage_withholds_governed_metrics": f"""
          SELECT COUNTIF(
            NOT telemetry_quality_gate_passed
            AND (
              governed_invoice_cost_per_logical_request IS NOT NULL
              OR governed_invoice_cost_per_successful_request IS NOT NULL
              OR governed_retry_cost_per_successful_request IS NOT NULL
              OR measurement_quality_status != 'INSUFFICIENT'
              OR unit_economics_status != 'LIMITED_TELEMETRY'
            )
          ) AS violation_count
          FROM {mart}.mart_ai_unit_economics`
        """,
        "sufficient_coverage_publishes_valid_metrics": f"""
          SELECT COUNTIF(
            telemetry_quality_gate_passed
            AND (
              measurement_quality_status != 'SUFFICIENT'
              OR unit_economics_status != 'PUBLISHABLE'
              OR (
                telemetry_logical_request_count > 0
                AND governed_invoice_cost_per_logical_request IS NULL
              )
              OR (
                successful_logical_request_count > 0
                AND governed_invoice_cost_per_successful_request IS NULL
              )
            )
          ) AS violation_count
          FROM {mart}.mart_ai_unit_economics`
        """,
        "observed_rates_are_null_or_between_zero_and_one": f"""
          SELECT COUNTIF(
            observed_success_rate < 0
            OR observed_success_rate > 1
            OR observed_retry_attempt_rate < 0
            OR observed_retry_attempt_rate > 1
            OR observed_failed_attempt_rate < 0
            OR observed_failed_attempt_rate > 1
          ) AS violation_count
          FROM {mart}.mart_ai_unit_economics`
        """,
        "attempts_per_logical_request_is_valid": f"""
          SELECT COUNTIF(
            (
              telemetry_logical_request_count = 0
              AND observed_attempts_per_logical_request IS NOT NULL
            )
            OR
            (
              telemetry_logical_request_count > 0
              AND observed_attempts_per_logical_request < 1
            )
          ) AS violation_count
          FROM {mart}.mart_ai_unit_economics`
        """,
        "retry_and_failure_costs_are_valid": f"""
          SELECT COUNTIF(
            estimated_retry_cost < 0
            OR estimated_failed_attempt_cost < 0
            OR estimated_retry_cost
              > telemetry_usage_cost_estimate + 0.000001
            OR estimated_failed_attempt_cost
              > telemetry_usage_cost_estimate + 0.000001
          ) AS violation_count
          FROM {mart}.mart_ai_unit_economics`
        """,
        "measurement_status_matches_coverage_gate": f"""
          SELECT COUNTIF(
            telemetry_quality_gate_passed
              != (
                telemetry_token_coverage_pct BETWEEN 0.95 AND 1.05
              )
          ) AS violation_count
          FROM {mart}.mart_ai_unit_economics`
        """,
        "basis_currency_and_synthetic_flag_are_valid": f"""
          SELECT COUNTIF(
            financial_basis != 'invoice_billed_cost_usage_lines'
            OR operational_cost_basis != 'usage_cost_estimate'
            OR billing_currency != 'USD'
            OR retry_and_failure_cost_label
              != 'Estimated from request telemetry'
            OR NOT is_synthetic
          ) AS violation_count
          FROM {mart}.mart_ai_unit_economics`
        """,
    }


def unit_economics_summary(
    client: bigquery.Client,
    project_id: str,
    mart_dataset: str,
    location: str,
) -> dict[str, Any]:
    sql = f"""
      SELECT
        COUNT(*) AS unit_economics_rows,
        COUNTIF(measurement_quality_status = 'SUFFICIENT')
          AS sufficient_measurement_rows,
        COUNTIF(measurement_quality_status = 'INSUFFICIENT')
          AS insufficient_measurement_rows,
        SUM(provider_request_count) AS provider_request_count,
        SUM(telemetry_logical_request_count)
          AS telemetry_logical_request_count,
        SUM(successful_logical_request_count)
          AS successful_logical_request_count,
        SUM(invoice_billed_usage_cost) AS invoice_billed_usage_cost,
        SAFE_DIVIDE(
          SUM(invoice_billed_usage_cost),
          SUM(provider_request_count)
        ) AS portfolio_invoice_cost_per_provider_request,
        SAFE_DIVIDE(
          SUM(invoice_billed_usage_cost) * 1000000,
          SUM(total_tokens)
        ) AS portfolio_invoice_cost_per_million_total_tokens,
        SUM(estimated_retry_cost) AS estimated_retry_cost,
        SUM(estimated_failed_attempt_cost)
          AS estimated_failed_attempt_cost,
        SUM(untraceable_provider_usage_cost_estimate)
          AS untraceable_provider_usage_cost_estimate
      FROM `{project_id}.{mart_dataset}.mart_ai_unit_economics`
    """
    rows = list(client.query(sql, location=location).result())
    if len(rows) != 1:
        raise RuntimeError("M14 summary query did not return exactly one row.")
    return {
        key: json_safe(value)
        for key, value in dict(rows[0].items()).items()
    }


SPEC = SqlPipelineSpec(
    pipeline_name="M14_UNIT_ECONOMICS",
    control_table="m14_unit_economics_control_result",
    manifest_filename="m14_unit_economics_manifest.json",
    summary_dataset_layer="mart",
)


@pipeline_run_guard("M14_UNIT_ECONOMICS")


def deploy_m14(
    *,
    project_root: Path,
    config_path: Path,
    project_id_override: str | None = None,
) -> dict[str, Any]:
    return run_sql_pipeline(
        project_root=project_root,
        spec=SPEC,
        control_query_factory=control_queries,
        summary_builder=unit_economics_summary,
    )
