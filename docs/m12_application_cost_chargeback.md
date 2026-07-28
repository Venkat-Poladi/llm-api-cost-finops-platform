# M12 — Application Cost and Chargeback

## What this milestone does

M12 converts monthly invoiced LLM cost into business-owned application cost while preserving financial uncertainty.

## Objects created

### `stg_ai_application_invoice_driver_monthly`

Aggregates M9 daily allocations before any financial join.

This is the protection against joining monthly invoice rows directly to daily usage rows.

### `mart_ai_application_cost`

Publishes invoice-basis cost by:

- month;
- provider;
- provider project;
- model;
- line-item type;
- application;
- department;
- cost center;
- allocation status and confidence.

## Usage-line allocation

Usage invoice cost is allocated inside its own source scope:

```text
billing month + provider + provider project + model
```

The driver is:

```text
application usage-cost estimate / total eligible usage-cost estimate
```

The same share allocates provider-reported and invoice-billed usage cost.

## Zero-denominator rule

When no eligible usage estimate exists:

```text
allocated cost = 0
unallocated cost = source cost
allocation status = Unallocated
allocation method = no_eligible_driver
```

## Non-usage lines

These lines are not assigned to applications:

- credits;
- tax;
- commitment true-ups;
- corrections;
- adjustments.

They remain in the explicit `Unallocated` bucket with:

```text
allocation status = Financial scope retained
allocation method = scope_retained
```

This is more honest than silently spreading tax or account-level credits across applications.

## Source-measure anchor

Each monthly financial source scope has exactly one anchor row containing source totals.

This prevents source invoice amounts from being repeated across application rows.

## Financial basis

The chargeback basis is:

`invoice_billed_cost`

Token economics remain on `usage_cost_estimate`.

## One-command execution

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_m12.ps1
```

M12 is complete only when all 16 BigQuery controls, all Python tests, and Ruff pass.
