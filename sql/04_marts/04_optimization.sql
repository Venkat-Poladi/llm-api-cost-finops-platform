CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.llm_finops_mart.mart_ai_optimization`
PARTITION BY billing_month
CLUSTER BY provider, optimization_type, evaluation_gate_status, model
AS
WITH token_base AS (
  SELECT
    t.billing_month,
    t.provider,
    t.provider_project_id,
    t.model,
    t.model_snapshot,
    t.usage_type,
    t.request_count,
    t.total_tokens,
    t.normalized_total_input_tokens,
    t.normalized_cache_read_tokens,
    t.cache_read_share,
    t.usage_cost_estimate,
    t.estimated_input_cost,
    t.estimated_batch_savings_opportunity,
    t.estimated_retry_cost,
    t.retry_cost_share,
    t.estimated_failed_attempt_cost,
    t.failed_attempt_cost_share,
    COALESCE(c.telemetry_token_coverage_pct, 0)
      AS telemetry_token_coverage_pct,
    COALESCE(c.untraceable_provider_usage_cost_estimate, 0)
      AS untraceable_provider_usage_cost_estimate
  FROM `{{PROJECT_ID}}.llm_finops_mart.mart_ai_token_economics` AS t
  LEFT JOIN
    `{{PROJECT_ID}}.llm_finops_mart.mart_ai_telemetry_coverage_monthly` AS c
    ON t.billing_month = c.billing_month
    AND t.provider = c.provider
    AND t.provider_project_id = c.provider_project_id
    AND t.model = c.model
    AND t.usage_type = c.usage_type
),
batch_recommendations AS (
  SELECT
    billing_month,
    provider,
    provider_project_id,
    model,
    model_snapshot,
    usage_type,
    'BATCH_MIGRATION' AS optimization_type,
    'Move eligible asynchronous workloads to Batch' AS recommendation_title,
    CONCAT(
      'The historical batch-rate comparison identifies ',
      FORMAT('%.2f', estimated_batch_savings_opportunity),
      ' USD of monthly modeled opportunity.'
    ) AS recommendation_rationale,
    usage_cost_estimate AS eligible_cost_base,
    CAST(0 AS NUMERIC) AS cost_at_risk,
    estimated_batch_savings_opportunity AS modeled_monthly_savings,
    estimated_batch_savings_opportunity * 12
      AS identified_annualized_savings,
    CAST(0 AS NUMERIC) AS approved_annualized_savings,
    CAST(0 AS NUMERIC) AS implemented_annualized_savings,
    CAST(0 AS NUMERIC) AS realized_savings,
    'IDENTIFIED' AS savings_stage,
    'READY_FOR_EVALUATION' AS evaluation_gate_status,
    'Historical batch rate exists and modeled monthly savings exceeds 5 USD.'
      AS gate_reason,
    'HIGH' AS savings_confidence,
    'Rate-based model' AS estimation_method,
    (
      'Assumes eligible nonbatch workloads can move to the matching historical '
      'Batch rate without changing request volume or output quality.'
    ) AS assumption_text,
    telemetry_token_coverage_pct,
    'NOT_REQUIRED' AS measurement_quality_status,
    FALSE AS requires_telemetry_remediation,
    FALSE AS is_approved,
    FALSE AS is_implemented,
    FALSE AS is_realized,
    'usage_cost_estimate' AS financial_basis,
    'USD' AS billing_currency
  FROM token_base
  WHERE estimated_batch_savings_opportunity >= 5
),
retry_recommendations AS (
  SELECT
    billing_month,
    provider,
    provider_project_id,
    model,
    model_snapshot,
    usage_type,
    'RETRY_REDUCTION' AS optimization_type,
    'Reduce avoidable retries' AS recommendation_title,
    CONCAT(
      'Request telemetry estimates ',
      FORMAT('%.2f', estimated_retry_cost),
      ' USD of monthly retry cost.'
    ) AS recommendation_rationale,
    usage_cost_estimate AS eligible_cost_base,
    estimated_retry_cost AS cost_at_risk,
    estimated_retry_cost * 0.50 AS modeled_monthly_savings,
    estimated_retry_cost * 0.50 * 12
      AS identified_annualized_savings,
    CAST(0 AS NUMERIC) AS approved_annualized_savings,
    CAST(0 AS NUMERIC) AS implemented_annualized_savings,
    CAST(0 AS NUMERIC) AS realized_savings,
    'IDENTIFIED' AS savings_stage,
    CASE
      WHEN telemetry_token_coverage_pct >= 0.95
        THEN 'READY_FOR_EVALUATION'
      ELSE 'HOLD_FOR_DATA'
    END AS evaluation_gate_status,
    CASE
      WHEN telemetry_token_coverage_pct >= 0.95
        THEN 'Telemetry coverage meets the 95 percent evaluation threshold.'
      ELSE 'Telemetry coverage is below 95 percent; improve measurement first.'
    END AS gate_reason,
    'MEDIUM' AS savings_confidence,
    'Assumption-based model' AS estimation_method,
    (
      'Models a 50 percent reduction in retry cost. This is not approved, '
      'implemented, or realized savings.'
    ) AS assumption_text,
    telemetry_token_coverage_pct,
    CASE
      WHEN telemetry_token_coverage_pct >= 0.95
        THEN 'SUFFICIENT'
      ELSE 'INSUFFICIENT'
    END AS measurement_quality_status,
    telemetry_token_coverage_pct < 0.95
      AS requires_telemetry_remediation,
    FALSE AS is_approved,
    FALSE AS is_implemented,
    FALSE AS is_realized,
    'usage_cost_estimate' AS financial_basis,
    'USD' AS billing_currency
  FROM token_base
  WHERE estimated_retry_cost >= 5
),
telemetry_recommendations AS (
  SELECT
    billing_month,
    provider,
    provider_project_id,
    model,
    model_snapshot,
    usage_type,
    'TELEMETRY_COVERAGE' AS optimization_type,
    'Improve request-level telemetry coverage' AS recommendation_title,
    CONCAT(
      FORMAT('%.2f', untraceable_provider_usage_cost_estimate),
      ' USD of monthly estimated provider usage cost is not traceable '
      'to complete request telemetry.'
    ) AS recommendation_rationale,
    usage_cost_estimate AS eligible_cost_base,
    untraceable_provider_usage_cost_estimate AS cost_at_risk,
    CAST(NULL AS NUMERIC) AS modeled_monthly_savings,
    CAST(0 AS NUMERIC) AS identified_annualized_savings,
    CAST(0 AS NUMERIC) AS approved_annualized_savings,
    CAST(0 AS NUMERIC) AS implemented_annualized_savings,
    CAST(0 AS NUMERIC) AS realized_savings,
    'UNQUANTIFIED' AS savings_stage,
    'HOLD_FOR_DATA' AS evaluation_gate_status,
    'Measurement must be improved before financial savings can be evaluated.'
      AS gate_reason,
    'UNQUANTIFIED' AS savings_confidence,
    'Cost-at-risk signal' AS estimation_method,
    (
      'The cost-at-risk value measures incomplete traceability. '
      'It is not a savings estimate.'
    ) AS assumption_text,
    telemetry_token_coverage_pct,
    'INSUFFICIENT' AS measurement_quality_status,
    TRUE AS requires_telemetry_remediation,
    FALSE AS is_approved,
    FALSE AS is_implemented,
    FALSE AS is_realized,
    'usage_cost_estimate' AS financial_basis,
    'USD' AS billing_currency
  FROM token_base
  WHERE telemetry_token_coverage_pct < 0.95
    AND untraceable_provider_usage_cost_estimate >= 1
),
cache_recommendations AS (
  SELECT
    billing_month,
    provider,
    provider_project_id,
    model,
    model_snapshot,
    usage_type,
    'CACHE_REUSE_ASSESSMENT' AS optimization_type,
    'Evaluate additional prompt-cache reuse' AS recommendation_title,
    CONCAT(
      'Observed cache-read share is ',
      FORMAT('%.1f', COALESCE(cache_read_share, 0) * 100),
      ' percent, below the 20 percent benchmark.'
    ) AS recommendation_rationale,
    estimated_input_cost AS eligible_cost_base,
    estimated_input_cost AS cost_at_risk,
    CAST(NULL AS NUMERIC) AS modeled_monthly_savings,
    CAST(0 AS NUMERIC) AS identified_annualized_savings,
    CAST(0 AS NUMERIC) AS approved_annualized_savings,
    CAST(0 AS NUMERIC) AS implemented_annualized_savings,
    CAST(0 AS NUMERIC) AS realized_savings,
    'UNQUANTIFIED' AS savings_stage,
    'REQUIRES_BENCHMARK' AS evaluation_gate_status,
    (
      'Run a controlled benchmark because future cache-hit improvement '
      'and cache-write behavior are not yet proven.'
    ) AS gate_reason,
    'UNQUANTIFIED' AS savings_confidence,
    'Benchmark required' AS estimation_method,
    (
      'No savings amount is assigned until a controlled cache experiment '
      'measures hit-rate change, write overhead, quality, and latency.'
    ) AS assumption_text,
    telemetry_token_coverage_pct,
    CASE
      WHEN telemetry_token_coverage_pct >= 0.95
        THEN 'SUFFICIENT'
      ELSE 'INSUFFICIENT'
    END AS measurement_quality_status,
    telemetry_token_coverage_pct < 0.95
      AS requires_telemetry_remediation,
    FALSE AS is_approved,
    FALSE AS is_implemented,
    FALSE AS is_realized,
    'usage_cost_estimate' AS financial_basis,
    'USD' AS billing_currency
  FROM token_base
  WHERE usage_type = 'text_generation'
    AND normalized_total_input_tokens > 0
    AND COALESCE(cache_read_share, 0) < 0.20
    AND estimated_input_cost >= 5
),
combined AS (
  SELECT * FROM batch_recommendations
  UNION ALL
  SELECT * FROM retry_recommendations
  UNION ALL
  SELECT * FROM telemetry_recommendations
  UNION ALL
  SELECT * FROM cache_recommendations
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
          optimization_type
        )
      )
    )
  ) AS recommendation_id,
  *,
  CASE
    WHEN evaluation_gate_status = 'READY_FOR_EVALUATION'
      THEN 1
    ELSE 0
  END AS evaluation_ready_flag,
  CURRENT_DATE() AS recommendation_generated_date
FROM combined;
