# M14 — Unit Economics

## What this milestone does

M14 converts monthly LLM spend, provider usage, and request telemetry into governed cost-per-unit metrics.

## Mart created

`llm_finops_mart.mart_ai_unit_economics`

## Grain

One row per:

- billing month;
- provider;
- provider project;
- model;
- model snapshot;
- usage type.

## Financial basis

The primary unit-cost numerator is:

`invoice_billed_cost` from usage lines only.

Taxes, credits, corrections, adjustments, and commitment true-ups are excluded because they do not represent direct request consumption.

The mart also retains `usage_cost_estimate` for operational comparisons.

## Provider-based metrics

These use the complete provider usage source and remain publishable even when telemetry is incomplete:

- invoice cost per provider request;
- invoice cost per thousand provider requests;
- invoice cost per million total tokens;
- invoice cost per million input tokens;
- invoice cost per million output tokens;
- average tokens per provider request.

## Telemetry-dependent metrics

These depend on request telemetry:

- invoice cost per logical request;
- invoice cost per successful request;
- observed success rate;
- observed retry rate;
- observed failed-attempt rate;
- attempts per logical request;
- retry cost per successful request.

## Measurement-quality gate

Telemetry-dependent financial metrics are published only when monthly token coverage is between 95% and 105%.

When coverage falls outside that range:

```text
measurement_quality_status = INSUFFICIENT
unit_economics_status = LIMITED_TELEMETRY
```

The governed logical-request and successful-request cost metrics return null.

This prevents incomplete telemetry from being presented as precise unit economics.

## Cost labels

Retry and failed-attempt costs remain labeled:

`Estimated from request telemetry`

They are not presented as invoiced waste.

## One-command execution

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_m14.ps1
```

M14 is complete only when all 16 BigQuery controls, all Python tests, and Ruff pass.
