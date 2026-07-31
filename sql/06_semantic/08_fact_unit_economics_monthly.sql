CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.{{MART_DATASET}}.fact_ai_unit_economics_monthly`
PARTITION BY billing_month
CLUSTER BY provider_key, model_key, measurement_quality_status
AS
WITH normalized AS (
  SELECT
    unit_economics_id,
    billing_month,
    provider,
    provider_project_id,
    COALESCE(model, 'Not applicable') AS model,
    COALESCE(model_snapshot, 'Not applicable') AS model_snapshot,
    COALESCE(usage_type, 'Not applicable') AS usage_type,
    provider_request_count,
    total_tokens,
    invoice_billed_usage_cost,
    provider_reported_usage_cost,
    usage_cost_estimate,
    telemetry_attempt_count,
    telemetry_logical_request_count,
    successful_logical_request_count,
    retry_attempt_count,
    failed_attempt_count,
    estimated_retry_cost,
    estimated_failed_attempt_cost,
    untraceable_provider_usage_cost_estimate,
    telemetry_token_coverage_pct,
    telemetry_request_coverage_pct,
    telemetry_quality_gate_passed,
    measurement_quality_status,
    unit_economics_status,
    billing_currency,
    financial_basis,
    operational_cost_basis
  FROM `{{PROJECT_ID}}.{{MART_DATASET}}.mart_ai_unit_economics`
)
SELECT
  unit_economics_id,
  CAST(FORMAT_DATE('%Y%m%d', billing_month) AS INT64) AS date_key,
  billing_month,
  TO_HEX(SHA256(provider)) AS provider_key,
  TO_HEX(
    SHA256(
      TO_JSON_STRING(
        STRUCT(provider, model, model_snapshot, usage_type)
      )
    )
  ) AS model_key,
  provider,
  provider_project_id,
  model,
  model_snapshot,
  usage_type,
  provider_request_count,
  total_tokens,
  invoice_billed_usage_cost,
  provider_reported_usage_cost,
  usage_cost_estimate,
  telemetry_attempt_count,
  telemetry_logical_request_count,
  successful_logical_request_count,
  retry_attempt_count,
  failed_attempt_count,
  estimated_retry_cost,
  estimated_failed_attempt_cost,
  untraceable_provider_usage_cost_estimate,
  telemetry_token_coverage_pct,
  telemetry_request_coverage_pct,
  telemetry_quality_gate_passed,
  measurement_quality_status,
  unit_economics_status,
  billing_currency,
  financial_basis,
  operational_cost_basis
FROM normalized;
