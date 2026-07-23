# Naming Conventions

## BigQuery datasets

- `llm_finops_raw`
- `llm_finops_staging`
- `llm_finops_core`
- `llm_finops_mart`
- `llm_finops_control`

## Table prefixes

- `raw_`: source-native data
- `stg_`: normalized staging data
- `dim_`: dimensions
- `bridge_`: allocation mappings
- `fct_`: facts and event facts
- `mart_`: decision-focused analytics outputs
- `ctl_`: automated controls
- `vw_`: views

## Column suffixes

- `_id`: identifier
- `_date`: date
- `_month`: reporting month
- `_timestamp`: timestamp
- `_count`: count
- `_tokens`: token quantity
- `_cost`: USD cost
- `_rate`: price rate
- `_percentage`: stored decimal allocation such as 0.60
- `_pct`: calculated reporting ratio
- `_flag`: boolean
- `_status`: controlled status
- `_reason_code`: controlled explanation

## General rules

- Use lowercase snake_case.
- Store timestamps in UTC.
- Store v1 financial values in USD.
- Avoid vague names such as `value`, `amount`, `type`, or `date`.
