CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.{{MART_DATASET}}.dim_ai_model`
AS
WITH models AS (
  SELECT DISTINCT
    provider,
    COALESCE(model, 'Not applicable') AS model,
    COALESCE(model_snapshot, 'Not applicable') AS model_snapshot,
    COALESCE(usage_type, 'Not applicable') AS usage_type
  FROM `{{PROJECT_ID}}.{{MART_DATASET}}.mart_ai_token_economics`

  UNION DISTINCT

  SELECT DISTINCT
    provider,
    COALESCE(model, 'Not applicable') AS model,
    COALESCE(model_snapshot, 'Not applicable') AS model_snapshot,
    COALESCE(usage_type, 'Not applicable') AS usage_type
  FROM `{{PROJECT_ID}}.{{MART_DATASET}}.mart_ai_application_cost`
)
SELECT
  TO_HEX(
    SHA256(
      TO_JSON_STRING(
        STRUCT(provider, model, model_snapshot, usage_type)
      )
    )
  ) AS model_key,
  provider,
  model,
  model_snapshot,
  usage_type,
  CONCAT(provider, ' | ', model) AS provider_model_label
FROM models;
