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


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing M7 configuration: {path}")
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
    }

    sql = path.read_text(encoding="utf-8")

    for placeholder, value in replacements.items():
        sql = sql.replace(placeholder, value)

    return sql


def query_scalar(
    client: bigquery.Client,
    sql: str,
    location: str,
) -> int:
    rows = list(client.query(sql, location=location).result())
    if len(rows) != 1:
        raise RuntimeError("Control query did not return exactly one row.")
    return int(rows[0]["violation_count"])


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


def ensure_control_table(
    client: bigquery.Client,
    project_id: str,
    control_dataset: str,
) -> None:
    table = bigquery.Table(
        f"{project_id}.{control_dataset}.m7_staging_control_result",
        schema=[
            bigquery.SchemaField("pipeline_run_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("control_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("violation_count", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("checked_at", "TIMESTAMP", mode="REQUIRED"),
        ],
    )
    client.create_table(table, exists_ok=True)


@pipeline_run_guard("M7_STAGING_NORMALIZATION_PRICING")
def deploy_m7(
    *,
    project_root: Path,
    config_path: Path,
    project_id_override: str | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    project_id = project_id_override or config["project_id"]
    location = config["location"]
    datasets = config["datasets"]
    client = bigquery.Client(project=project_id)

    pipeline_run_id = current_pipeline_run_id()
    started_at = current_pipeline_started_at()

    for relative_path in config["sql_files"]:
        sql_path = project_root / relative_path
        sql = render_sql(sql_path, project_id, datasets)
        client.query(sql, location=location).result()

    ensure_control_table(
        client,
        project_id,
        datasets["control"],
    )

    checked_at = datetime.now(timezone.utc)
    control_rows: list[dict[str, Any]] = []

    for control_name, sql in control_queries(
        project_id,
        datasets,
    ).items():
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

    errors = client.insert_rows_json(
        (
            f"{project_id}.{datasets['control']}."
            "m7_staging_control_result"
        ),
        control_rows,
    )
    if errors:
        raise RuntimeError(f"Could not write M7 controls: {errors}")

    failed = [row for row in control_rows if row["status"] != "PASS"]
    if failed:
        raise RuntimeError(f"M7 controls failed: {failed}")

    completed_at = datetime.now(timezone.utc)
    manifest = {
        "pipeline_run_id": pipeline_run_id,
        "pipeline_name": "M7_STAGING_NORMALIZATION_PRICING",
        "project_id": project_id,
        "location": location,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "status": "PASS",
        "created_objects": config["expected_objects"],
        "controls": control_rows,
    }

    manifest_path = (
        project_root / "data" / "generated" / "m7_staging_manifest.json"
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    run_errors = client.insert_rows_json(
        f"{project_id}.{datasets['control']}.pipeline_run_log",
        [
            {
                "pipeline_run_id": pipeline_run_id,
                "pipeline_name": "M7_STAGING_NORMALIZATION_PRICING",
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "status": "PASS",
                "loaded_table_count": len(config["expected_objects"]),
                "error_message": None,
            }
        ],
    )
    if run_errors:
        raise RuntimeError(f"Could not write M7 pipeline log: {run_errors}")

    return manifest
