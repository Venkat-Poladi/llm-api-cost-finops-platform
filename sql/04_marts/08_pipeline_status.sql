CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.llm_finops_mart.mart_ai_pipeline_status`
CLUSTER BY status, pipeline_name
AS
WITH expected AS (
  SELECT pipeline_name
  FROM UNNEST([
    'M6_BIGQUERY_RAW_LAYER',
    'M7_STAGING_NORMALIZATION_PRICING',
    'M8_MONTHLY_COST_RECONCILIATION',
    'M9_DAILY_USAGE_ALLOCATION',
    'M10_TELEMETRY_RECONCILIATION',
    'M11_TOKEN_ECONOMICS',
    'M12_APPLICATION_COST_CHARGEBACK',
    'M13_OPTIMIZATION_EVALUATION_GATE',
    'M14_UNIT_ECONOMICS',
    'M15_EXPERIMENT_GOVERNANCE'
  ]) AS pipeline_name
),
latest AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY pipeline_name
      ORDER BY completed_at DESC, pipeline_run_id DESC
    ) AS latest_row_number
  FROM `{{PROJECT_ID}}.llm_finops_control.pipeline_run_log`
)
SELECT
  e.pipeline_name,
  l.pipeline_run_id,
  l.started_at,
  l.completed_at,
  COALESCE(l.status, 'MISSING') AS status,
  l.loaded_table_count,
  l.error_message,
  IF(l.status = 'PASS', 1, 0) AS pass_flag,
  IF(l.status IS NULL OR l.status != 'PASS', 1, 0) AS attention_flag
FROM expected AS e
LEFT JOIN latest AS l
  ON e.pipeline_name = l.pipeline_name
  AND l.latest_row_number = 1;
