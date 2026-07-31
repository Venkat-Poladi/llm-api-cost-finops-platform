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


def application_cost_summary(
    client: bigquery.Client,
    project_id: str,
    mart_dataset: str,
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
      FROM `{project_id}.{mart_dataset}.mart_ai_application_cost`
    """
    rows = list(client.query(sql, location=location).result())
    if len(rows) != 1:
        raise RuntimeError("M12 summary query did not return exactly one row.")
    return {
        key: json_safe(value)
        for key, value in dict(rows[0].items()).items()
    }


SPEC = SqlPipelineSpec(
    pipeline_name="M12_APPLICATION_COST_CHARGEBACK",
    control_table="m12_application_cost_control_result",
    manifest_filename="m12_application_cost_manifest.json",
    summary_dataset_layer="mart",
)


@pipeline_run_guard("M12_APPLICATION_COST_CHARGEBACK")


def deploy_m12(
    *,
    project_root: Path,
    config_path: Path,
    project_id_override: str | None = None,
) -> dict[str, Any]:
    return run_sql_pipeline(
        project_root=project_root,
        spec=SPEC,
        control_query_factory=control_queries,
        summary_builder=application_cost_summary,
    )
