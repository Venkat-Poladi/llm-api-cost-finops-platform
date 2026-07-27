CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.llm_finops_core.fct_ai_telemetry_reconciliation_daily`
PARTITION BY usage_date
CLUSTER BY provider, provider_project_id, model, coverage_status
AS
WITH provider_usage AS (
  SELECT
    usage_date,
    provider,
    provider_project_id,
    model,
    ANY_VALUE(usage_type) AS usage_type,
    SUM(request_count) AS provider_request_count,
    SUM(normalized_total_input_tokens) AS provider_input_tokens,
    SUM(output_tokens) AS provider_output_tokens,
    SUM(normalized_total_input_tokens + output_tokens)
      AS provider_total_tokens,
    SUM(usage_cost_estimate) AS provider_usage_cost_estimate,
    COUNT(*) AS provider_usage_row_count
  FROM
    `{{PROJECT_ID}}.llm_finops_staging.stg_ai_provider_usage_priced`
  WHERE pricing_status = 'Priced'
  GROUP BY
    usage_date,
    provider,
    provider_project_id,
    model
),
telemetry AS (
  SELECT
    usage_date,
    provider,
    provider_project_id,
    model,
    ANY_VALUE(usage_type) AS usage_type,
    COUNT(*) AS telemetry_attempt_count,
    COUNT(DISTINCT logical_request_id) AS telemetry_logical_request_count,
    COUNTIF(is_final_attempt) AS telemetry_final_attempt_count,
    COUNTIF(is_successful_logical_request)
      AS telemetry_successful_logical_request_count,
    COUNTIF(is_retry_attempt) AS telemetry_retry_attempt_count,
    COUNTIF(attempt_status = 'failed') AS telemetry_failed_attempt_count,
    SUM(normalized_total_input_tokens) AS telemetry_input_tokens,
    SUM(output_tokens) AS telemetry_output_tokens,
    SUM(normalized_total_input_tokens + output_tokens)
      AS telemetry_total_tokens,
    SUM(usage_cost_estimate) AS telemetry_usage_cost_estimate,
    SUM(IF(is_retry_attempt, usage_cost_estimate, 0))
      AS telemetry_retry_cost_estimate,
    SUM(IF(attempt_status = 'failed', usage_cost_estimate, 0))
      AS telemetry_failed_attempt_cost_estimate,
    SUM(
      IF(
        failure_stage = 'mid_generation_error',
        usage_cost_estimate,
        0
      )
    ) AS telemetry_mid_generation_failure_cost_estimate,
    COUNT(*) AS telemetry_row_count
  FROM
    `{{PROJECT_ID}}.llm_finops_staging.stg_ai_request_telemetry`
  WHERE telemetry_validation_status = 'Valid'
  GROUP BY
    usage_date,
    provider,
    provider_project_id,
    model
),
joined AS (
  SELECT
    COALESCE(p.usage_date, t.usage_date) AS usage_date,
    COALESCE(p.provider, t.provider) AS provider,
    COALESCE(p.provider_project_id, t.provider_project_id)
      AS provider_project_id,
    COALESCE(p.model, t.model) AS model,
    COALESCE(p.usage_type, t.usage_type) AS usage_type,
    p.provider_request_count,
    p.provider_input_tokens,
    p.provider_output_tokens,
    p.provider_total_tokens,
    p.provider_usage_cost_estimate,
    p.provider_usage_row_count,
    t.telemetry_attempt_count,
    t.telemetry_logical_request_count,
    t.telemetry_final_attempt_count,
    t.telemetry_successful_logical_request_count,
    t.telemetry_retry_attempt_count,
    t.telemetry_failed_attempt_count,
    t.telemetry_input_tokens,
    t.telemetry_output_tokens,
    t.telemetry_total_tokens,
    t.telemetry_usage_cost_estimate,
    t.telemetry_retry_cost_estimate,
    t.telemetry_failed_attempt_cost_estimate,
    t.telemetry_mid_generation_failure_cost_estimate,
    t.telemetry_row_count,
    p.usage_date IS NOT NULL AS has_provider_usage,
    t.usage_date IS NOT NULL AS has_telemetry
  FROM provider_usage AS p
  FULL OUTER JOIN telemetry AS t
    ON p.usage_date = t.usage_date
    AND p.provider = t.provider
    AND p.provider_project_id = t.provider_project_id
    AND p.model = t.model
),
metrics AS (
  SELECT
    *,
    SAFE_DIVIDE(
      telemetry_total_tokens,
      provider_total_tokens
    ) AS telemetry_token_coverage_pct,
    SAFE_DIVIDE(
      telemetry_attempt_count,
      provider_request_count
    ) AS telemetry_request_coverage_pct,
    telemetry_attempt_count - provider_request_count
      AS request_count_variance,
    telemetry_total_tokens - provider_total_tokens
      AS token_count_variance,
    telemetry_input_tokens - provider_input_tokens
      AS input_token_variance,
    telemetry_output_tokens - provider_output_tokens
      AS output_token_variance,
    SAFE_DIVIDE(
      telemetry_attempt_count - provider_request_count,
      provider_request_count
    ) AS request_count_variance_pct,
    SAFE_DIVIDE(
      telemetry_total_tokens - provider_total_tokens,
      provider_total_tokens
    ) AS token_count_variance_pct
  FROM joined
),
cost_metrics AS (
  SELECT
    *,
    CASE
      WHEN provider_total_tokens IS NULL THEN NULL
      WHEN provider_total_tokens = 0 THEN provider_usage_cost_estimate
      ELSE
        provider_usage_cost_estimate
        * GREATEST(
            1 - COALESCE(telemetry_token_coverage_pct, 0),
            0
          )
    END AS untraceable_provider_usage_cost_estimate
  FROM metrics
)
SELECT
  TO_HEX(
    SHA256(
      TO_JSON_STRING(
        STRUCT(
          usage_date,
          provider,
          provider_project_id,
          model
        )
      )
    )
  ) AS telemetry_reconciliation_id,
  *,
  CASE
    WHEN NOT has_provider_usage THEN 'NO_PROVIDER_USAGE'
    WHEN NOT has_telemetry THEN 'NO_TELEMETRY'
    WHEN telemetry_token_coverage_pct < 0.95 THEN 'PARTIAL_COVERAGE'
    WHEN telemetry_token_coverage_pct > 1.05 THEN 'OVER_COVERAGE'
    WHEN provider_request_count IS NULL
      THEN 'REQUEST_COUNT_UNAVAILABLE'
    WHEN ABS(request_count_variance_pct) > 0.05
      THEN 'REQUEST_MISMATCH'
    ELSE 'WITHIN_TOLERANCE'
  END AS coverage_status,
  CASE
    WHEN NOT has_provider_usage OR NOT has_telemetry THEN 'EXCEPTION'
    WHEN telemetry_token_coverage_pct BETWEEN 0.95 AND 1.05
      AND (
        provider_request_count IS NULL
        OR ABS(request_count_variance_pct) <= 0.05
      )
      THEN 'PASS'
    ELSE 'EXCEPTION'
  END AS reconciliation_status,
  CASE
    WHEN NOT has_provider_usage THEN 'TELEMETRY_WITHOUT_PROVIDER_USAGE'
    WHEN NOT has_telemetry THEN 'PROVIDER_USAGE_WITHOUT_TELEMETRY'
    WHEN telemetry_token_coverage_pct < 0.95
      THEN 'INCOMPLETE_TELEMETRY_CAPTURE'
    WHEN telemetry_token_coverage_pct > 1.05
      THEN 'TELEMETRY_EXCEEDS_PROVIDER_USAGE'
    WHEN ABS(request_count_variance_pct) > 0.05
      THEN 'REQUEST_COUNT_DIFFERENCE'
    ELSE NULL
  END AS variance_reason_code
FROM cost_metrics;
