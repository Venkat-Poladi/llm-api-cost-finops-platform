CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.llm_finops_staging.stg_ai_provider_usage_normalized`
PARTITION BY usage_date
CLUSTER BY provider, usage_type, model, provider_project_id
AS
WITH source AS (
  SELECT
    TO_HEX(
      SHA256(
        TO_JSON_STRING(
          STRUCT(
            usage_date,
            provider,
            usage_type,
            provider_project_id,
            api_key_id,
            model,
            provider_service_tier,
            is_batch,
            context_window_tier
          )
        )
      )
    ) AS source_usage_key,
    u.*,
    ARRAY(
      SELECT AS STRUCT
        m.model_snapshot,
        m.effective_start,
        m.effective_end,
        m.reasoning_capable
      FROM `{{PROJECT_ID}}.llm_finops_raw.dim_ai_model_map` AS m
      WHERE m.provider = u.provider
        AND m.usage_type = u.usage_type
        AND m.provider_model_name = u.model
        AND u.usage_date BETWEEN m.effective_start AND m.effective_end
    ) AS model_matches,
    ARRAY(
      SELECT AS STRUCT
        t.normalized_processing_tier
      FROM `{{PROJECT_ID}}.llm_finops_staging.dim_ai_service_tier_map` AS t
      WHERE t.provider = u.provider
        AND t.provider_service_tier = u.provider_service_tier
        AND t.is_batch = u.is_batch
    ) AS tier_matches
  FROM `{{PROJECT_ID}}.llm_finops_raw.raw_ai_provider_usage` AS u
),
resolved AS (
  SELECT
    source_usage_key,
    usage_date,
    provider,
    usage_type,
    provider_project_id,
    api_key_id,
    model,
    provider_service_tier,
    is_batch,
    context_window_tier,
    request_count,
    input_tokens,
    output_tokens,
    COALESCE(reasoning_tokens, 0) AS reasoning_tokens,
    cached_input_tokens,
    uncached_input_tokens,
    cache_read_input_tokens,
    cache_creation_5m_tokens,
    cache_creation_1h_tokens,
    is_synthetic,
    ARRAY_LENGTH(model_matches) AS model_map_match_count,
    model_matches[SAFE_OFFSET(0)].model_snapshot AS model_snapshot,
    model_matches[SAFE_OFFSET(0)].effective_start AS model_map_effective_start,
    model_matches[SAFE_OFFSET(0)].effective_end AS model_map_effective_end,
    model_matches[SAFE_OFFSET(0)].reasoning_capable AS reasoning_capable,
    ARRAY_LENGTH(tier_matches) AS service_tier_match_count,
    tier_matches[SAFE_OFFSET(0)].normalized_processing_tier
      AS normalized_processing_tier
  FROM source
)
SELECT
  *,
  CASE
    WHEN provider = 'openai' THEN input_tokens
    WHEN provider = 'anthropic' THEN
      COALESCE(uncached_input_tokens, 0)
      + COALESCE(cache_read_input_tokens, 0)
      + COALESCE(cache_creation_5m_tokens, 0)
      + COALESCE(cache_creation_1h_tokens, 0)
  END AS normalized_total_input_tokens,
  CASE
    WHEN provider = 'openai' THEN
      input_tokens - COALESCE(cached_input_tokens, 0)
    WHEN provider = 'anthropic' THEN
      COALESCE(uncached_input_tokens, 0)
  END AS normalized_uncached_input_tokens,
  CASE
    WHEN provider = 'openai' THEN COALESCE(cached_input_tokens, 0)
    WHEN provider = 'anthropic' THEN
      COALESCE(cache_read_input_tokens, 0)
  END AS normalized_cache_read_tokens,
  CASE
    WHEN provider = 'openai' THEN 0
    WHEN provider = 'anthropic' THEN
      COALESCE(cache_creation_5m_tokens, 0)
  END AS normalized_cache_creation_5m_tokens,
  CASE
    WHEN provider = 'openai' THEN 0
    WHEN provider = 'anthropic' THEN
      COALESCE(cache_creation_1h_tokens, 0)
  END AS normalized_cache_creation_1h_tokens,
  input_tokens + output_tokens AS provider_total_tokens,
  output_tokens - reasoning_tokens AS visible_output_tokens,
  CASE
    WHEN model_map_match_count = 1 THEN 'Resolved'
    WHEN model_map_match_count = 0 THEN 'Missing model map'
    ELSE 'Multiple model maps'
  END AS model_map_resolution_status,
  CASE
    WHEN service_tier_match_count = 1 THEN 'Resolved'
    WHEN service_tier_match_count = 0 THEN 'Missing service tier'
    ELSE 'Multiple service tiers'
  END AS service_tier_resolution_status,
  CASE
    WHEN reasoning_tokens > output_tokens THEN 'Invalid reasoning tokens'
    WHEN provider = 'openai'
      AND COALESCE(cached_input_tokens, 0) > input_tokens
      THEN 'Invalid cached input'
    WHEN usage_type = 'embedding' AND output_tokens != 0
      THEN 'Invalid embedding output'
    ELSE 'Valid'
  END AS token_validation_status
FROM resolved;
