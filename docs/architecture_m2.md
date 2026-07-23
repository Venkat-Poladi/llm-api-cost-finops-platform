# M2 Architecture and Data Contracts

## Purpose

This milestone converts the locked project scope into executable table contracts before any synthetic data is generated.

## Layered architecture

```text
Synthetic source generation
        |
        v
Raw layer
- raw_ai_provider_usage
- raw_ai_provider_cost
- fct_ai_request_telemetry
- bridge_ai_usage_attribution
- dim_ai_model_map
- dim_ai_model_rate
- dim_ai_experiment_control
- fct_ai_experiment_decision
        |
        v
Staging layer
- provider-specific token normalization
- model snapshot resolution
- historical rate resolution
- usage cost estimate
- allocation-window resolution
        |
        +------------------------------+
        |                              |
        v                              v
Daily usage fact                 Monthly reconciliation fact
fct_ai_usage_daily               fct_ai_cost_reconciliation
        |                              |
        +---------------+--------------+
                        |
                        v
Analytics marts
- mart_ai_token_economics
- mart_ai_application_cost
- mart_ai_optimization
- mart_ai_unit_economics
- mart_ai_experiments
                        |
                        v
Power BI semantic model and report
```

## Non-negotiable grain rule

Monthly invoice rows must never be joined directly to daily usage rows because that would repeat one monthly amount across many daily rows.

When a monthly invoiced amount must be shown daily, it must be allocated using a documented driver such as each day's share of estimated usage cost.

## Financial bases

- `usage_cost_estimate`: operational estimate derived from tokens and the historical rate card.
- `provider_reported_cost`: amount reported by the provider cost source.
- `invoice_billed_cost`: invoiced financial amount.

Every metric and visual must explicitly state which cost basis it uses.

## Currency rule

Version 1 is USD only.

Any non-USD cost or spending-limit record is a data-quality failure.

## Effective-dated lookup rule

A usage row must resolve to exactly one model map and exactly one historical rate row for its usage date.

Overlapping effective windows are not allowed.
