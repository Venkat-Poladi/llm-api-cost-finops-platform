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
        "every_source_row_has_one_anchor": f"""
          SELECT COUNT(*) AS violation_count
          FROM (
            SELECT
              source_usage_key,
              COUNTIF(source_measure_anchor_flag) AS anchor_count
            FROM {core}.fct_ai_usage_daily`
            GROUP BY source_usage_key
            HAVING anchor_count != 1
          )
        """,
        "source_anchor_count_matches_priced_usage": f"""
          SELECT ABS(
            (
              SELECT COUNTIF(source_measure_anchor_flag)
              FROM {core}.fct_ai_usage_daily`
            )
            -
            (
              SELECT COUNT(*)
              FROM {staging}.stg_ai_provider_usage_priced`
              WHERE pricing_status = 'Priced'
            )
          ) AS violation_count
        """,
        "allocation_fact_grain_is_unique": f"""
          SELECT
            COUNT(*) - COUNT(DISTINCT usage_allocation_fact_id)
              AS violation_count
          FROM {core}.fct_ai_usage_daily`
        """,
        "distribution_percentage_equals_100_percent": f"""
          SELECT COUNT(*) AS violation_count
          FROM (
            SELECT
              source_usage_key,
              MAX(total_distribution_percentage) AS distribution_total
            FROM {core}.fct_ai_usage_daily`
            GROUP BY source_usage_key
            HAVING ABS(distribution_total - 1) > 0.000000001
          )
        """,
        "allocation_percentage_is_valid": f"""
          SELECT COUNTIF(
            allocation_percentage <= 0
            OR allocation_percentage > 1
          ) AS violation_count
          FROM {core}.fct_ai_usage_daily`
        """,
        "cost_allocation_reconciles_to_source": f"""
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
        "request_allocation_reconciles_to_source": f"""
          SELECT COUNT(*) AS violation_count
          FROM (
            SELECT
              source_usage_key,
              SUM(source_request_count) AS source_requests,
              SUM(allocated_request_count)
                + SUM(unallocated_request_count) AS distributed_requests
            FROM {core}.fct_ai_usage_daily`
            GROUP BY source_usage_key
            HAVING ABS(source_requests - distributed_requests) > 0.000000001
          )
        """,
        "input_token_allocation_reconciles_to_source": f"""
          SELECT COUNT(*) AS violation_count
          FROM (
            SELECT
              source_usage_key,
              SUM(source_total_input_tokens) AS source_tokens,
              SUM(allocated_total_input_tokens)
                + SUM(unallocated_total_input_tokens) AS distributed_tokens
            FROM {core}.fct_ai_usage_daily`
            GROUP BY source_usage_key
            HAVING ABS(source_tokens - distributed_tokens) > 0.000000001
          )
        """,
        "output_token_allocation_reconciles_to_source": f"""
          SELECT COUNT(*) AS violation_count
          FROM (
            SELECT
              source_usage_key,
              SUM(source_output_tokens) AS source_tokens,
              SUM(allocated_output_tokens)
                + SUM(unallocated_output_tokens) AS distributed_tokens
            FROM {core}.fct_ai_usage_daily`
            GROUP BY source_usage_key
            HAVING ABS(source_tokens - distributed_tokens) > 0.000000001
          )
        """,
        "reasoning_token_allocation_reconciles_to_source": f"""
          SELECT COUNT(*) AS violation_count
          FROM (
            SELECT
              source_usage_key,
              SUM(source_reasoning_tokens) AS source_tokens,
              SUM(allocated_reasoning_tokens)
                + SUM(unallocated_reasoning_tokens) AS distributed_tokens
            FROM {core}.fct_ai_usage_daily`
            GROUP BY source_usage_key
            HAVING ABS(source_tokens - distributed_tokens) > 0.000000001
          )
        """,
        "source_cost_total_matches_priced_usage": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(source_usage_cost_estimate)
                FROM {core}.fct_ai_usage_daily`
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
        "shared_key_has_60_30_10_split": f"""
          SELECT COUNT(*) AS violation_count
          FROM (
            SELECT
              source_usage_key,
              MAX(IF(application_name = 'Campaign Assistant',
                allocation_percentage, NULL)) AS campaign_pct,
              MAX(IF(application_name = 'Growth Experiment Assistant',
                allocation_percentage, NULL)) AS experiment_pct,
              MAX(IF(allocation_status = 'Unallocated',
                allocation_percentage, NULL)) AS unallocated_pct
            FROM {core}.fct_ai_usage_daily`
            WHERE api_key_id = 'oa-key-shared'
            GROUP BY source_usage_key
            HAVING
              ABS(campaign_pct - 0.60) > 0.000000001
              OR ABS(experiment_pct - 0.30) > 0.000000001
              OR ABS(unallocated_pct - 0.10) > 0.000000001
          )
        """,
        "developer_ownership_change_is_respected": f"""
          SELECT COUNTIF(
            api_key_id = 'an-key-developer'
            AND allocation_status = 'Allocated'
            AND (
              (usage_date < DATE '2026-01-01' AND cost_center != 'CC400')
              OR
              (usage_date >= DATE '2026-01-01' AND cost_center != 'CC410')
            )
          ) AS violation_count
          FROM {core}.fct_ai_usage_daily`
        """,
        "late_mapping_is_flagged_as_restatement": f"""
          SELECT COUNTIF(
            api_key_id = 'an-key-lab'
            AND usage_date < DATE '2026-02-01'
            AND allocation_status = 'Allocated'
            AND NOT is_historical_restatement
          ) AS violation_count
          FROM {core}.fct_ai_usage_daily`
        """,
        "unmapped_key_is_fully_unallocated": f"""
          SELECT COUNTIF(
            api_key_id = 'an-key-unmapped'
            AND (
              allocation_status != 'Unallocated'
              OR ABS(allocation_percentage - 1) > 0.000000001
              OR application_name != 'Unallocated'
              OR cost_center != 'UNALLOCATED'
            )
          ) AS violation_count
          FROM {core}.fct_ai_usage_daily`
        """,
        "all_rows_are_usd_and_synthetic": f"""
          SELECT COUNTIF(
            billing_currency != 'USD'
            OR NOT is_synthetic
          ) AS violation_count
          FROM {core}.fct_ai_usage_daily`
        """,
    }


def allocation_summary(
    client: bigquery.Client,
    project_id: str,
    core_dataset: str,
    location: str,
) -> dict[str, Any]:
    sql = f"""
      SELECT
        COUNT(*) AS allocation_rows,
        COUNTIF(source_measure_anchor_flag) AS source_usage_rows,
        COUNTIF(allocation_status = 'Allocated') AS allocated_rows,
        COUNTIF(allocation_status = 'Unallocated') AS unallocated_rows,
        SUM(source_usage_cost_estimate) AS source_usage_cost_estimate,
        SUM(allocated_usage_cost_estimate) AS allocated_usage_cost_estimate,
        SUM(unallocated_usage_cost_estimate) AS unallocated_usage_cost_estimate,
        SAFE_DIVIDE(
          SUM(unallocated_usage_cost_estimate),
          SUM(source_usage_cost_estimate)
        ) AS unallocated_cost_pct,
        COUNTIF(is_historical_restatement) AS restated_allocation_rows
      FROM `{project_id}.{core_dataset}.fct_ai_usage_daily`
    """
    rows = list(client.query(sql, location=location).result())
    if len(rows) != 1:
        raise RuntimeError("M9 summary query did not return exactly one row.")
    return {
        key: json_safe(value)
        for key, value in dict(rows[0].items()).items()
    }


SPEC = SqlPipelineSpec(
    pipeline_name="M9_DAILY_USAGE_ALLOCATION",
    control_table="m9_allocation_control_result",
    manifest_filename="m9_allocation_manifest.json",
    summary_dataset_layer="core",
)


@pipeline_run_guard("M9_DAILY_USAGE_ALLOCATION")


def deploy_m9(
    *,
    project_root: Path,
    config_path: Path,
    project_id_override: str | None = None,
) -> dict[str, Any]:
    return run_sql_pipeline(
        project_root=project_root,
        spec=SPEC,
        control_query_factory=control_queries,
        summary_builder=allocation_summary,
    )
