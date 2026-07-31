CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.{{STAGING_DATASET}}.stg_ai_provider_usage_priced`
PARTITION BY usage_date
CLUSTER BY provider, usage_type, model_snapshot, provider_project_id
AS
WITH candidates AS (
  SELECT
    n.*,
    ARRAY(
      SELECT AS STRUCT
        r.effective_start,
        r.effective_end,
        r.input_rate_per_million,
        r.cached_input_rate_per_million,
        r.cache_write_5m_rate_per_million,
        r.cache_write_1h_rate_per_million,
        r.output_rate_per_million,
        r.contracted_discount,
        r.rate_currency,
        r.rate_basis,
        r.rate_source,
        r.rate_status
      FROM `{{PROJECT_ID}}.{{RAW_DATASET}}.dim_ai_model_rate` AS r
      WHERE r.provider = n.provider
        AND r.usage_type = n.usage_type
        AND r.model_snapshot = n.model_snapshot
        AND r.normalized_processing_tier = n.normalized_processing_tier
        AND r.is_batch = n.is_batch
        AND r.context_window_tier = n.context_window_tier
        AND n.usage_date BETWEEN r.effective_start AND r.effective_end
    ) AS rate_matches
  FROM
    `{{PROJECT_ID}}.{{STAGING_DATASET}}.stg_ai_provider_usage_normalized` AS n
),
resolved AS (
  SELECT
    * EXCEPT(rate_matches),
    ARRAY_LENGTH(rate_matches) AS rate_match_count,
    rate_matches[SAFE_OFFSET(0)] AS rate
  FROM candidates
)
SELECT
  * EXCEPT(rate),
  rate.effective_start AS rate_effective_start,
  rate.effective_end AS rate_effective_end,
  rate.input_rate_per_million,
  rate.cached_input_rate_per_million,
  rate.cache_write_5m_rate_per_million,
  rate.cache_write_1h_rate_per_million,
  rate.output_rate_per_million,
  rate.contracted_discount,
  rate.rate_currency,
  rate.rate_basis,
  rate.rate_source,
  rate.rate_status,
  CASE
    WHEN rate_match_count != 1 THEN NULL
    ELSE ROUND(
      (
        (
          normalized_uncached_input_tokens
          * rate.input_rate_per_million
        )
        + (
          normalized_cache_read_tokens
          * COALESCE(
              rate.cached_input_rate_per_million,
              rate.input_rate_per_million
            )
        )
        + (
          normalized_cache_creation_5m_tokens
          * COALESCE(rate.cache_write_5m_rate_per_million, 0)
        )
        + (
          normalized_cache_creation_1h_tokens
          * COALESCE(rate.cache_write_1h_rate_per_million, 0)
        )
        + (
          output_tokens
          * rate.output_rate_per_million
        )
      )
      / 1000000
      * (1 - rate.contracted_discount),
      9
    )
  END AS usage_cost_estimate,
  CASE
    WHEN rate_match_count = 1
      AND rate.rate_currency = 'USD'
      AND token_validation_status = 'Valid'
      AND model_map_resolution_status = 'Resolved'
      AND service_tier_resolution_status = 'Resolved'
      THEN 'Priced'
    WHEN rate_match_count = 0 THEN 'Missing rate'
    WHEN rate_match_count > 1 THEN 'Multiple rates'
    WHEN rate.rate_currency != 'USD' THEN 'Invalid currency'
    ELSE 'Invalid upstream record'
  END AS pricing_status
FROM resolved;
