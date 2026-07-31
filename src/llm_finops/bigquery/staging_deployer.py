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
    raw = f"`{project_id}.{datasets['raw']}"
    staging = f"`{project_id}.{datasets['staging']}"

    return {
        "normalized_row_count_matches_raw": f"""
          SELECT ABS(
            (SELECT COUNT(*) FROM {staging}.stg_ai_provider_usage_normalized`)
            -
            (SELECT COUNT(*) FROM {raw}.raw_ai_provider_usage`)
          ) AS violation_count
        """,
        "normalized_source_key_is_unique": f"""
          SELECT COUNT(*) - COUNT(DISTINCT source_usage_key) AS violation_count
          FROM {staging}.stg_ai_provider_usage_normalized`
        """,
        "every_usage_row_resolves_one_model_map": f"""
          SELECT COUNTIF(model_map_match_count != 1) AS violation_count
          FROM {staging}.stg_ai_provider_usage_normalized`
        """,
        "every_usage_row_resolves_one_service_tier": f"""
          SELECT COUNTIF(service_tier_match_count != 1) AS violation_count
          FROM {staging}.stg_ai_provider_usage_normalized`
        """,
        "all_normalized_tokens_are_valid": f"""
          SELECT COUNTIF(token_validation_status != 'Valid') AS violation_count
          FROM {staging}.stg_ai_provider_usage_normalized`
        """,
        "every_usage_row_resolves_one_rate": f"""
          SELECT COUNTIF(rate_match_count != 1) AS violation_count
          FROM {staging}.stg_ai_provider_usage_priced`
        """,
        "all_usage_rows_are_priced": f"""
          SELECT COUNTIF(
            pricing_status != 'Priced'
            OR usage_cost_estimate IS NULL
            OR usage_cost_estimate < 0
          ) AS violation_count
          FROM {staging}.stg_ai_provider_usage_priced`
        """,
        "historical_rate_window_contains_usage_date": f"""
          SELECT COUNTIF(
            usage_date NOT BETWEEN rate_effective_start AND rate_effective_end
          ) AS violation_count
          FROM {staging}.stg_ai_provider_usage_priced`
        """,
        "historical_model_window_contains_usage_date": f"""
          SELECT COUNTIF(
            usage_date NOT BETWEEN
              model_map_effective_start AND model_map_effective_end
          ) AS violation_count
          FROM {staging}.stg_ai_provider_usage_priced`
        """,
        "priced_usage_is_usd": f"""
          SELECT COUNTIF(rate_currency != 'USD') AS violation_count
          FROM {staging}.stg_ai_provider_usage_priced`
        """,
        "staged_cost_row_count_matches_raw": f"""
          SELECT ABS(
            (SELECT COUNT(*) FROM {staging}.stg_ai_provider_cost`)
            -
            (SELECT COUNT(*) FROM {raw}.raw_ai_provider_cost`)
          ) AS violation_count
        """,
        "staged_cost_is_usd": f"""
          SELECT COUNTIF(financial_validation_status != 'Valid')
            AS violation_count
          FROM {staging}.stg_ai_provider_cost`
        """,
        "staged_telemetry_row_count_matches_raw": f"""
          SELECT ABS(
            (SELECT COUNT(*) FROM {staging}.stg_ai_request_telemetry`)
            -
            (SELECT COUNT(*) FROM {raw}.fct_ai_request_telemetry`)
          ) AS violation_count
        """,
        "staged_telemetry_tokens_are_valid": f"""
          SELECT COUNTIF(telemetry_validation_status != 'Valid')
            AS violation_count
          FROM {staging}.stg_ai_request_telemetry`
        """,
    }


SPEC = SqlPipelineSpec(
    pipeline_name="M7_STAGING_NORMALIZATION_PRICING",
    control_table="m7_staging_control_result",
    manifest_filename="m7_staging_manifest.json",
)


@pipeline_run_guard("M7_STAGING_NORMALIZATION_PRICING")


def deploy_m7(
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
