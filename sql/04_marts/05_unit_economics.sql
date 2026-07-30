CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.llm_finops_mart.mart_ai_unit_economics`
PARTITION BY billing_month
CLUSTER BY provider, model, measurement_quality_status, usage_type
AS
WITH financial_usage AS (
  SELECT
    billing_month,
    provider,
    provider_project_id,
    model,
    COUNT(*) AS financial_usage_line_count,
    SUM(usage_cost_estimate) AS reconciled_usage_cost_estimate,
    SUM(provider_reported_cost) AS provider_reported_usage_cost,
    SUM(invoice_billed_cost) AS invoice_billed_usage_cost,
    ANY_VALUE(billing_currency) AS billing_currency,
    LOGICAL_AND(is_synthetic) AS is_synthetic
  FROM `{{PROJECT_ID}}.llm_finops_core.fct_ai_cost_reconciliation`
  WHERE line_item_type = 'usage'
  GROUP BY
    billing_month,
    provider,
    provider_project_id,
    model
),
base AS (
  SELECT
    t.billing_month,
    t.provider,
    t.provider_project_id,
    t.model,
    t.model_snapshot,
    t.usage_type,
    f.financial_usage_line_count,
    t.request_count AS provider_request_count,
    t.normalized_total_input_tokens,
    t.output_tokens,
    t.reasoning_tokens,
    t.visible_output_tokens,
    t.total_tokens,
    t.usage_cost_estimate,
    f.reconciled_usage_cost_estimate,
    f.provider_reported_usage_cost,
    f.invoice_billed_usage_cost,
    f.invoice_billed_usage_cost - t.usage_cost_estimate
      AS invoice_to_estimate_variance,
    SAFE_DIVIDE(
      f.invoice_billed_usage_cost - t.usage_cost_estimate,
      ABS(t.usage_cost_estimate)
    ) AS invoice_to_estimate_variance_pct,
    t.telemetry_attempt_count,
    t.telemetry_logical_request_count,
    t.successful_logical_request_count,
    t.retry_attempt_count,
    t.failed_attempt_count,
    t.telemetry_usage_cost_estimate,
    t.estimated_retry_cost,
    t.estimated_failed_attempt_cost,
    t.estimated_mid_generation_failure_cost,
    c.telemetry_token_coverage_pct,
    c.telemetry_request_coverage_pct,
    c.untraceable_provider_usage_cost_estimate,
    c.exception_day_count,
    c.observed_day_count,
    f.billing_currency,
    f.is_synthetic,
    c.telemetry_token_coverage_pct BETWEEN 0.95 AND 1.05
      AS telemetry_quality_gate_passed
  FROM `{{PROJECT_ID}}.llm_finops_mart.mart_ai_token_economics` AS t
  JOIN financial_usage AS f
    ON t.billing_month = f.billing_month
    AND t.provider = f.provider
    AND t.provider_project_id = f.provider_project_id
    AND t.model = f.model
  LEFT JOIN
    `{{PROJECT_ID}}.llm_finops_mart.mart_ai_telemetry_coverage_monthly` AS c
    ON t.billing_month = c.billing_month
    AND t.provider = c.provider
    AND t.provider_project_id = c.provider_project_id
    AND t.model = c.model
    AND t.usage_type = c.usage_type
)
SELECT
  TO_HEX(
    SHA256(
      TO_JSON_STRING(
        STRUCT(
          billing_month,
          provider,
          provider_project_id,
          model,
          model_snapshot,
          usage_type
        )
      )
    )
  ) AS unit_economics_id,
  *,
  SAFE_DIVIDE(
    invoice_billed_usage_cost,
    provider_request_count
  ) AS invoice_cost_per_provider_request,
  SAFE_DIVIDE(
    invoice_billed_usage_cost * 1000,
    provider_request_count
  ) AS invoice_cost_per_thousand_provider_requests,
  SAFE_DIVIDE(
    invoice_billed_usage_cost * 1000000,
    total_tokens
  ) AS invoice_cost_per_million_total_tokens,
  SAFE_DIVIDE(
    invoice_billed_usage_cost * 1000000,
    normalized_total_input_tokens
  ) AS invoice_cost_per_million_input_tokens,
  SAFE_DIVIDE(
    invoice_billed_usage_cost * 1000000,
    output_tokens
  ) AS invoice_cost_per_million_output_tokens,
  CASE
    WHEN telemetry_quality_gate_passed THEN SAFE_DIVIDE(
      invoice_billed_usage_cost,
      telemetry_logical_request_count
    )
    ELSE NULL
  END AS governed_invoice_cost_per_logical_request,
  CASE
    WHEN telemetry_quality_gate_passed THEN SAFE_DIVIDE(
      invoice_billed_usage_cost,
      successful_logical_request_count
    )
    ELSE NULL
  END AS governed_invoice_cost_per_successful_request,
  SAFE_DIVIDE(
    successful_logical_request_count,
    telemetry_logical_request_count
  ) AS observed_success_rate,
  SAFE_DIVIDE(
    retry_attempt_count,
    telemetry_attempt_count
  ) AS observed_retry_attempt_rate,
  SAFE_DIVIDE(
    failed_attempt_count,
    telemetry_attempt_count
  ) AS observed_failed_attempt_rate,
  SAFE_DIVIDE(
    telemetry_attempt_count,
    telemetry_logical_request_count
  ) AS observed_attempts_per_logical_request,
  SAFE_DIVIDE(
    total_tokens,
    provider_request_count
  ) AS average_tokens_per_provider_request,
  SAFE_DIVIDE(
    normalized_total_input_tokens,
    provider_request_count
  ) AS average_input_tokens_per_provider_request,
  SAFE_DIVIDE(
    output_tokens,
    provider_request_count
  ) AS average_output_tokens_per_provider_request,
  SAFE_DIVIDE(
    reasoning_tokens,
    output_tokens
  ) AS reasoning_overhead_pct,
  SAFE_DIVIDE(
    estimated_retry_cost,
    telemetry_usage_cost_estimate
  ) AS estimated_retry_cost_share,
  SAFE_DIVIDE(
    estimated_failed_attempt_cost,
    telemetry_usage_cost_estimate
  ) AS estimated_failed_attempt_cost_share,
  CASE
    WHEN telemetry_quality_gate_passed THEN SAFE_DIVIDE(
      estimated_retry_cost,
      successful_logical_request_count
    )
    ELSE NULL
  END AS governed_retry_cost_per_successful_request,
  CASE
    WHEN telemetry_quality_gate_passed THEN 'SUFFICIENT'
    ELSE 'INSUFFICIENT'
  END AS measurement_quality_status,
  CASE
    WHEN telemetry_quality_gate_passed THEN 'PUBLISHABLE'
    ELSE 'LIMITED_TELEMETRY'
  END AS unit_economics_status,
  CASE
    WHEN telemetry_quality_gate_passed THEN
      'Telemetry-dependent unit economics passed the 95%-105% token coverage gate.'
    ELSE
      'Provider-based metrics are valid, but logical-request and successful-request cost metrics are withheld.'
  END AS measurement_quality_note,
  'invoice_billed_cost_usage_lines' AS financial_basis,
  'usage_cost_estimate' AS operational_cost_basis,
  'Estimated from request telemetry' AS retry_and_failure_cost_label
FROM base;
