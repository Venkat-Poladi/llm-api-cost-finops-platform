CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.llm_finops_core.fct_ai_cost_reconciliation`
PARTITION BY billing_month
CLUSTER BY provider, provider_project_id, line_item_type, model
AS
WITH joined AS (
  SELECT
    TO_HEX(
      SHA256(
        TO_JSON_STRING(
          STRUCT(
            c.billing_month,
            c.provider,
            c.provider_project_id,
            c.model,
            c.line_item_type,
            c.provider_line_item_id
          )
        )
      )
    ) AS reconciliation_fact_id,
    c.billing_period,
    c.billing_month,
    c.provider,
    c.provider_project_id,
    c.model,
    c.line_item_scope,
    c.line_item_type,
    c.provider_line_item_id,
    c.provider_reported_cost,
    c.invoice_billed_cost,
    c.billing_currency,
    c.credit_amount,
    c.adjustment_reason AS source_adjustment_reason,
    c.invoice_issue_date,
    c.is_restatement,
    c.is_synthetic,
    c.usage_reconciliation_applicability,
    IF(u.billing_month IS NULL, 0, 1) AS usage_rollup_match_count,
    IF(c.line_item_type = 'usage', u.source_daily_row_count, NULL)
      AS source_daily_row_count,
    IF(c.line_item_type = 'usage', u.distinct_api_key_count, NULL)
      AS distinct_api_key_count,
    IF(c.line_item_type = 'usage', u.request_count, NULL)
      AS request_count,
    IF(c.line_item_type = 'usage', u.normalized_total_input_tokens, NULL)
      AS normalized_total_input_tokens,
    IF(c.line_item_type = 'usage', u.output_tokens, NULL)
      AS output_tokens,
    IF(c.line_item_type = 'usage', u.reasoning_tokens, NULL)
      AS reasoning_tokens,
    IF(c.line_item_type = 'usage', u.usage_cost_estimate, NULL)
      AS usage_cost_estimate,
    IF(c.line_item_type = 'usage', u.estimate_currency, NULL)
      AS estimate_currency,
    IF(c.line_item_type = 'usage', u.unpriced_daily_row_count, NULL)
      AS unpriced_daily_row_count
  FROM `{{PROJECT_ID}}.llm_finops_staging.stg_ai_provider_cost` AS c
  LEFT JOIN
    `{{PROJECT_ID}}.llm_finops_staging.stg_ai_usage_cost_monthly` AS u
    ON c.line_item_type = 'usage'
    AND c.billing_month = u.billing_month
    AND c.provider = u.provider
    AND c.provider_project_id = u.provider_project_id
    AND c.model = u.model
),
variances AS (
  SELECT
    *,
    CASE
      WHEN line_item_type = 'usage'
        THEN provider_reported_cost - usage_cost_estimate
      ELSE NULL
    END AS usage_to_reported_variance,
    invoice_billed_cost - provider_reported_cost
      AS reported_to_invoice_variance
  FROM joined
),
percentages AS (
  SELECT
    *,
    CASE
      WHEN line_item_type = 'usage'
        THEN SAFE_DIVIDE(
          usage_to_reported_variance,
          ABS(usage_cost_estimate)
        )
      ELSE NULL
    END AS usage_to_reported_variance_pct,
    SAFE_DIVIDE(
      reported_to_invoice_variance,
      ABS(provider_reported_cost)
    ) AS reported_to_invoice_variance_pct
  FROM variances
),
statuses AS (
  SELECT
    *,
    CASE
      WHEN line_item_type != 'usage' THEN 'NOT_APPLICABLE'
      WHEN usage_cost_estimate IS NULL THEN 'EXCEPTION'
      WHEN ABS(usage_to_reported_variance) <= 1.00 THEN 'PASS'
      WHEN ABS(usage_to_reported_variance_pct) <= 0.01 THEN 'PASS'
      ELSE 'EXCEPTION'
    END AS usage_reconciliation_status,
    CASE
      WHEN ABS(reported_to_invoice_variance) <= 1.00 THEN 'PASS'
      WHEN ABS(reported_to_invoice_variance_pct) <= 0.01 THEN 'PASS'
      ELSE 'EXCEPTION'
    END AS invoice_reconciliation_status
  FROM percentages
),
reason_codes AS (
  SELECT
    *,
    CASE
      WHEN usage_reconciliation_status != 'EXCEPTION' THEN NULL
      WHEN usage_cost_estimate IS NULL THEN 'MISSING_USAGE_ESTIMATE'
      WHEN source_adjustment_reason IN ('LATE_USAGE', 'INVOICE_CUTOFF')
        THEN source_adjustment_reason
      WHEN source_adjustment_reason = 'ROUTINE_ROUNDING'
        THEN 'INDEPENDENT_SOURCE_ESTIMATE_DIFFERENCE'
      ELSE COALESCE(
        source_adjustment_reason,
        'UNCLASSIFIED_USAGE_VARIANCE'
      )
    END AS usage_variance_reason_code,
    CASE
      WHEN invoice_reconciliation_status != 'EXCEPTION' THEN NULL
      ELSE COALESCE(
        source_adjustment_reason,
        CASE
          WHEN line_item_type = 'credit' THEN 'CREDIT'
          WHEN line_item_type = 'tax' THEN 'TAX'
          WHEN line_item_type = 'commitment_true_up'
            THEN 'COMMITMENT_TRUE_UP'
          WHEN line_item_type = 'correction' THEN 'CORRECTION'
          WHEN line_item_type = 'adjustment' THEN 'ADJUSTMENT'
          ELSE 'UNCLASSIFIED_INVOICE_VARIANCE'
        END
      )
    END AS invoice_variance_reason_code
  FROM statuses
)
SELECT
  *,
  CASE
    WHEN usage_reconciliation_status = 'EXCEPTION'
      AND invoice_reconciliation_status = 'EXCEPTION'
      THEN CONCAT(
        usage_variance_reason_code,
        '|',
        invoice_variance_reason_code
      )
    WHEN usage_reconciliation_status = 'EXCEPTION'
      THEN usage_variance_reason_code
    WHEN invoice_reconciliation_status = 'EXCEPTION'
      THEN invoice_variance_reason_code
    ELSE NULL
  END AS variance_reason_code,
  CASE
    WHEN usage_reconciliation_status = 'EXCEPTION'
      OR invoice_reconciliation_status = 'EXCEPTION'
      THEN 'EXCEPTION'
    ELSE 'PASS'
  END AS exception_status
FROM reason_codes;
