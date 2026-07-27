# M10 — Telemetry Reconciliation

## What this milestone does

M10 proves that request telemetry and provider usage describe the same underlying consumption, while preserving their expected differences.

## Matching grain

The reconciliation compares both sources by:

- usage date;
- provider;
- provider project;
- model.

## Fact created

`llm_finops_core.fct_ai_telemetry_reconciliation_daily`

## Monthly summary created

`llm_finops_mart.mart_ai_telemetry_coverage_monthly`

## What is compared

### Provider usage

- provider request count;
- normalized input tokens;
- output tokens;
- total tokens;
- historical usage-cost estimate.

### Request telemetry

- provider attempts;
- logical requests;
- successful logical requests;
- retries;
- failed attempts;
- normalized input and output tokens;
- attempt-level estimated cost.

## Request-count comparison

Provider usage reports provider calls, so the comparable telemetry measure is:

`telemetry_attempt_count`

Logical-request count remains separate because retries can create several provider attempts for one business request.

## Token coverage

```text
telemetry_token_coverage_pct =
telemetry_total_tokens / provider_total_tokens
```

The calculation uses safe division. A zero provider-token denominator returns null, not zero.

## Untraceable provider-usage cost

When telemetry covers less than provider usage, M10 estimates the untraceable share:

```text
provider usage cost × uncovered token share
```

The value is bounded between zero and provider usage cost.

## Coverage status

- `WITHIN_TOLERANCE`
- `PARTIAL_COVERAGE`
- `OVER_COVERAGE`
- `REQUEST_MISMATCH`
- `NO_TELEMETRY`
- `NO_PROVIDER_USAGE`

Every exception receives a reason code.

## One-command execution

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_m10.ps1
```

M10 is complete only when all 14 BigQuery controls, all Python tests, and Ruff pass.
