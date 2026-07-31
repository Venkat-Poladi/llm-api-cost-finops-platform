CREATE OR REPLACE TABLE `{{PROJECT_ID}}.{{STAGING_DATASET}}.dim_ai_service_tier_map` AS
SELECT *
FROM UNNEST([
  STRUCT(
    'openai' AS provider,
    'default' AS provider_service_tier,
    FALSE AS is_batch,
    'standard' AS normalized_processing_tier
  ),
  STRUCT(
    'openai' AS provider,
    'default' AS provider_service_tier,
    TRUE AS is_batch,
    'standard' AS normalized_processing_tier
  ),
  STRUCT(
    'anthropic' AS provider,
    'standard' AS provider_service_tier,
    FALSE AS is_batch,
    'standard' AS normalized_processing_tier
  ),
  STRUCT(
    'anthropic' AS provider,
    'batch' AS provider_service_tier,
    TRUE AS is_batch,
    'standard' AS normalized_processing_tier
  )
]);
