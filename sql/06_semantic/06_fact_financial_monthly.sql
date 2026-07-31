CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.{{MART_DATASET}}.fact_ai_financial_monthly`
PARTITION BY billing_month
CLUSTER BY provider_key, model_key, application_key, line_item_type
AS
WITH normalized AS (
  SELECT
    billing_month,
    provider,
    provider_project_id,
    COALESCE(model, 'Not applicable') AS model,
    COALESCE(model_snapshot, 'Not applicable') AS model_snapshot,
    COALESCE(usage_type, 'Not applicable') AS usage_type,
    line_item_scope,
    line_item_type,
    COALESCE(application_name, 'Unallocated') AS application_name,
    COALESCE(department_name, 'Unallocated') AS department_name,
    COALESCE(cost_center, 'UNALLOCATED') AS cost_center,
    allocation_status,
    allocation_method,
    allocation_confidence,
    COALESCE(is_historical_restatement, FALSE)
      AS is_historical_restatement,
    COALESCE(distributed_request_count, CAST(0 AS NUMERIC))
      AS distributed_request_count,
    COALESCE(distributed_total_input_tokens, CAST(0 AS NUMERIC))
      AS distributed_total_input_tokens,
    COALESCE(distributed_output_tokens, CAST(0 AS NUMERIC))
      AS distributed_output_tokens,
    COALESCE(distributed_reasoning_tokens, CAST(0 AS NUMERIC))
      AS distributed_reasoning_tokens,
    COALESCE(allocated_usage_cost_estimate, CAST(0 AS NUMERIC))
      + COALESCE(unallocated_usage_cost_estimate, CAST(0 AS NUMERIC))
      AS usage_cost_estimate,
    COALESCE(allocated_provider_reported_cost, CAST(0 AS NUMERIC))
      + COALESCE(unallocated_provider_reported_cost, CAST(0 AS NUMERIC))
      AS provider_reported_cost,
    COALESCE(allocated_invoice_billed_cost, CAST(0 AS NUMERIC))
      + COALESCE(unallocated_invoice_billed_cost, CAST(0 AS NUMERIC))
      AS invoice_billed_cost,
    COALESCE(allocated_invoice_billed_cost, CAST(0 AS NUMERIC))
      AS allocated_invoice_billed_cost,
    COALESCE(unallocated_invoice_billed_cost, CAST(0 AS NUMERIC))
      AS unallocated_invoice_billed_cost,
    billing_currency,
    financial_basis
  FROM `{{PROJECT_ID}}.{{MART_DATASET}}.mart_ai_application_cost`
),
aggregated AS (
  SELECT
    billing_month,
    provider,
    provider_project_id,
    model,
    model_snapshot,
    usage_type,
    line_item_scope,
    line_item_type,
    application_name,
    department_name,
    cost_center,
    allocation_status,
    allocation_method,
    allocation_confidence,
    LOGICAL_OR(is_historical_restatement)
      AS has_historical_restatement,
    SUM(distributed_request_count) AS distributed_request_count,
    SUM(distributed_total_input_tokens) AS distributed_total_input_tokens,
    SUM(distributed_output_tokens) AS distributed_output_tokens,
    SUM(distributed_reasoning_tokens) AS distributed_reasoning_tokens,
    SUM(usage_cost_estimate) AS usage_cost_estimate,
    SUM(provider_reported_cost) AS provider_reported_cost,
    SUM(invoice_billed_cost) AS invoice_billed_cost,
    SUM(allocated_invoice_billed_cost) AS allocated_invoice_billed_cost,
    SUM(unallocated_invoice_billed_cost) AS unallocated_invoice_billed_cost,
    ANY_VALUE(billing_currency) AS billing_currency,
    ANY_VALUE(financial_basis) AS financial_basis
  FROM normalized
  GROUP BY
    billing_month,
    provider,
    provider_project_id,
    model,
    model_snapshot,
    usage_type,
    line_item_scope,
    line_item_type,
    application_name,
    department_name,
    cost_center,
    allocation_status,
    allocation_method,
    allocation_confidence
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
          usage_type,
          line_item_scope,
          line_item_type,
          application_name,
          department_name,
          cost_center,
          allocation_status,
          allocation_method,
          allocation_confidence
        )
      )
    )
  ) AS financial_monthly_id,
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
  TO_HEX(
    SHA256(
      TO_JSON_STRING(
        STRUCT(application_name, department_name, cost_center)
      )
    )
  ) AS application_key,
  provider,
  provider_project_id,
  model,
  model_snapshot,
  usage_type,
  line_item_scope,
  line_item_type,
  application_name,
  department_name,
  cost_center,
  allocation_status,
  allocation_method,
  allocation_confidence,
  has_historical_restatement,
  distributed_request_count,
  distributed_total_input_tokens,
  distributed_output_tokens,
  distributed_reasoning_tokens,
  usage_cost_estimate,
  provider_reported_cost,
  invoice_billed_cost,
  allocated_invoice_billed_cost,
  unallocated_invoice_billed_cost,
  billing_currency,
  financial_basis
FROM aggregated;
