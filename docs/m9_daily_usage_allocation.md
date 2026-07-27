# M9 — Daily Usage Allocation

## What this milestone does

M9 converts daily priced usage into business-owned usage without duplicating shared keys.

## Fact created

`llm_finops_core.fct_ai_usage_daily`

Its grain is daily provider usage plus:

- application;
- department;
- cost center;
- allocation status.

## Shared-key example

The shared OpenAI key is distributed:

- 60% to Campaign Assistant;
- 30% to Growth Experiment Assistant;
- 10% to Unallocated.

A $100 source row becomes:

```text
Campaign Assistant              $60
Growth Experiment Assistant     $30
Unallocated                     $10
```

It never becomes $100 on each application.

## Source-measure anchor

A shared source row produces several allocation rows.

To prevent source totals from repeating, source measures are populated on exactly one deterministic row per `source_usage_key`.

The fact includes:

- `source_measure_anchor_flag`;
- source measures;
- allocated measures;
- unallocated measures.

This makes both checks possible:

```text
SUM(source cost) = original priced usage cost
```

and:

```text
allocated cost + unallocated cost = source cost
```

## Imperfect attribution handled

### Partial allocation

Any percentage below 100% creates an explicit residual row.

### Missing mapping

A key with no matching attribution row becomes 100% Unallocated.

### Ownership change

The Developer Assistant maps to:

- Engineering / CC400 before January 2026;
- Platform Engineering / CC410 from January 2026.

### Late mapping

Usage for `an-key-lab` before its February 2026 recording date is allocated in the current restated view and flagged with:

`is_historical_restatement = true`

## Financial basis

This milestone allocates `usage_cost_estimate`.

Invoice-basis application chargeback is built later after telemetry and financial allocation controls are complete.

## One-command execution

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_m9.ps1
```

M9 is complete only when all 16 BigQuery controls, all Python tests, and Ruff pass.
