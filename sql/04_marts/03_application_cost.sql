CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.llm_finops_mart.mart_ai_application_cost`
PARTITION BY billing_month
CLUSTER BY provider, application_name, department_name, line_item_type
AS
WITH usage_invoice_scope AS (
  SELECT
    billing_month,
    provider,
    provider_project_id,
    model,
    line_item_scope,
    line_item_type,
    COUNT(*) AS source_line_count,
    SUM(usage_cost_estimate) AS source_usage_cost_estimate,
    SUM(provider_reported_cost) AS source_provider_reported_cost,
    SUM(invoice_billed_cost) AS source_invoice_billed_cost,
    ANY_VALUE(billing_currency) AS billing_currency,
    LOGICAL_OR(is_restatement) AS is_restatement,
    LOGICAL_AND(is_synthetic) AS is_synthetic
  FROM `{{PROJECT_ID}}.llm_finops_core.fct_ai_cost_reconciliation`
  WHERE line_item_type = 'usage'
  GROUP BY
    billing_month,
    provider,
    provider_project_id,
    model,
    line_item_scope,
    line_item_type
),
driver_with_scope AS (
  SELECT
    i.*,
    d.model_snapshot,
    d.usage_type,
    d.application_name,
    d.department_name,
    d.cost_center,
    d.allocation_status,
    d.allocation_method,
    d.allocation_confidence,
    d.is_historical_restatement,
    d.distributed_request_count,
    d.distributed_total_input_tokens,
    d.distributed_output_tokens,
    d.distributed_reasoning_tokens,
    d.driver_usage_cost_estimate,
    SUM(d.driver_usage_cost_estimate) OVER (
      PARTITION BY
        i.billing_month,
        i.provider,
        i.provider_project_id,
        i.model,
        i.line_item_scope,
        i.line_item_type
    ) AS eligible_driver_denominator
  FROM usage_invoice_scope AS i
  LEFT JOIN
    `{{PROJECT_ID}}.llm_finops_staging.stg_ai_application_invoice_driver_monthly`
      AS d
    ON i.billing_month = d.billing_month
    AND i.provider = d.provider
    AND i.provider_project_id = d.provider_project_id
    AND i.model = d.model
),
usage_with_driver AS (
  SELECT
    *,
    SAFE_DIVIDE(
      driver_usage_cost_estimate,
      eligible_driver_denominator
    ) AS financial_allocation_share,
    ROW_NUMBER() OVER (
      PARTITION BY
        billing_month,
        provider,
        provider_project_id,
        model,
        line_item_scope,
        line_item_type
      ORDER BY
        CASE WHEN allocation_status = 'Allocated' THEN 0 ELSE 1 END,
        application_name,
        department_name,
        cost_center
    ) AS source_measure_anchor_number
  FROM driver_with_scope
  WHERE eligible_driver_denominator > 0
),
usage_allocated_rows AS (
  SELECT
    TO_HEX(
      SHA256(
        TO_JSON_STRING(
          STRUCT(
            billing_month,
            provider,
            provider_project_id,
            model,
            line_item_scope,
            line_item_type,
            application_name,
            department_name,
            cost_center,
            allocation_status
          )
        )
      )
    ) AS application_cost_id,
    TO_HEX(
      SHA256(
        TO_JSON_STRING(
          STRUCT(
            billing_month,
            provider,
            provider_project_id,
            model,
            line_item_scope,
            line_item_type
          )
        )
      )
    ) AS financial_source_scope_id,
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
    is_historical_restatement,
    is_restatement,
    source_line_count,
    driver_usage_cost_estimate,
    eligible_driver_denominator,
    financial_allocation_share,
    distributed_request_count,
    distributed_total_input_tokens,
    distributed_output_tokens,
    distributed_reasoning_tokens,
    source_measure_anchor_number = 1 AS source_measure_anchor_flag,
    IF(
      source_measure_anchor_number = 1,
      source_usage_cost_estimate,
      NULL
    ) AS source_usage_cost_estimate,
    IF(
      source_measure_anchor_number = 1,
      source_provider_reported_cost,
      NULL
    ) AS source_provider_reported_cost,
    IF(
      source_measure_anchor_number = 1,
      source_invoice_billed_cost,
      NULL
    ) AS source_invoice_billed_cost,
    IF(
      allocation_status = 'Allocated',
      driver_usage_cost_estimate,
      0
    ) AS allocated_usage_cost_estimate,
    IF(
      allocation_status = 'Unallocated',
      driver_usage_cost_estimate,
      0
    ) AS unallocated_usage_cost_estimate,
    IF(
      allocation_status = 'Allocated',
      source_provider_reported_cost * financial_allocation_share,
      0
    ) AS allocated_provider_reported_cost,
    IF(
      allocation_status = 'Unallocated',
      source_provider_reported_cost * financial_allocation_share,
      0
    ) AS unallocated_provider_reported_cost,
    IF(
      allocation_status = 'Allocated',
      source_invoice_billed_cost * financial_allocation_share,
      0
    ) AS allocated_invoice_billed_cost,
    IF(
      allocation_status = 'Unallocated',
      source_invoice_billed_cost * financial_allocation_share,
      0
    ) AS unallocated_invoice_billed_cost,
    billing_currency,
    'invoice_billed_cost' AS financial_basis,
    'Allocated invoiced cost' AS cost_basis_label,
    is_synthetic
  FROM usage_with_driver
),
usage_without_driver AS (
  SELECT
    TO_HEX(
      SHA256(
        TO_JSON_STRING(
          STRUCT(
            billing_month,
            provider,
            provider_project_id,
            model,
            line_item_scope,
            line_item_type,
            'NO_ELIGIBLE_DRIVER'
          )
        )
      )
    ) AS application_cost_id,
    TO_HEX(
      SHA256(
        TO_JSON_STRING(
          STRUCT(
            billing_month,
            provider,
            provider_project_id,
            model,
            line_item_scope,
            line_item_type
          )
        )
      )
    ) AS financial_source_scope_id,
    billing_month,
    provider,
    provider_project_id,
    model,
    CAST(NULL AS STRING) AS model_snapshot,
    CAST(NULL AS STRING) AS usage_type,
    line_item_scope,
    line_item_type,
    'Unallocated' AS application_name,
    'Unallocated' AS department_name,
    'UNALLOCATED' AS cost_center,
    'Unallocated' AS allocation_status,
    'no_eligible_driver' AS allocation_method,
    'none' AS allocation_confidence,
    FALSE AS is_historical_restatement,
    is_restatement,
    source_line_count,
    CAST(0 AS NUMERIC) AS driver_usage_cost_estimate,
    CAST(0 AS NUMERIC) AS eligible_driver_denominator,
    CAST(NULL AS NUMERIC) AS financial_allocation_share,
    CAST(0 AS NUMERIC) AS distributed_request_count,
    CAST(0 AS NUMERIC) AS distributed_total_input_tokens,
    CAST(0 AS NUMERIC) AS distributed_output_tokens,
    CAST(0 AS NUMERIC) AS distributed_reasoning_tokens,
    TRUE AS source_measure_anchor_flag,
    source_usage_cost_estimate,
    source_provider_reported_cost,
    source_invoice_billed_cost,
    CAST(0 AS NUMERIC) AS allocated_usage_cost_estimate,
    source_usage_cost_estimate AS unallocated_usage_cost_estimate,
    CAST(0 AS NUMERIC) AS allocated_provider_reported_cost,
    source_provider_reported_cost AS unallocated_provider_reported_cost,
    CAST(0 AS NUMERIC) AS allocated_invoice_billed_cost,
    source_invoice_billed_cost AS unallocated_invoice_billed_cost,
    billing_currency,
    'invoice_billed_cost' AS financial_basis,
    'Allocated invoiced cost' AS cost_basis_label,
    is_synthetic
  FROM driver_with_scope
  WHERE eligible_driver_denominator IS NULL
     OR eligible_driver_denominator = 0
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY
      billing_month,
      provider,
      provider_project_id,
      model,
      line_item_scope,
      line_item_type
    ORDER BY billing_month
  ) = 1
),
non_usage_scope AS (
  SELECT
    billing_month,
    provider,
    provider_project_id,
    model,
    line_item_scope,
    line_item_type,
    COUNT(*) AS source_line_count,
    SUM(provider_reported_cost) AS source_provider_reported_cost,
    SUM(invoice_billed_cost) AS source_invoice_billed_cost,
    ANY_VALUE(billing_currency) AS billing_currency,
    LOGICAL_OR(is_restatement) AS is_restatement,
    LOGICAL_AND(is_synthetic) AS is_synthetic
  FROM `{{PROJECT_ID}}.llm_finops_core.fct_ai_cost_reconciliation`
  WHERE line_item_type != 'usage'
  GROUP BY
    billing_month,
    provider,
    provider_project_id,
    model,
    line_item_scope,
    line_item_type
),
non_usage_rows AS (
  SELECT
    TO_HEX(
      SHA256(
        TO_JSON_STRING(
          STRUCT(
            billing_month,
            provider,
            provider_project_id,
            model,
            line_item_scope,
            line_item_type,
            'SCOPE_RETAINED'
          )
        )
      )
    ) AS application_cost_id,
    TO_HEX(
      SHA256(
        TO_JSON_STRING(
          STRUCT(
            billing_month,
            provider,
            provider_project_id,
            model,
            line_item_scope,
            line_item_type
          )
        )
      )
    ) AS financial_source_scope_id,
    billing_month,
    provider,
    provider_project_id,
    model,
    CAST(NULL AS STRING) AS model_snapshot,
    CAST(NULL AS STRING) AS usage_type,
    line_item_scope,
    line_item_type,
    'Unallocated' AS application_name,
    'Unallocated' AS department_name,
    'UNALLOCATED' AS cost_center,
    'Financial scope retained' AS allocation_status,
    'scope_retained' AS allocation_method,
    'none' AS allocation_confidence,
    FALSE AS is_historical_restatement,
    is_restatement,
    source_line_count,
    CAST(NULL AS NUMERIC) AS driver_usage_cost_estimate,
    CAST(NULL AS NUMERIC) AS eligible_driver_denominator,
    CAST(NULL AS NUMERIC) AS financial_allocation_share,
    CAST(NULL AS NUMERIC) AS distributed_request_count,
    CAST(NULL AS NUMERIC) AS distributed_total_input_tokens,
    CAST(NULL AS NUMERIC) AS distributed_output_tokens,
    CAST(NULL AS NUMERIC) AS distributed_reasoning_tokens,
    TRUE AS source_measure_anchor_flag,
    CAST(NULL AS NUMERIC) AS source_usage_cost_estimate,
    source_provider_reported_cost,
    source_invoice_billed_cost,
    CAST(NULL AS NUMERIC) AS allocated_usage_cost_estimate,
    CAST(NULL AS NUMERIC) AS unallocated_usage_cost_estimate,
    CAST(0 AS NUMERIC) AS allocated_provider_reported_cost,
    source_provider_reported_cost AS unallocated_provider_reported_cost,
    CAST(0 AS NUMERIC) AS allocated_invoice_billed_cost,
    source_invoice_billed_cost AS unallocated_invoice_billed_cost,
    billing_currency,
    'invoice_billed_cost' AS financial_basis,
    'Scope-retained invoiced cost' AS cost_basis_label,
    is_synthetic
  FROM non_usage_scope
)
SELECT * FROM usage_allocated_rows
UNION ALL
SELECT * FROM usage_without_driver
UNION ALL
SELECT * FROM non_usage_rows;
