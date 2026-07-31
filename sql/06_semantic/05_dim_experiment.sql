CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.{{MART_DATASET}}.dim_ai_experiment`
AS
SELECT
  experiment_id AS experiment_key,
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
  current_status,
  override_reason
FROM `{{PROJECT_ID}}.{{RAW_DATASET}}.dim_ai_experiment_control`;
