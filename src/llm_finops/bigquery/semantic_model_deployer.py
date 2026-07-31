from __future__ import annotations

from pathlib import Path
from typing import Any

from llm_finops.bigquery.deployment_runner import (
    SqlPipelineSpec,
    run_sql_pipeline,
)
from llm_finops.bigquery.pipeline_logging import pipeline_run_guard


def control_queries(
    project_id: str,
    datasets: dict[str, str],
) -> dict[str, str]:
    mart = f"`{project_id}.{datasets['mart']}"

    return {
        "date_dimension_is_unique_and_complete": f"""
          SELECT
            (
              SELECT COUNT(*) - COUNT(DISTINCT date_key)
              FROM {mart}.dim_ai_date`
            )
            +
            ABS(
              (
                SELECT COUNT(*)
                FROM {mart}.dim_ai_date`
              )
              -
              DATE_DIFF(DATE '2026-06-30', DATE '2025-01-01', DAY)
              - 1
            ) AS violation_count
        """,
        "provider_dimension_key_is_unique": f"""
          SELECT COUNT(*) - COUNT(DISTINCT provider_key) AS violation_count
          FROM {mart}.dim_ai_provider`
        """,
        "model_dimension_key_is_unique": f"""
          SELECT COUNT(*) - COUNT(DISTINCT model_key) AS violation_count
          FROM {mart}.dim_ai_model`
        """,
        "application_dimension_key_is_unique": f"""
          SELECT COUNT(*) - COUNT(DISTINCT application_key) AS violation_count
          FROM {mart}.dim_ai_application`
        """,
        "experiment_dimension_key_is_unique": f"""
          SELECT COUNT(*) - COUNT(DISTINCT experiment_key) AS violation_count
          FROM {mart}.dim_ai_experiment`
        """,
        "financial_fact_reconciles_to_application_cost": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(invoice_billed_cost)
                FROM {mart}.fact_ai_financial_monthly`
              )
              -
              (
                SELECT SUM(
                  allocated_invoice_billed_cost
                  + unallocated_invoice_billed_cost
                )
                FROM {mart}.mart_ai_application_cost`
              )
            ) <= 0.000001,
            0,
            1
          ) AS violation_count
        """,
        "usage_fact_reconciles_to_token_economics": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(usage_cost_estimate)
                FROM {mart}.fact_ai_usage_monthly`
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
        "unit_economics_fact_reconciles": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(invoice_billed_usage_cost)
                FROM {mart}.fact_ai_unit_economics_monthly`
              )
              -
              (
                SELECT SUM(invoice_billed_usage_cost)
                FROM {mart}.mart_ai_unit_economics`
              )
            ) <= 0.000001,
            0,
            1
          ) AS violation_count
        """,
        "optimization_fact_reconciles": f"""
          SELECT IF(
            ABS(
              (
                SELECT SUM(identified_annualized_savings)
                FROM {mart}.fact_ai_optimization_monthly`
              )
              -
              (
                SELECT SUM(identified_annualized_savings)
                FROM {mart}.mart_ai_optimization`
              )
            ) <= 0.000001,
            0,
            1
          ) AS violation_count
        """,
        "experiment_current_has_one_row_per_experiment": f"""
          SELECT
            COUNT(*) - COUNT(DISTINCT experiment_key) AS violation_count
          FROM {mart}.fact_ai_experiment_current`
        """,
        "all_fact_provider_keys_resolve": f"""
          SELECT
            (
              SELECT COUNT(*)
              FROM {mart}.fact_ai_financial_monthly` AS f
              LEFT JOIN {mart}.dim_ai_provider` AS d
                USING (provider_key)
              WHERE d.provider_key IS NULL
            )
            +
            (
              SELECT COUNT(*)
              FROM {mart}.fact_ai_usage_monthly` AS f
              LEFT JOIN {mart}.dim_ai_provider` AS d
                USING (provider_key)
              WHERE d.provider_key IS NULL
            )
            +
            (
              SELECT COUNT(*)
              FROM {mart}.fact_ai_unit_economics_monthly` AS f
              LEFT JOIN {mart}.dim_ai_provider` AS d
                USING (provider_key)
              WHERE d.provider_key IS NULL
            )
            +
            (
              SELECT COUNT(*)
              FROM {mart}.fact_ai_optimization_monthly` AS f
              LEFT JOIN {mart}.dim_ai_provider` AS d
                USING (provider_key)
              WHERE d.provider_key IS NULL
            ) AS violation_count
        """,
        "all_fact_model_keys_resolve": f"""
          SELECT
            (
              SELECT COUNT(*)
              FROM {mart}.fact_ai_financial_monthly` AS f
              LEFT JOIN {mart}.dim_ai_model` AS d
                USING (model_key)
              WHERE d.model_key IS NULL
            )
            +
            (
              SELECT COUNT(*)
              FROM {mart}.fact_ai_usage_monthly` AS f
              LEFT JOIN {mart}.dim_ai_model` AS d
                USING (model_key)
              WHERE d.model_key IS NULL
            )
            +
            (
              SELECT COUNT(*)
              FROM {mart}.fact_ai_unit_economics_monthly` AS f
              LEFT JOIN {mart}.dim_ai_model` AS d
                USING (model_key)
              WHERE d.model_key IS NULL
            )
            +
            (
              SELECT COUNT(*)
              FROM {mart}.fact_ai_optimization_monthly` AS f
              LEFT JOIN {mart}.dim_ai_model` AS d
                USING (model_key)
              WHERE d.model_key IS NULL
            ) AS violation_count
        """,
    }


SPEC = SqlPipelineSpec(
    pipeline_name="M17_POWER_BI_SEMANTIC_MODEL",
    control_table="m17_semantic_control_result",
    manifest_filename="m17_semantic_model_manifest.json",
)


@pipeline_run_guard("M17_POWER_BI_SEMANTIC_MODEL")


def deploy_m17(
    *,
    project_root: Path,
    config_path: Path,
    project_id_override: str | None = None,
) -> dict[str, Any]:
    return run_sql_pipeline(
        project_root=project_root,
        spec=SPEC,
        control_query_factory=control_queries,
    )
