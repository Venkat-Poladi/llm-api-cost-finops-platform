CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.{{MART_DATASET}}.mart_ai_token_economics`
PARTITION BY billing_month
CLUSTER BY provider, provider_project_id, model, usage_type
AS
WITH usage_with_batch_rate AS (
  SELECT
    u.*,
    ARRAY(
      SELECT AS STRUCT
        r.input_rate_per_million,
        r.output_rate_per_million,
        r.contracted_discount
      FROM `{{PROJECT_ID}}.{{RAW_DATASET}}.dim_ai_model_rate` AS r
      WHERE r.provider = u.provider
        AND r.usage_type = u.usage_type
        AND r.model_snapshot = u.model_snapshot
        AND r.normalized_processing_tier = u.normalized_processing_tier
        AND r.is_batch = TRUE
        AND r.context_window_tier = u.context_window_tier
        AND u.usage_date BETWEEN r.effective_start AND r.effective_end
    ) AS batch_rate_matches
  FROM
    `{{PROJECT_ID}}.{{STAGING_DATASET}}.stg_ai_provider_usage_priced` AS u
  WHERE u.pricing_status = 'Priced'
),
usage_components AS (
  SELECT
    *,
    ARRAY_LENGTH(batch_rate_matches) AS batch_rate_match_count,
    batch_rate_matches[SAFE_OFFSET(0)] AS batch_rate,
    (
      normalized_uncached_input_tokens
      * input_rate_per_million
      + normalized_cache_read_tokens
        * COALESCE(cached_input_rate_per_million, input_rate_per_million)
      + normalized_cache_creation_5m_tokens
        * COALESCE(cache_write_5m_rate_per_million, 0)
      + normalized_cache_creation_1h_tokens
        * COALESCE(cache_write_1h_rate_per_million, 0)
    )
    / 1000000
    * (1 - contracted_discount)
      AS estimated_input_cost,
    output_tokens
    * output_rate_per_million
    / 1000000
    * (1 - contracted_discount)
      AS estimated_output_cost,
    reasoning_tokens
    * output_rate_per_million
    / 1000000
    * (1 - contracted_discount)
      AS estimated_reasoning_output_cost,
    (
      normalized_total_input_tokens * input_rate_per_million
      + output_tokens * output_rate_per_million
    )
    / 1000000
    * (1 - contracted_discount)
      AS no_cache_baseline_cost,
    CASE
      WHEN is_batch THEN usage_cost_estimate
      WHEN ARRAY_LENGTH(batch_rate_matches) != 1 THEN NULL
      ELSE (
        normalized_total_input_tokens
          * batch_rate_matches[SAFE_OFFSET(0)].input_rate_per_million
        + output_tokens
          * batch_rate_matches[SAFE_OFFSET(0)].output_rate_per_million
      )
      / 1000000
      * (
        1
        - batch_rate_matches[SAFE_OFFSET(0)].contracted_discount
      )
    END AS batch_equivalent_cost_estimate
  FROM usage_with_batch_rate
),
usage_monthly AS (
  SELECT
    DATE_TRUNC(usage_date, MONTH) AS billing_month,
    provider,
    provider_project_id,
    model,
    model_snapshot,
    usage_type,
    COUNT(*) AS source_daily_row_count,
    SUM(request_count) AS request_count,
    SUM(IF(is_batch, request_count, 0)) AS batch_request_count,
    SUM(IF(NOT is_batch, request_count, 0)) AS nonbatch_request_count,
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
    SUM(normalized_total_input_tokens + output_tokens) AS total_tokens,
    ROUND(SUM(usage_cost_estimate), 9) AS usage_cost_estimate,
    ROUND(SUM(estimated_input_cost), 9) AS estimated_input_cost,
    ROUND(SUM(estimated_output_cost), 9) AS estimated_output_cost,
    ROUND(
      SUM(estimated_reasoning_output_cost),
      9
    ) AS estimated_reasoning_output_cost,
    ROUND(SUM(no_cache_baseline_cost), 9) AS no_cache_baseline_cost,
    ROUND(
      SUM(
        GREATEST(no_cache_baseline_cost - usage_cost_estimate, 0)
      ),
      9
    ) AS estimated_cache_savings,
    ROUND(
      SUM(
        CASE
          WHEN is_batch THEN 0
          WHEN batch_equivalent_cost_estimate IS NULL THEN 0
          ELSE GREATEST(
            usage_cost_estimate - batch_equivalent_cost_estimate,
            0
          )
        END
      ),
      9
    ) AS estimated_batch_savings_opportunity,
    COUNTIF(
      NOT is_batch AND batch_rate_match_count != 1
    ) AS nonbatch_rows_without_one_batch_rate,
    'USD' AS billing_currency,
    'usage_cost_estimate' AS financial_basis
  FROM usage_components
  GROUP BY
    billing_month,
    provider,
    provider_project_id,
    model,
    model_snapshot,
    usage_type
),
telemetry_monthly AS (
  SELECT
    DATE_TRUNC(usage_date, MONTH) AS billing_month,
    provider,
    provider_project_id,
    model,
    ANY_VALUE(usage_type) AS usage_type,
    COUNT(*) AS telemetry_attempt_count,
    COUNT(DISTINCT logical_request_id) AS telemetry_logical_request_count,
    COUNTIF(is_successful_logical_request)
      AS successful_logical_request_count,
    COUNTIF(is_retry_attempt) AS retry_attempt_count,
    COUNTIF(attempt_status = 'failed') AS failed_attempt_count,
    SUM(usage_cost_estimate) AS telemetry_usage_cost_estimate,
    SUM(IF(is_retry_attempt, usage_cost_estimate, 0))
      AS estimated_retry_cost,
    SUM(IF(attempt_status = 'failed', usage_cost_estimate, 0))
      AS estimated_failed_attempt_cost,
    SUM(
      IF(
        failure_stage = 'mid_generation_error',
        usage_cost_estimate,
        0
      )
    ) AS estimated_mid_generation_failure_cost
  FROM
    `{{PROJECT_ID}}.{{STAGING_DATASET}}.stg_ai_request_telemetry`
  WHERE telemetry_validation_status = 'Valid'
  GROUP BY
    billing_month,
    provider,
    provider_project_id,
    model
)
SELECT
  TO_HEX(
    SHA256(
      TO_JSON_STRING(
        STRUCT(
          u.billing_month,
          u.provider,
          u.provider_project_id,
          u.model,
          u.model_snapshot,
          u.usage_type
        )
      )
    )
  ) AS token_economics_id,
  u.*,
  SAFE_DIVIDE(
    u.normalized_cache_read_tokens,
    u.normalized_total_input_tokens
  ) AS cache_read_share,
  SAFE_DIVIDE(
    u.reasoning_tokens,
    u.output_tokens
  ) AS reasoning_overhead_pct,
  SAFE_DIVIDE(
    u.batch_request_count,
    u.request_count
  ) AS batch_adoption_pct,
  SAFE_DIVIDE(
    u.estimated_input_cost * 1000000,
    u.normalized_total_input_tokens
  ) AS cost_per_million_input_tokens,
  SAFE_DIVIDE(
    u.estimated_output_cost * 1000000,
    u.output_tokens
  ) AS cost_per_million_output_tokens,
  SAFE_DIVIDE(
    u.usage_cost_estimate * 1000000,
    u.total_tokens
  ) AS cost_per_million_total_tokens,
  SAFE_DIVIDE(
    u.usage_cost_estimate,
    u.request_count
  ) AS estimated_cost_per_provider_request,
  COALESCE(t.telemetry_attempt_count, 0) AS telemetry_attempt_count,
  COALESCE(t.telemetry_logical_request_count, 0)
    AS telemetry_logical_request_count,
  COALESCE(t.successful_logical_request_count, 0)
    AS successful_logical_request_count,
  COALESCE(t.retry_attempt_count, 0) AS retry_attempt_count,
  COALESCE(t.failed_attempt_count, 0) AS failed_attempt_count,
  COALESCE(t.telemetry_usage_cost_estimate, 0)
    AS telemetry_usage_cost_estimate,
  COALESCE(t.estimated_retry_cost, 0) AS estimated_retry_cost,
  COALESCE(t.estimated_failed_attempt_cost, 0)
    AS estimated_failed_attempt_cost,
  COALESCE(t.estimated_mid_generation_failure_cost, 0)
    AS estimated_mid_generation_failure_cost,
  SAFE_DIVIDE(
    t.estimated_failed_attempt_cost,
    t.telemetry_usage_cost_estimate
  ) AS failed_attempt_cost_share,
  SAFE_DIVIDE(
    t.estimated_retry_cost,
    t.telemetry_usage_cost_estimate
  ) AS retry_cost_share,
  'Estimated from request telemetry' AS failure_cost_label
FROM usage_monthly AS u
LEFT JOIN telemetry_monthly AS t
  ON u.billing_month = t.billing_month
  AND u.provider = t.provider
  AND u.provider_project_id = t.provider_project_id
  AND u.model = t.model
  AND u.usage_type = t.usage_type;
