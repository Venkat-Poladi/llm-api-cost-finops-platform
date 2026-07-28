CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.llm_finops_staging.stg_ai_application_invoice_driver_monthly`
PARTITION BY billing_month
CLUSTER BY provider, provider_project_id, model, application_name
AS
SELECT
  DATE_TRUNC(usage_date, MONTH) AS billing_month,
  provider,
  provider_project_id,
  model,
  model_snapshot,
  usage_type,
  application_name,
  department_name,
  cost_center,
  allocation_status,
  allocation_method,
  allocation_confidence,
  LOGICAL_OR(is_historical_restatement) AS is_historical_restatement,
  SUM(
    allocated_request_count + unallocated_request_count
  ) AS distributed_request_count,
  SUM(
    allocated_total_input_tokens + unallocated_total_input_tokens
  ) AS distributed_total_input_tokens,
  SUM(
    allocated_output_tokens + unallocated_output_tokens
  ) AS distributed_output_tokens,
  SUM(
    allocated_reasoning_tokens + unallocated_reasoning_tokens
  ) AS distributed_reasoning_tokens,
  ROUND(
    SUM(
      allocated_usage_cost_estimate
      + unallocated_usage_cost_estimate
    ),
    9
  ) AS driver_usage_cost_estimate,
  ANY_VALUE(billing_currency) AS billing_currency,
  LOGICAL_AND(is_synthetic) AS is_synthetic
FROM `{{PROJECT_ID}}.llm_finops_core.fct_ai_usage_daily`
GROUP BY
  billing_month,
  provider,
  provider_project_id,
  model,
  model_snapshot,
  usage_type,
  application_name,
  department_name,
  cost_center,
  allocation_status,
  allocation_method,
  allocation_confidence;
