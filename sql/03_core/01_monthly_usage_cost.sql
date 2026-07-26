CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.llm_finops_staging.stg_ai_usage_cost_monthly`
PARTITION BY billing_month
CLUSTER BY provider, provider_project_id, model
AS
SELECT
  DATE_TRUNC(usage_date, MONTH) AS billing_month,
  provider,
  provider_project_id,
  model,
  COUNT(*) AS source_daily_row_count,
  COUNT(DISTINCT api_key_id) AS distinct_api_key_count,
  SUM(request_count) AS request_count,
  SUM(normalized_total_input_tokens) AS normalized_total_input_tokens,
  SUM(normalized_uncached_input_tokens) AS normalized_uncached_input_tokens,
  SUM(normalized_cache_read_tokens) AS normalized_cache_read_tokens,
  SUM(normalized_cache_creation_5m_tokens)
    AS normalized_cache_creation_5m_tokens,
  SUM(normalized_cache_creation_1h_tokens)
    AS normalized_cache_creation_1h_tokens,
  SUM(output_tokens) AS output_tokens,
  SUM(reasoning_tokens) AS reasoning_tokens,
  SUM(visible_output_tokens) AS visible_output_tokens,
  ROUND(SUM(usage_cost_estimate), 9) AS usage_cost_estimate,
  COUNTIF(pricing_status != 'Priced') AS unpriced_daily_row_count,
  'USD' AS estimate_currency
FROM `{{PROJECT_ID}}.llm_finops_staging.stg_ai_provider_usage_priced`
GROUP BY
  billing_month,
  provider,
  provider_project_id,
  model;
