# Source-to-Target Mapping

| Source object | Staging work | Final target | Main purpose |
|---|---|---|---|
| `raw_ai_provider_usage` | Normalize tokens, resolve model snapshot and rate, calculate estimated cost | `fct_ai_usage_daily`, `fct_ai_cost_reconciliation` | Usage trends and estimated cost |
| `raw_ai_provider_cost` | Classify scope and line type | `fct_ai_cost_reconciliation` | Financial reconciliation |
| `fct_ai_request_telemetry` | Validate attempts, retries, failures, and coverage | Unit economics and experiment marts | Request economics |
| `bridge_ai_usage_attribution` | Resolve effective allocation window | Daily usage and application-cost mart | Chargeback and unallocated reporting |
| `dim_ai_model_map` | Resolve model snapshot | Staged usage | Historical model mapping |
| `dim_ai_model_rate` | Resolve historical price | Staged usage | Estimated usage cost |
| `dim_ai_experiment_control` | Validate limits and dates | Experiment mart | Spend governance |
| `fct_ai_experiment_decision` | Validate status history | Experiment mart | Auditable decisions |

## Fact separation

`fct_ai_usage_daily` is daily and operational.

`fct_ai_cost_reconciliation` is monthly and financial.

Monthly invoice rows must never be expanded through a direct join to daily usage rows.
