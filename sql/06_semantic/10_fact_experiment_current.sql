CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.llm_finops_mart.fact_ai_experiment_current`
CLUSTER BY experiment_key, threshold_status, governance_action_status
AS
SELECT
  experiment_governance_id,
  experiment_id AS experiment_key,
  experiment_id,
  CAST(FORMAT_DATE('%Y%m%d', evaluation_date) AS INT64) AS date_key,
  evaluation_date,
  owner,
  approver,
  application_name,
  cost_center,
  spending_limit,
  spending_limit_period,
  limit_currency,
  period_invoice_billed_experiment_cost,
  period_provider_reported_experiment_cost,
  period_driver_cost_estimate,
  period_telemetry_attempt_count,
  period_logical_request_count,
  period_successful_request_count,
  period_retry_attempt_count,
  period_estimated_retry_cost,
  spend_to_limit_pct,
  threshold_status,
  governance_action_status,
  decision_financial_evidence_status,
  governance_exception_status,
  governance_exception_reason,
  period_measurement_quality_status,
  period_spend_quality_label,
  latest_decision,
  latest_decision_date,
  decision_status_as_of_date,
  observed_success_rate,
  observed_retry_attempt_rate,
  invoice_cost_per_successful_request,
  financial_basis,
  operational_basis
FROM `{{PROJECT_ID}}.llm_finops_mart.mart_ai_experiments`
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY experiment_id
  ORDER BY evaluation_date DESC, experiment_governance_id DESC
) = 1;
