CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.{{STAGING_DATASET}}.stg_ai_experiment_invoice_driver_daily`
PARTITION BY usage_date
CLUSTER BY experiment_id, provider, provider_project_id, model
AS
WITH experiment_telemetry_daily AS (
  SELECT
    usage_date,
    DATE_TRUNC(usage_date, MONTH) AS billing_month,
    provider,
    provider_project_id,
    model,
    experiment_id,
    COUNT(*) AS telemetry_attempt_count,
    COUNT(DISTINCT logical_request_id) AS telemetry_logical_request_count,
    COUNTIF(is_successful_logical_request)
      AS successful_logical_request_count,
    COUNTIF(is_retry_attempt) AS retry_attempt_count,
    SUM(normalized_total_input_tokens + output_tokens)
      AS telemetry_total_tokens,
    SUM(usage_cost_estimate) AS experiment_driver_cost_estimate,
    SUM(IF(is_retry_attempt, usage_cost_estimate, 0))
      AS estimated_retry_cost
  FROM
    `{{PROJECT_ID}}.{{STAGING_DATASET}}.stg_ai_request_telemetry`
  WHERE telemetry_validation_status = 'Valid'
    AND experiment_id IS NOT NULL
  GROUP BY
    usage_date,
    billing_month,
    provider,
    provider_project_id,
    model,
    experiment_id
),
invoice_usage_scope AS (
  SELECT
    billing_month,
    provider,
    provider_project_id,
    model,
    SUM(usage_cost_estimate) AS monthly_usage_cost_estimate,
    SUM(provider_reported_cost) AS monthly_provider_reported_usage_cost,
    SUM(invoice_billed_cost) AS monthly_invoice_billed_usage_cost,
    ANY_VALUE(billing_currency) AS billing_currency
  FROM `{{PROJECT_ID}}.{{CORE_DATASET}}.fct_ai_cost_reconciliation`
  WHERE line_item_type = 'usage'
  GROUP BY
    billing_month,
    provider,
    provider_project_id,
    model
),
coverage AS (
  SELECT
    billing_month,
    provider,
    provider_project_id,
    model,
    telemetry_token_coverage_pct
  FROM
    `{{PROJECT_ID}}.{{MART_DATASET}}.mart_ai_telemetry_coverage_monthly`
),
joined AS (
  SELECT
    e.*,
    i.monthly_usage_cost_estimate,
    i.monthly_provider_reported_usage_cost,
    i.monthly_invoice_billed_usage_cost,
    i.billing_currency,
    c.telemetry_token_coverage_pct,
    SAFE_DIVIDE(
      e.experiment_driver_cost_estimate,
      i.monthly_usage_cost_estimate
    ) AS financial_allocation_share
  FROM experiment_telemetry_daily AS e
  JOIN invoice_usage_scope AS i
    USING (
      billing_month,
      provider,
      provider_project_id,
      model
    )
  LEFT JOIN coverage AS c
    USING (
      billing_month,
      provider,
      provider_project_id,
      model
    )
)
SELECT
  TO_HEX(
    SHA256(
      TO_JSON_STRING(
        STRUCT(
          usage_date,
          provider,
          provider_project_id,
          model,
          experiment_id
        )
      )
    )
  ) AS experiment_driver_id,
  *,
  monthly_provider_reported_usage_cost
    * financial_allocation_share
      AS allocated_provider_reported_experiment_cost,
  monthly_invoice_billed_usage_cost
    * financial_allocation_share
      AS allocated_invoice_billed_experiment_cost,
  CASE
    WHEN monthly_usage_cost_estimate IS NULL
      OR monthly_usage_cost_estimate = 0
      THEN 'NO_ELIGIBLE_DRIVER'
    WHEN telemetry_token_coverage_pct BETWEEN 0.95 AND 1.05
      THEN 'SUFFICIENT'
    ELSE 'LIMITED'
  END AS measurement_quality_status,
  CASE
    WHEN telemetry_token_coverage_pct BETWEEN 0.95 AND 1.05
      THEN 'BEST_ESTIMATE'
    ELSE 'LOWER_BOUND'
  END AS spend_quality_label,
  'allocated_invoice_billed_cost_usage_lines_only'
    AS financial_basis,
  'request_telemetry_usage_cost_estimate'
    AS operational_basis
FROM joined;
