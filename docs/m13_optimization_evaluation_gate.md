# M13 — Optimization and Evaluation Gate

## What this milestone does

M13 converts cost signals into controlled recommendations without pretending that modeled savings have already been achieved.

## Mart created

`llm_finops_mart.mart_ai_optimization`

## Recommendation types

### Batch migration

Uses the historical batch-rate opportunity calculated in M11.

This is a rate-based estimate.

### Retry reduction

Uses request telemetry and models a 50% reduction in retry cost.

This is an assumption-based estimate and requires sufficient telemetry coverage.

### Telemetry coverage

Surfaces estimated provider-usage cost that cannot be traced to complete request telemetry.

This is cost at risk, not savings.

### Cache reuse assessment

Flags low cache-read usage for controlled benchmarking.

No savings amount is assigned because future cache-hit improvement, cache-write overhead, latency, and quality are not yet measured.

## Evaluation gates

- `READY_FOR_EVALUATION`
- `HOLD_FOR_DATA`
- `REQUIRES_BENCHMARK`

A recommendation can be ready for evaluation without being approved or implemented.

## Savings hierarchy

### Identified

A modeled opportunity from a documented rate or assumption.

### Approved

Authorized by the accountable owner.

### Implemented

The change has been deployed.

### Realized

Measured against an approved baseline after implementation.

M13 populates only the identified stage.

The following remain zero:

- approved savings;
- implemented savings;
- realized savings.

## Interview wording

Permitted:

> The project identified modeled annualized savings opportunities using historical rate comparisons and request-telemetry assumptions.

Not permitted:

> I realized these savings for a real company.

## Financial basis

Optimization estimates use:

`usage_cost_estimate`

They are not presented as invoice-billed savings.

## One-command execution

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_m13.ps1
```

M13 is complete only when all 16 BigQuery controls, all Python tests, and Ruff pass.
