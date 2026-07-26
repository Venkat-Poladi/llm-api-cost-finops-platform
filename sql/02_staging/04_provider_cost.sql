CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.llm_finops_staging.stg_ai_provider_cost`
PARTITION BY billing_month
CLUSTER BY provider, provider_project_id, line_item_type, model
AS
SELECT
  billing_period,
  DATE_TRUNC(billing_period, MONTH) AS billing_month,
  provider,
  provider_project_id,
  NULLIF(model, '') AS model,
  line_item_scope,
  line_item_type,
  provider_line_item_id,
  provider_reported_cost,
  invoice_billed_cost,
  UPPER(billing_currency) AS billing_currency,
  credit_amount,
  NULLIF(adjustment_reason, '') AS adjustment_reason,
  invoice_issue_date,
  is_restatement,
  is_synthetic,
  CASE
    WHEN line_item_type = 'usage' THEN 'Applicable'
    ELSE 'Not applicable'
  END AS usage_reconciliation_applicability,
  CASE
    WHEN UPPER(billing_currency) = 'USD' THEN 'Valid'
    ELSE 'Invalid currency'
  END AS financial_validation_status
FROM `{{PROJECT_ID}}.llm_finops_raw.raw_ai_provider_cost`;
