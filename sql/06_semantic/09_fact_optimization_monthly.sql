CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.{{MART_DATASET}}.fact_ai_optimization_monthly`
PARTITION BY billing_month
CLUSTER BY provider_key, model_key, optimization_type, evaluation_gate_status
AS
WITH normalized AS (
  SELECT
    recommendation_id,
    billing_month,
    provider,
    provider_project_id,
    COALESCE(model, 'Not applicable') AS model,
    COALESCE(model_snapshot, 'Not applicable') AS model_snapshot,
    COALESCE(usage_type, 'Not applicable') AS usage_type,
    optimization_type,
    recommendation_title,
    recommendation_rationale,
    eligible_cost_base,
    cost_at_risk,
    modeled_monthly_savings,
    identified_annualized_savings,
    approved_annualized_savings,
    implemented_annualized_savings,
    realized_savings,
    savings_stage,
    evaluation_gate_status,
    gate_reason,
    savings_confidence,
    estimation_method,
    assumption_text,
    telemetry_token_coverage_pct,
    measurement_quality_status,
    requires_telemetry_remediation,
    evaluation_ready_flag,
    recommendation_generated_date,
    financial_basis,
    billing_currency
  FROM `{{PROJECT_ID}}.{{MART_DATASET}}.mart_ai_optimization`
)
SELECT
  recommendation_id,
  CAST(FORMAT_DATE('%Y%m%d', billing_month) AS INT64) AS date_key,
  billing_month,
  TO_HEX(SHA256(provider)) AS provider_key,
  TO_HEX(
    SHA256(
      TO_JSON_STRING(
        STRUCT(provider, model, model_snapshot, usage_type)
      )
    )
  ) AS model_key,
  provider,
  provider_project_id,
  model,
  model_snapshot,
  usage_type,
  optimization_type,
  recommendation_title,
  recommendation_rationale,
  eligible_cost_base,
  cost_at_risk,
  modeled_monthly_savings,
  identified_annualized_savings,
  approved_annualized_savings,
  implemented_annualized_savings,
  realized_savings,
  savings_stage,
  evaluation_gate_status,
  gate_reason,
  savings_confidence,
  estimation_method,
  assumption_text,
  telemetry_token_coverage_pct,
  measurement_quality_status,
  requires_telemetry_remediation,
  evaluation_ready_flag,
  recommendation_generated_date,
  financial_basis,
  billing_currency
FROM normalized;
