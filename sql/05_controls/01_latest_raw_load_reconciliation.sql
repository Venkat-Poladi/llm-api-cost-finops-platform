-- M6 manual inspection query
SELECT
  table_name,
  source_row_count,
  bigquery_row_count,
  row_count_difference,
  status,
  checked_at
FROM `finops-learning-lab.llm_finops_control.raw_load_reconciliation`
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY table_name
  ORDER BY checked_at DESC
) = 1
ORDER BY table_name;
