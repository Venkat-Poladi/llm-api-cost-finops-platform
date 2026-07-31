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
    mart = f"`{project_id}.{datasets['mart']}"

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


def token_summary(
    client: bigquery.Client,
    project_id: str,
    mart_dataset: str,
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
      FROM `{project_id}.{mart_dataset}.mart_ai_token_economics`
    """
    rows = list(client.query(sql, location=location).result())
    if len(rows) != 1:
        raise RuntimeError("M11 summary query did not return exactly one row.")
    return {
        key: json_safe(value)
        for key, value in dict(rows[0].items()).items()
    }


SPEC = SqlPipelineSpec(
    pipeline_name="M11_TOKEN_ECONOMICS",
    control_table="m11_token_control_result",
    manifest_filename="m11_token_economics_manifest.json",
    summary_dataset_layer="mart",
)


@pipeline_run_guard("M11_TOKEN_ECONOMICS")


def deploy_m11(
    *,
    project_root: Path,
    config_path: Path,
    project_id_override: str | None = None,
) -> dict[str, Any]:
    return run_sql_pipeline(
        project_root=project_root,
        spec=SPEC,
        control_query_factory=control_queries,
        summary_builder=token_summary,
    )
