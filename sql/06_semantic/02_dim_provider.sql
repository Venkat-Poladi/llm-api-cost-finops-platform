CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.llm_finops_mart.dim_ai_provider`
AS
SELECT DISTINCT
  TO_HEX(SHA256(provider)) AS provider_key,
  provider,
  CASE
    WHEN provider = 'openai' THEN 'OpenAI'
    WHEN provider = 'anthropic' THEN 'Anthropic'
    ELSE provider
  END AS provider_display_name
FROM (
  SELECT provider
  FROM `{{PROJECT_ID}}.llm_finops_mart.mart_ai_token_economics`
  UNION DISTINCT
  SELECT provider
  FROM `{{PROJECT_ID}}.llm_finops_mart.mart_ai_application_cost`
);
