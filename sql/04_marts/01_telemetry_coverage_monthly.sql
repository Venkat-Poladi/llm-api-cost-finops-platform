CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.{{MART_DATASET}}.mart_ai_telemetry_coverage_monthly`
PARTITION BY billing_month
CLUSTER BY provider, provider_project_id, model
AS
SELECT
  DATE_TRUNC(usage_date, MONTH) AS billing_month,
  provider,
  provider_project_id,
  model,
  usage_type,
  SUM(provider_request_count) AS provider_request_count,
  SUM(telemetry_attempt_count) AS telemetry_attempt_count,
  SUM(telemetry_logical_request_count)
    AS telemetry_logical_request_count,
  SUM(telemetry_successful_logical_request_count)
    AS telemetry_successful_logical_request_count,
  SUM(telemetry_retry_attempt_count) AS telemetry_retry_attempt_count,
  SUM(provider_total_tokens) AS provider_total_tokens,
  SUM(telemetry_total_tokens) AS telemetry_total_tokens,
  SUM(provider_usage_cost_estimate) AS provider_usage_cost_estimate,
  SUM(telemetry_usage_cost_estimate) AS telemetry_usage_cost_estimate,
  SUM(telemetry_retry_cost_estimate) AS telemetry_retry_cost_estimate,
  SUM(telemetry_failed_attempt_cost_estimate)
    AS telemetry_failed_attempt_cost_estimate,
  SUM(untraceable_provider_usage_cost_estimate)
    AS untraceable_provider_usage_cost_estimate,
  SAFE_DIVIDE(
    SUM(telemetry_total_tokens),
    SUM(provider_total_tokens)
  ) AS telemetry_token_coverage_pct,
  SAFE_DIVIDE(
    SUM(telemetry_attempt_count),
    SUM(provider_request_count)
  ) AS telemetry_request_coverage_pct,
  SUM(telemetry_attempt_count) - SUM(provider_request_count)
    AS request_count_variance,
  SUM(telemetry_total_tokens) - SUM(provider_total_tokens)
    AS token_count_variance,
  COUNTIF(reconciliation_status = 'EXCEPTION') AS exception_day_count,
  COUNT(*) AS observed_day_count
FROM
  `{{PROJECT_ID}}.{{CORE_DATASET}}.fct_ai_telemetry_reconciliation_daily`
GROUP BY
  billing_month,
  provider,
  provider_project_id,
  model,
  usage_type;
