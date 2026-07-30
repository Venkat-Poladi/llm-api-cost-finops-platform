# M15 — Experiment Governance

## What this milestone does

M15 measures experiment spending against daily, monthly, or lifetime limits and audits the decision history against the calculated financial evidence.

## Objects created

### `stg_ai_experiment_invoice_driver_daily`

Uses request telemetry to identify experiment activity, then allocates only usage-line invoice cost to experiments.

The driver is:

```text
daily experiment telemetry estimated cost
/
monthly provider usage estimated cost
```

The resulting experiment spend uses:

`allocated invoice_billed_cost from usage lines only`

Tax, credits, corrections, adjustments, and commitment true-ups are excluded.

### `mart_ai_experiments`

Evaluates each experiment according to its configured limit period:

- `day`: one row per experiment day;
- `month`: one row per experiment month;
- `lifetime`: one cumulative row per experiment day.

## Thresholds

```text
warning threshold amount =
spending limit × warning threshold percentage
```

```text
hard-stop threshold amount =
spending limit × hard-stop threshold percentage
```

Statuses:

- `WITHIN_LIMIT`
- `WARNING`
- `HARD_STOP`

## Measurement quality

When telemetry token coverage is between 95% and 105%:

```text
spend quality = BEST_ESTIMATE
```

Otherwise:

```text
spend quality = LOWER_BOUND
```

The spend remains visible, but the limitation is explicit.

## Decision audit

The mart resolves the latest decision as of every evaluation date.

It checks:

- whether a hard-stop breach has a stopped status;
- whether a decision rationale claiming a spending-limit breach is supported by the calculated financial data;
- whether the final decision status matches the experiment control table.

A financial claim without a calculated breach is labeled:

`FINANCIAL_EVIDENCE_MISMATCH`

It is surfaced as a governance exception instead of being silently accepted.

## Zero-spend periods

The mart generates the complete experiment calendar, so days and months with no activity remain visible with zero spend.

This prevents missing rows from being mistaken for missing controls.

## One-command execution

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_m15.ps1
```

M15 is complete only when all 18 BigQuery controls, all Python tests, and Ruff pass.
