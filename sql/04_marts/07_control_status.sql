CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.llm_finops_mart.mart_ai_control_status`
CLUSTER BY status, severity, control_domain
AS
WITH latest AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY control_id
      ORDER BY checked_at DESC, pipeline_run_id DESC
    ) AS latest_row_number
  FROM
    `{{PROJECT_ID}}.llm_finops_control.m16_end_to_end_control_result`
)
SELECT
  c.control_id,
  c.control_name,
  c.control_domain,
  c.severity,
  c.data_layer,
  c.description,
  l.pipeline_run_id,
  l.violation_count,
  l.status,
  l.checked_at,
  IF(l.status = 'PASS', 1, 0) AS pass_flag,
  IF(l.status = 'FAIL', 1, 0) AS fail_flag
FROM `{{PROJECT_ID}}.llm_finops_control.dim_ai_control_catalog` AS c
LEFT JOIN latest AS l
  ON c.control_id = l.control_id
  AND l.latest_row_number = 1;
