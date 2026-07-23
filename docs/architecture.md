# Architecture

## Design principle

Production realism is simulated through independent sources, source disagreement, attribution uncertainty, incomplete telemetry, and explicit financial reconciliation.

## Core objects

### Source and control objects

- `raw_ai_provider_usage`
- `raw_ai_provider_cost`
- `fct_ai_request_telemetry`
- `bridge_ai_usage_attribution`
- `dim_ai_model_rate`
- `dim_ai_model_map`
- `dim_ai_experiment_control`
- `fct_ai_experiment_decision`

### Derived facts

- `fct_ai_usage_daily`
- `fct_ai_cost_reconciliation`

### Marts

- `mart_ai_token_economics`
- `mart_ai_application_cost`
- `mart_ai_optimization`
- `mart_ai_unit_economics`
- `mart_ai_experiments`

## Grain rule

Monthly invoice cost is never joined directly to daily usage rows. Daily financial allocation must use a documented driver, retain source and allocated values, and preserve an unallocated residual.
