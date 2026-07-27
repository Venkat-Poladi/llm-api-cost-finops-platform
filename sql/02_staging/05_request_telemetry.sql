CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.llm_finops_staging.stg_ai_request_telemetry`
PARTITION BY usage_date
CLUSTER BY provider, model, provider_project_id, application_name
AS
SELECT
  *,
  CASE
    WHEN STARTS_WITH(model, 'text-embedding-') THEN 'embedding'
    ELSE 'text_generation'
  END AS usage_type,
  CASE
    WHEN provider = 'openai' THEN input_tokens
    WHEN provider = 'anthropic' THEN
      COALESCE(uncached_input_tokens, 0)
      + COALESCE(cache_read_input_tokens, 0)
      + COALESCE(cache_creation_5m_tokens, 0)
      + COALESCE(cache_creation_1h_tokens, 0)
  END AS normalized_total_input_tokens,
  CASE
    WHEN provider = 'openai' THEN COALESCE(cached_input_tokens, 0)
    WHEN provider = 'anthropic' THEN COALESCE(cache_read_input_tokens, 0)
  END AS normalized_cache_read_tokens,
  input_tokens + output_tokens AS provider_total_tokens,
  output_tokens - reasoning_tokens AS visible_output_tokens,
  is_final_attempt AND final_request_status = 'success'
    AS is_successful_logical_request,
  NOT is_final_attempt AS is_retry_attempt,
  CASE
    WHEN reasoning_tokens > output_tokens THEN 'Invalid reasoning tokens'
    WHEN provider = 'openai' AND cached_input_tokens > input_tokens
      THEN 'Invalid cached input'
    ELSE 'Valid'
  END AS telemetry_validation_status
FROM `{{PROJECT_ID}}.llm_finops_raw.fct_ai_request_telemetry`;
