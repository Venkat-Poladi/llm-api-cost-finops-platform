CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.llm_finops_mart.dim_ai_date`
AS
SELECT
  CAST(FORMAT_DATE('%Y%m%d', calendar_date) AS INT64) AS date_key,
  calendar_date AS date,
  EXTRACT(YEAR FROM calendar_date) AS year,
  EXTRACT(QUARTER FROM calendar_date) AS quarter_number,
  CONCAT('Q', CAST(EXTRACT(QUARTER FROM calendar_date) AS STRING))
    AS quarter_name,
  EXTRACT(MONTH FROM calendar_date) AS month_number,
  FORMAT_DATE('%B', calendar_date) AS month_name,
  FORMAT_DATE('%b', calendar_date) AS month_short_name,
  FORMAT_DATE('%Y-%m', calendar_date) AS year_month,
  EXTRACT(YEAR FROM calendar_date) * 100
    + EXTRACT(MONTH FROM calendar_date) AS year_month_sort,
  DATE_TRUNC(calendar_date, MONTH) AS month_start_date,
  LAST_DAY(calendar_date, MONTH) AS month_end_date,
  EXTRACT(DAY FROM calendar_date) AS day_of_month,
  FORMAT_DATE('%A', calendar_date) AS day_name,
  EXTRACT(DAYOFWEEK FROM calendar_date) AS day_of_week_number
FROM UNNEST(
  GENERATE_DATE_ARRAY(DATE '2025-01-01', DATE '2026-06-30')
) AS calendar_date;
