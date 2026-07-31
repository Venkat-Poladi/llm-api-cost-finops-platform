CREATE OR REPLACE TABLE
  `{{PROJECT_ID}}.{{CORE_DATASET}}.fct_ai_usage_daily`
PARTITION BY usage_date
CLUSTER BY provider, application_name, department_name, model_snapshot
AS
WITH usage_source AS (
  SELECT
    source_usage_key,
    usage_date,
    provider,
    usage_type,
    provider_project_id,
    api_key_id,
    model,
    model_snapshot,
    provider_service_tier,
    normalized_processing_tier,
    is_batch,
    context_window_tier,
    request_count,
    normalized_total_input_tokens,
    normalized_uncached_input_tokens,
    normalized_cache_read_tokens,
    normalized_cache_creation_5m_tokens,
    normalized_cache_creation_1h_tokens,
    output_tokens,
    reasoning_tokens,
    visible_output_tokens,
    usage_cost_estimate,
    rate_currency,
    is_synthetic
  FROM
    `{{PROJECT_ID}}.{{STAGING_DATASET}}.stg_ai_provider_usage_priced`
  WHERE pricing_status = 'Priced'
),
matched_mappings AS (
  SELECT
    u.source_usage_key,
    b.mapping_id,
    b.application_name,
    b.department_name,
    b.cost_center,
    b.allocation_percentage,
    b.mapping_status,
    b.allocation_method,
    b.allocation_confidence,
    b.effective_start_date,
    b.effective_end_date,
    b.mapping_recorded_date,
    b.mapping_recorded_date > b.effective_start_date
      AND u.usage_date < b.mapping_recorded_date
      AS is_historical_restatement
  FROM usage_source AS u
  JOIN `{{PROJECT_ID}}.{{RAW_DATASET}}.bridge_ai_usage_attribution` AS b
    ON u.provider = b.provider
    AND u.provider_project_id = b.provider_project_id
    AND u.api_key_id = b.api_key_id
    AND u.usage_date BETWEEN
      b.effective_start_date AND b.effective_end_date
),
mapping_totals AS (
  SELECT
    source_usage_key,
    COUNT(*) AS matched_mapping_count,
    SUM(allocation_percentage) AS mapped_allocation_percentage
  FROM matched_mappings
  GROUP BY source_usage_key
),
allocated_rows AS (
  SELECT
    u.*,
    m.mapping_id,
    m.application_name,
    m.department_name,
    m.cost_center,
    m.allocation_percentage,
    m.mapping_status,
    m.allocation_method,
    m.allocation_confidence,
    m.effective_start_date,
    m.effective_end_date,
    m.mapping_recorded_date,
    m.is_historical_restatement,
    'Allocated' AS allocation_status
  FROM usage_source AS u
  JOIN matched_mappings AS m
    USING (source_usage_key)
),
unallocated_rows AS (
  SELECT
    u.*,
    CAST(NULL AS STRING) AS mapping_id,
    'Unallocated' AS application_name,
    'Unallocated' AS department_name,
    'UNALLOCATED' AS cost_center,
    CAST(
      1 - COALESCE(t.mapped_allocation_percentage, 0)
      AS NUMERIC
    ) AS allocation_percentage,
    'unallocated' AS mapping_status,
    CASE
      WHEN t.source_usage_key IS NULL THEN 'no_mapping'
      ELSE 'unallocated_residual'
    END AS allocation_method,
    'none' AS allocation_confidence,
    CAST(NULL AS DATE) AS effective_start_date,
    CAST(NULL AS DATE) AS effective_end_date,
    CAST(NULL AS DATE) AS mapping_recorded_date,
    FALSE AS is_historical_restatement,
    'Unallocated' AS allocation_status
  FROM usage_source AS u
  LEFT JOIN mapping_totals AS t
    USING (source_usage_key)
  WHERE COALESCE(t.mapped_allocation_percentage, 0) < 1
),
combined AS (
  SELECT * FROM allocated_rows
  UNION ALL
  SELECT * FROM unallocated_rows
),
ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY source_usage_key
      ORDER BY
        CASE WHEN allocation_status = 'Allocated' THEN 0 ELSE 1 END,
        application_name,
        department_name,
        cost_center,
        COALESCE(mapping_id, '')
    ) AS source_measure_anchor_number,
    SUM(allocation_percentage) OVER (
      PARTITION BY source_usage_key
    ) AS total_distribution_percentage
  FROM combined
)
SELECT
  TO_HEX(
    SHA256(
      TO_JSON_STRING(
        STRUCT(
          source_usage_key,
          application_name,
          department_name,
          cost_center,
          allocation_status,
          COALESCE(mapping_id, 'UNALLOCATED')
        )
      )
    )
  ) AS usage_allocation_fact_id,
  source_usage_key,
  usage_date,
  provider,
  usage_type,
  provider_project_id,
  api_key_id,
  model,
  model_snapshot,
  provider_service_tier,
  normalized_processing_tier,
  is_batch,
  context_window_tier,
  application_name,
  department_name,
  cost_center,
  mapping_id,
  mapping_status,
  allocation_method,
  allocation_confidence,
  effective_start_date,
  effective_end_date,
  mapping_recorded_date,
  is_historical_restatement,
  allocation_status,
  allocation_percentage,
  total_distribution_percentage,
  source_measure_anchor_number = 1 AS source_measure_anchor_flag,

  IF(source_measure_anchor_number = 1, request_count, NULL)
    AS source_request_count,
  IF(source_measure_anchor_number = 1, normalized_total_input_tokens, NULL)
    AS source_total_input_tokens,
  IF(source_measure_anchor_number = 1, normalized_uncached_input_tokens, NULL)
    AS source_uncached_input_tokens,
  IF(source_measure_anchor_number = 1, normalized_cache_read_tokens, NULL)
    AS source_cache_read_tokens,
  IF(
    source_measure_anchor_number = 1,
    normalized_cache_creation_5m_tokens,
    NULL
  ) AS source_cache_creation_5m_tokens,
  IF(
    source_measure_anchor_number = 1,
    normalized_cache_creation_1h_tokens,
    NULL
  ) AS source_cache_creation_1h_tokens,
  IF(source_measure_anchor_number = 1, output_tokens, NULL)
    AS source_output_tokens,
  IF(source_measure_anchor_number = 1, reasoning_tokens, NULL)
    AS source_reasoning_tokens,
  IF(source_measure_anchor_number = 1, visible_output_tokens, NULL)
    AS source_visible_output_tokens,
  IF(source_measure_anchor_number = 1, usage_cost_estimate, NULL)
    AS source_usage_cost_estimate,

  IF(
    allocation_status = 'Allocated',
    request_count * allocation_percentage,
    0
  ) AS allocated_request_count,
  IF(
    allocation_status = 'Allocated',
    normalized_total_input_tokens * allocation_percentage,
    0
  ) AS allocated_total_input_tokens,
  IF(
    allocation_status = 'Allocated',
    normalized_uncached_input_tokens * allocation_percentage,
    0
  ) AS allocated_uncached_input_tokens,
  IF(
    allocation_status = 'Allocated',
    normalized_cache_read_tokens * allocation_percentage,
    0
  ) AS allocated_cache_read_tokens,
  IF(
    allocation_status = 'Allocated',
    normalized_cache_creation_5m_tokens * allocation_percentage,
    0
  ) AS allocated_cache_creation_5m_tokens,
  IF(
    allocation_status = 'Allocated',
    normalized_cache_creation_1h_tokens * allocation_percentage,
    0
  ) AS allocated_cache_creation_1h_tokens,
  IF(
    allocation_status = 'Allocated',
    output_tokens * allocation_percentage,
    0
  ) AS allocated_output_tokens,
  IF(
    allocation_status = 'Allocated',
    reasoning_tokens * allocation_percentage,
    0
  ) AS allocated_reasoning_tokens,
  IF(
    allocation_status = 'Allocated',
    visible_output_tokens * allocation_percentage,
    0
  ) AS allocated_visible_output_tokens,
  IF(
    allocation_status = 'Allocated',
    usage_cost_estimate * allocation_percentage,
    0
  ) AS allocated_usage_cost_estimate,

  IF(
    allocation_status = 'Unallocated',
    request_count * allocation_percentage,
    0
  ) AS unallocated_request_count,
  IF(
    allocation_status = 'Unallocated',
    normalized_total_input_tokens * allocation_percentage,
    0
  ) AS unallocated_total_input_tokens,
  IF(
    allocation_status = 'Unallocated',
    normalized_uncached_input_tokens * allocation_percentage,
    0
  ) AS unallocated_uncached_input_tokens,
  IF(
    allocation_status = 'Unallocated',
    normalized_cache_read_tokens * allocation_percentage,
    0
  ) AS unallocated_cache_read_tokens,
  IF(
    allocation_status = 'Unallocated',
    normalized_cache_creation_5m_tokens * allocation_percentage,
    0
  ) AS unallocated_cache_creation_5m_tokens,
  IF(
    allocation_status = 'Unallocated',
    normalized_cache_creation_1h_tokens * allocation_percentage,
    0
  ) AS unallocated_cache_creation_1h_tokens,
  IF(
    allocation_status = 'Unallocated',
    output_tokens * allocation_percentage,
    0
  ) AS unallocated_output_tokens,
  IF(
    allocation_status = 'Unallocated',
    reasoning_tokens * allocation_percentage,
    0
  ) AS unallocated_reasoning_tokens,
  IF(
    allocation_status = 'Unallocated',
    visible_output_tokens * allocation_percentage,
    0
  ) AS unallocated_visible_output_tokens,
  IF(
    allocation_status = 'Unallocated',
    usage_cost_estimate * allocation_percentage,
    0
  ) AS unallocated_usage_cost_estimate,

  rate_currency AS billing_currency,
  is_synthetic
FROM ranked;
