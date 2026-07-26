# M8 — Monthly Cost Reconciliation

## What this milestone does

M8 creates the monthly financial fact that compares three separate amounts:

1. `usage_cost_estimate`
2. `provider_reported_cost`
3. `invoice_billed_cost`

These amounts are not blended into one variance.

## Objects created

### `stg_ai_usage_cost_monthly`

Rolls daily historically priced usage up to:

- billing month;
- provider;
- provider project;
- model.

This table has one row for each monthly usage-cost group.

### `fct_ai_cost_reconciliation`

Keeps the provider cost-line grain:

- billing month;
- provider;
- provider project;
- nullable model;
- line-item type;
- provider line-item ID.

## Two reconciliations

### Usage to reported

Applicable only to usage lines:

```text
provider_reported_cost - usage_cost_estimate
```

### Reported to invoice

Applicable to every cost line:

```text
invoice_billed_cost - provider_reported_cost
```

## Tolerance

A reconciliation passes when either:

- absolute variance is no more than $1; or
- absolute relative variance is no more than 1%.

## Honest reason codes

The cost source was intentionally generated independently from daily usage.

When a usage exception is labeled `ROUTINE_ROUNDING` by the source but the
actual variance exceeds tolerance, M8 reports:

`INDEPENDENT_SOURCE_ESTIMATE_DIFFERENCE`

It does not falsely describe a large source difference as ordinary rounding.

## Non-usage lines

Credit, tax, commitment true-up, correction, and adjustment lines have:

- null `usage_cost_estimate`;
- null usage-to-reported variance;
- `NOT_APPLICABLE` usage reconciliation status.

They still participate in reported-to-invoice reconciliation.

## One-command execution

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_m8.ps1
```

M8 is complete only when all 12 BigQuery controls, all Python tests, and Ruff pass.
