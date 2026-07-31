CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.llm_finops_mart.fact_ai_usage_monthly`
PARTITION BY billing_month
CLUSTER BY provider_key, model_key, usage_type
AS
WITH normalized AS (
  SELECT
    token_economics_id AS usage_monthly_id,
    billing_month,
    provider,
    provider_project_id,
    COALESCE(model, 'Not applicable') AS model,
    COALESCE(model_snapshot, 'Not applicable') AS model_snapshot,
    COALESCE(usage_type, 'Not applicable') AS usage_type,
    request_count,
    batch_request_count,
    nonbatch_request_count,
    normalized_total_input_tokens,
    normalized_uncached_input_tokens,
    normalized_cache_read_tokens,
    normalized_cache_creation_5m_tokens,
    normalized_cache_creation_1h_tokens,
    output_tokens,
    reasoning_tokens,
    visible_output_tokens,
    total_tokens,
    usage_cost_estimate,
    estimated_input_cost,
    estimated_output_cost,
    estimated_reasoning_output_cost,
    no_cache_baseline_cost,
    estimated_cache_savings,
    estimated_batch_savings_opportunity,
    telemetry_attempt_count,
    telemetry_logical_request_count,
    successful_logical_request_count,
    retry_attempt_count,
    failed_attempt_count,
    telemetry_usage_cost_estimate,
    estimated_retry_cost,
    estimated_failed_attempt_cost,
    estimated_mid_generation_failure_cost,
    billing_currency,
    financial_basis
  FROM `{{PROJECT_ID}}.llm_finops_mart.mart_ai_token_economics`
)
SELECT
  usage_monthly_id,
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
  request_count,
  batch_request_count,
  nonbatch_request_count,
  normalized_total_input_tokens,
  normalized_uncached_input_tokens,
  normalized_cache_read_tokens,
  normalized_cache_creation_5m_tokens,
  normalized_cache_creation_1h_tokens,
  output_tokens,
  reasoning_tokens,
  visible_output_tokens,
  total_tokens,
  usage_cost_estimate,
  estimated_input_cost,
  estimated_output_cost,
  estimated_reasoning_output_cost,
  no_cache_baseline_cost,
  estimated_cache_savings,
  estimated_batch_savings_opportunity,
  telemetry_attempt_count,
  telemetry_logical_request_count,
  successful_logical_request_count,
  retry_attempt_count,
  failed_attempt_count,
  telemetry_usage_cost_estimate,
  estimated_retry_cost,
  estimated_failed_attempt_cost,
  estimated_mid_generation_failure_cost,
  billing_currency,
  financial_basis
FROM normalized;
