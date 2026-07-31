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


SPEC = SqlPipelineSpec(
    pipeline_name="M10_TELEMETRY_RECONCILIATION",
    control_table="m10_telemetry_control_result",
    manifest_filename="m10_telemetry_reconciliation_manifest.json",
    summary_dataset_layer="core",
)


@pipeline_run_guard("M10_TELEMETRY_RECONCILIATION")


def deploy_m10(
    *,
    project_root: Path,
    config_path: Path,
    project_id_override: str | None = None,
) -> dict[str, Any]:
    return run_sql_pipeline(
        project_root=project_root,
        spec=SPEC,
        control_query_factory=control_queries,
        summary_builder=telemetry_summary,
    )
