# Data Contracts

## Contract rules

Each table has one declared grain, and the listed business-key columns together identify one row at that grain.

## `raw_ai_provider_usage`

**Grain:** One row per `usage_date`, `provider`, `provider_project_id`, `api_key_id`, `model`, `provider_service_tier`, `is_batch`, and `context_window_tier`.

**Purpose:** Store provider-native aggregated request and token usage.

**Rules**
- Do not store cost in raw usage.
- `reasoning_tokens <= output_tokens`.
- OpenAI `cached_input_tokens <= input_tokens`.
- Do not store currency because the table has no financial amount.

## `raw_ai_provider_cost`

**Grain:** One row per `billing_period`, `provider`, `provider_project_id`, nullable `model`, `line_item_type`, and `provider_line_item_id`.

**Purpose:** Store provider-reported and invoiced cost lines.

**Rules**
- `model` may be null for project-level and invoice-level lines.
- `provider_line_item_id` is required for uniqueness.
- `billing_currency = 'USD'`.
- Non-usage lines do not receive a token-derived usage estimate.

## `fct_ai_request_telemetry`

**Grain:** One row per provider request attempt, identified by `provider_request_id`.

**Purpose:** Store retries, failures, tokens, and estimated attempt cost.

**Rules**
- One logical request may create several attempt rows.
- Attempt metrics and logical-request metrics must remain separate.
- Retry cost uses non-final attempts.
- Successful-request metrics use the final logical-request outcome.

## `bridge_ai_usage_attribution`

**Grain:** One row per `provider`, `provider_project_id`, `api_key_id`, allocation target, and effective window.

**Purpose:** Map provider usage to application, department, and cost center.

**Rules**
- Shared keys may have multiple allocation rows.
- Allocation percentages must total no more than 100% for a key and window.
- Unmapped or partially mapped usage remains unallocated.
- Ownership changes use separate effective windows.

## `dim_ai_model_map`

**Grain:** One row per `provider`, `provider_model_name`, `model_snapshot`, and effective window.

**Purpose:** Resolve provider model names to stable historical model snapshots.

**Rules**
- Effective windows may not overlap for the same provider model.
- Every usage row must resolve to exactly one model snapshot.

## `dim_ai_model_rate`

**Grain:** One row per `provider`, `model_snapshot`, `normalized_processing_tier`, `is_batch`, `context_window_tier`, and effective window.

**Purpose:** Store historical model rates in wide format.

**Rules**
- `billable_unit` is not part of the grain.
- Batch and context-window pricing are grain dimensions, not duplicate rate columns.
- Effective windows may not overlap for the same complete rate key.

## `dim_ai_experiment_control`

**Grain:** One row per `experiment_id`.

**Purpose:** Store experiment ownership, dates, limits, thresholds, and current status.

**Rules**
- `spending_limit_period` is `day`, `month`, or `lifetime`.
- Warning and hard-stop thresholds are percentages.
- `limit_currency = 'USD'`.

## `fct_ai_experiment_decision`

**Grain:** One row per `experiment_decision_id`.

**Purpose:** Preserve append-only experiment decision history.

**Rules**
- Decisions must be chronological.
- Each event's `previous_status` must match the prior event's `new_status`.
- The latest event determines current status.

## `fct_ai_usage_daily`

**Grain:** One row per daily source dimensions plus attributed application, department, and cost center.

**Purpose:** Store daily source and allocated requests, tokens, and estimated cost.

**Rules**
- Source and allocated measures remain separate.
- Shared keys split usage instead of duplicating it.
- `allocated_cost + unallocated_cost = source_cost`.
- Ratio metrics return null when the denominator is zero.

## `fct_ai_cost_reconciliation`

**Grain:** One row per `billing_month`, `provider`, `provider_project_id`, nullable `model`, `line_item_type`, and `provider_line_item_id`.

**Purpose:** Reconcile monthly estimated, provider-reported, and invoiced amounts.

**Rules**
- Usage lines may carry `usage_cost_estimate`.
- Non-usage lines carry null `usage_cost_estimate`.
- Usage-to-reported and reported-to-invoice variances remain separate.
- Every exception requires a variance reason code.
- Monthly invoice rows are never directly joined to daily usage rows.

## Analytics marts

- `mart_ai_token_economics`
- `mart_ai_application_cost`
- `mart_ai_optimization`
- `mart_ai_unit_economics`
- `mart_ai_experiments`
