CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.{{MART_DATASET}}.dim_ai_application`
AS
WITH applications AS (
  SELECT DISTINCT
    COALESCE(application_name, 'Unallocated') AS application_name,
    COALESCE(department_name, 'Unallocated') AS department_name,
    COALESCE(cost_center, 'UNALLOCATED') AS cost_center
  FROM `{{PROJECT_ID}}.{{MART_DATASET}}.mart_ai_application_cost`
)
SELECT
  TO_HEX(
    SHA256(
      TO_JSON_STRING(
        STRUCT(application_name, department_name, cost_center)
      )
    )
  ) AS application_key,
  application_name,
  department_name,
  cost_center,
  application_name = 'Unallocated' AS is_unallocated
FROM applications;
