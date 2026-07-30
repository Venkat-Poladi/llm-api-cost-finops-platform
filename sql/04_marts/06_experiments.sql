CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.llm_finops_mart.mart_ai_experiments`
PARTITION BY evaluation_date
CLUSTER BY experiment_id, spending_limit_period, threshold_status, governance_action_status
AS
WITH controls AS (
  SELECT
    experiment_id,
    owner,
    approver,
    hypothesis,
    application_name,
    cost_center,
    spending_limit,
    spending_limit_period,
    limit_currency,
    warning_threshold,
    hard_stop_threshold,
    start_date,
    planned_end_date,
    current_status AS source_current_status,
    override_reason
  FROM `{{PROJECT_ID}}.llm_finops_raw.dim_ai_experiment_control`
),
calendar AS (
  SELECT
    c.*,
    calendar_date
  FROM controls AS c
  CROSS JOIN UNNEST(
    GENERATE_DATE_ARRAY(c.start_date, c.planned_end_date)
  ) AS calendar_date
),
daily AS (
  SELECT
    c.*,
    COALESCE(SUM(d.experiment_driver_cost_estimate), 0)
      AS daily_driver_cost_estimate,
    COALESCE(SUM(d.allocated_provider_reported_experiment_cost), 0)
      AS daily_provider_reported_experiment_cost,
    COALESCE(SUM(d.allocated_invoice_billed_experiment_cost), 0)
      AS daily_invoice_billed_experiment_cost,
    COALESCE(SUM(d.telemetry_attempt_count), 0)
      AS daily_telemetry_attempt_count,
    COALESCE(SUM(d.telemetry_logical_request_count), 0)
      AS daily_logical_request_count,
    COALESCE(SUM(d.successful_logical_request_count), 0)
      AS daily_successful_request_count,
    COALESCE(SUM(d.retry_attempt_count), 0)
      AS daily_retry_attempt_count,
    COALESCE(SUM(d.estimated_retry_cost), 0)
      AS daily_estimated_retry_cost,
    CASE
      WHEN COUNT(d.experiment_driver_id) = 0 THEN 'NO_ACTIVITY'
      WHEN COUNTIF(d.measurement_quality_status = 'LIMITED') > 0
        THEN 'LIMITED'
      ELSE 'SUFFICIENT'
    END AS daily_measurement_quality_status,
    CASE
      WHEN COUNT(d.experiment_driver_id) = 0 THEN 'NO_ACTIVITY'
      WHEN COUNTIF(d.spend_quality_label = 'LOWER_BOUND') > 0
        THEN 'LOWER_BOUND'
      ELSE 'BEST_ESTIMATE'
    END AS daily_spend_quality_label
  FROM calendar AS c
  LEFT JOIN
    `{{PROJECT_ID}}.llm_finops_staging.stg_ai_experiment_invoice_driver_daily`
      AS d
    ON c.experiment_id = d.experiment_id
    AND c.calendar_date = d.usage_date
  GROUP BY
    c.experiment_id,
    c.owner,
    c.approver,
    c.hypothesis,
    c.application_name,
    c.cost_center,
    c.spending_limit,
    c.spending_limit_period,
    c.limit_currency,
    c.warning_threshold,
    c.hard_stop_threshold,
    c.start_date,
    c.planned_end_date,
    c.source_current_status,
    c.override_reason,
    c.calendar_date
),
daily_periods AS (
  SELECT
    experiment_id,
    owner,
    approver,
    hypothesis,
    application_name,
    cost_center,
    spending_limit,
    spending_limit_period,
    limit_currency,
    warning_threshold,
    hard_stop_threshold,
    start_date,
    planned_end_date,
    source_current_status,
    override_reason,
    calendar_date AS evaluation_date,
    calendar_date AS period_start_date,
    calendar_date AS period_end_date,
    daily_invoice_billed_experiment_cost
      AS period_invoice_billed_experiment_cost,
    daily_provider_reported_experiment_cost
      AS period_provider_reported_experiment_cost,
    daily_driver_cost_estimate AS period_driver_cost_estimate,
    daily_telemetry_attempt_count AS period_telemetry_attempt_count,
    daily_logical_request_count AS period_logical_request_count,
    daily_successful_request_count AS period_successful_request_count,
    daily_retry_attempt_count AS period_retry_attempt_count,
    daily_estimated_retry_cost AS period_estimated_retry_cost,
    daily_measurement_quality_status AS period_measurement_quality_status,
    daily_spend_quality_label AS period_spend_quality_label
  FROM daily
  WHERE spending_limit_period = 'day'
),
monthly_periods AS (
  SELECT
    experiment_id,
    ANY_VALUE(owner) AS owner,
    ANY_VALUE(approver) AS approver,
    ANY_VALUE(hypothesis) AS hypothesis,
    ANY_VALUE(application_name) AS application_name,
    ANY_VALUE(cost_center) AS cost_center,
    ANY_VALUE(spending_limit) AS spending_limit,
    ANY_VALUE(spending_limit_period) AS spending_limit_period,
    ANY_VALUE(limit_currency) AS limit_currency,
    ANY_VALUE(warning_threshold) AS warning_threshold,
    ANY_VALUE(hard_stop_threshold) AS hard_stop_threshold,
    ANY_VALUE(start_date) AS start_date,
    ANY_VALUE(planned_end_date) AS planned_end_date,
    ANY_VALUE(source_current_status) AS source_current_status,
    ANY_VALUE(override_reason) AS override_reason,
    MAX(calendar_date) AS evaluation_date,
    MIN(calendar_date) AS period_start_date,
    MAX(calendar_date) AS period_end_date,
    SUM(daily_invoice_billed_experiment_cost)
      AS period_invoice_billed_experiment_cost,
    SUM(daily_provider_reported_experiment_cost)
      AS period_provider_reported_experiment_cost,
    SUM(daily_driver_cost_estimate) AS period_driver_cost_estimate,
    SUM(daily_telemetry_attempt_count) AS period_telemetry_attempt_count,
    SUM(daily_logical_request_count) AS period_logical_request_count,
    SUM(daily_successful_request_count) AS period_successful_request_count,
    SUM(daily_retry_attempt_count) AS period_retry_attempt_count,
    SUM(daily_estimated_retry_cost) AS period_estimated_retry_cost,
    CASE
      WHEN SUM(daily_telemetry_attempt_count) = 0 THEN 'NO_ACTIVITY'
      WHEN COUNTIF(daily_measurement_quality_status = 'LIMITED') > 0
        THEN 'LIMITED'
      ELSE 'SUFFICIENT'
    END AS period_measurement_quality_status,
    CASE
      WHEN SUM(daily_telemetry_attempt_count) = 0 THEN 'NO_ACTIVITY'
      WHEN COUNTIF(daily_spend_quality_label = 'LOWER_BOUND') > 0
        THEN 'LOWER_BOUND'
      ELSE 'BEST_ESTIMATE'
    END AS period_spend_quality_label
  FROM daily
  WHERE spending_limit_period = 'month'
  GROUP BY
    experiment_id,
    DATE_TRUNC(calendar_date, MONTH)
),
lifetime_periods AS (
  SELECT
    experiment_id,
    owner,
    approver,
    hypothesis,
    application_name,
    cost_center,
    spending_limit,
    spending_limit_period,
    limit_currency,
    warning_threshold,
    hard_stop_threshold,
    start_date,
    planned_end_date,
    source_current_status,
    override_reason,
    calendar_date AS evaluation_date,
    start_date AS period_start_date,
    calendar_date AS period_end_date,
    SUM(daily_invoice_billed_experiment_cost) OVER (
      PARTITION BY experiment_id
      ORDER BY calendar_date
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS period_invoice_billed_experiment_cost,
    SUM(daily_provider_reported_experiment_cost) OVER (
      PARTITION BY experiment_id
      ORDER BY calendar_date
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS period_provider_reported_experiment_cost,
    SUM(daily_driver_cost_estimate) OVER (
      PARTITION BY experiment_id
      ORDER BY calendar_date
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS period_driver_cost_estimate,
    SUM(daily_telemetry_attempt_count) OVER (
      PARTITION BY experiment_id
      ORDER BY calendar_date
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS period_telemetry_attempt_count,
    SUM(daily_logical_request_count) OVER (
      PARTITION BY experiment_id
      ORDER BY calendar_date
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS period_logical_request_count,
    SUM(daily_successful_request_count) OVER (
      PARTITION BY experiment_id
      ORDER BY calendar_date
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS period_successful_request_count,
    SUM(daily_retry_attempt_count) OVER (
      PARTITION BY experiment_id
      ORDER BY calendar_date
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS period_retry_attempt_count,
    SUM(daily_estimated_retry_cost) OVER (
      PARTITION BY experiment_id
      ORDER BY calendar_date
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS period_estimated_retry_cost,
    CASE
      WHEN SUM(daily_telemetry_attempt_count) OVER (
        PARTITION BY experiment_id
        ORDER BY calendar_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
      ) = 0 THEN 'NO_ACTIVITY'
      WHEN COUNTIF(daily_measurement_quality_status = 'LIMITED') OVER (
        PARTITION BY experiment_id
        ORDER BY calendar_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
      ) > 0 THEN 'LIMITED'
      ELSE 'SUFFICIENT'
    END AS period_measurement_quality_status,
    CASE
      WHEN SUM(daily_telemetry_attempt_count) OVER (
        PARTITION BY experiment_id
        ORDER BY calendar_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
      ) = 0 THEN 'NO_ACTIVITY'
      WHEN COUNTIF(daily_spend_quality_label = 'LOWER_BOUND') OVER (
        PARTITION BY experiment_id
        ORDER BY calendar_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
      ) > 0 THEN 'LOWER_BOUND'
      ELSE 'BEST_ESTIMATE'
    END AS period_spend_quality_label
  FROM daily
  WHERE spending_limit_period = 'lifetime'
),
periodized AS (
  SELECT * FROM daily_periods
  UNION ALL
  SELECT * FROM monthly_periods
  UNION ALL
  SELECT * FROM lifetime_periods
),
thresholds AS (
  SELECT
    *,
    spending_limit * warning_threshold AS warning_spend_threshold,
    spending_limit * hard_stop_threshold AS hard_stop_spend_threshold,
    SAFE_DIVIDE(
      period_invoice_billed_experiment_cost,
      spending_limit
    ) AS spend_to_limit_pct,
    CASE
      WHEN period_invoice_billed_experiment_cost
        >= spending_limit * hard_stop_threshold
        THEN 'HARD_STOP'
      WHEN period_invoice_billed_experiment_cost
        >= spending_limit * warning_threshold
        THEN 'WARNING'
      ELSE 'WITHIN_LIMIT'
    END AS threshold_status
  FROM periodized
),
history AS (
  SELECT
    *,
    MAX(period_invoice_billed_experiment_cost) OVER (
      PARTITION BY experiment_id
      ORDER BY evaluation_date
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS max_period_spend_to_date,
    MIN(
      IF(threshold_status = 'WARNING', evaluation_date, NULL)
    ) OVER (
      PARTITION BY experiment_id
    ) AS first_warning_date,
    MIN(
      IF(threshold_status = 'HARD_STOP', evaluation_date, NULL)
    ) OVER (
      PARTITION BY experiment_id
    ) AS first_hard_stop_date
  FROM thresholds
),
resolved AS (
  SELECT
    h.*,
    d.experiment_decision_id AS latest_experiment_decision_id,
    d.decision AS latest_decision,
    d.decision_date AS latest_decision_date,
    d.decided_by AS latest_decided_by,
    d.rationale AS latest_decision_rationale,
    d.previous_status AS latest_previous_status,
    d.new_status AS decision_status_as_of_date
  FROM history AS h
  LEFT JOIN
    `{{PROJECT_ID}}.llm_finops_raw.fct_ai_experiment_decision` AS d
    ON d.experiment_id = h.experiment_id
    AND d.decision_date <= h.evaluation_date
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY
      h.experiment_id,
      h.spending_limit_period,
      h.evaluation_date,
      h.period_start_date,
      h.period_end_date
    ORDER BY
      d.decision_date DESC,
      d.experiment_decision_id DESC
  ) = 1
)
SELECT
  TO_HEX(
    SHA256(
      TO_JSON_STRING(
        STRUCT(
          experiment_id,
          spending_limit_period,
          evaluation_date,
          period_start_date,
          period_end_date
        )
      )
    )
  ) AS experiment_governance_id,
  *,
  CASE
    WHEN threshold_status = 'HARD_STOP'
      AND decision_status_as_of_date = 'stopped'
      THEN 'HARD_STOP_COMPLIANT'
    WHEN threshold_status = 'HARD_STOP'
      THEN 'HARD_STOP_ACTION_REQUIRED'
    WHEN threshold_status = 'WARNING'
      THEN 'WARNING_REVIEW_REQUIRED'
    ELSE 'WITHIN_LIMIT'
  END AS governance_action_status,
  CASE
    WHEN latest_decision = 'Stop'
      AND REGEXP_CONTAINS(
        LOWER(COALESCE(latest_decision_rationale, '')),
        r'spend|limit|budget|cost'
      )
      AND max_period_spend_to_date < hard_stop_spend_threshold
      THEN 'FINANCIAL_EVIDENCE_MISMATCH'
    WHEN latest_decision IS NULL THEN 'NO_DECISION_AS_OF_DATE'
    ELSE 'SUPPORTED_OR_NONFINANCIAL'
  END AS decision_financial_evidence_status,
  CASE
    WHEN latest_decision = 'Stop'
      AND REGEXP_CONTAINS(
        LOWER(COALESCE(latest_decision_rationale, '')),
        r'spend|limit|budget|cost'
      )
      AND max_period_spend_to_date < hard_stop_spend_threshold
      THEN 'Decision rationale references financial limits, but no calculated hard-stop breach exists.'
    WHEN threshold_status = 'HARD_STOP'
      AND decision_status_as_of_date != 'stopped'
      THEN 'Calculated hard-stop threshold was reached without a stopped status.'
    WHEN period_measurement_quality_status = 'LIMITED'
      THEN 'Spend is a lower-bound estimate because telemetry coverage is limited.'
    ELSE NULL
  END AS governance_exception_reason,
  CASE
    WHEN (
      latest_decision = 'Stop'
      AND REGEXP_CONTAINS(
        LOWER(COALESCE(latest_decision_rationale, '')),
        r'spend|limit|budget|cost'
      )
      AND max_period_spend_to_date < hard_stop_spend_threshold
    )
    OR (
      threshold_status = 'HARD_STOP'
      AND decision_status_as_of_date != 'stopped'
    )
    OR period_measurement_quality_status = 'LIMITED'
      THEN 'EXCEPTION'
    ELSE 'PASS'
  END AS governance_exception_status,
  SAFE_DIVIDE(
    period_successful_request_count,
    period_logical_request_count
  ) AS observed_success_rate,
  SAFE_DIVIDE(
    period_retry_attempt_count,
    period_telemetry_attempt_count
  ) AS observed_retry_attempt_rate,
  SAFE_DIVIDE(
    period_invoice_billed_experiment_cost,
    period_successful_request_count
  ) AS invoice_cost_per_successful_request,
  'allocated_invoice_billed_cost_usage_lines_only'
    AS financial_basis,
  'request_telemetry_usage_cost_estimate'
    AS operational_basis
FROM resolved;
