# Metric Change Log

## Purpose

This log prevents published values from changing silently as Phase 2 adds providers, infrastructure, budgets, forecasts, and new allocation rules.

## Required fields

Every change to published cost, requests, tokens, allocation coverage, budget, forecast, savings, quality, latency, or dashboard measures must record:

- Change date
- Milestone and pull request or commit
- Dataset release ID
- Metric name
- Previous value
- New value
- Reason
- Affected source, table, SQL, or DAX
- Reconciliation/control result
- README, screenshot, release-note, and artifact updates

## Entries

| Date | Milestone | Dataset release | Metric set | Previous | New | Reason | Evidence |
|---|---|---|---|---|---|---|---|
| 2026-08-06 | M20 | v1 baseline | V1 governed portfolio metrics | Not previously frozen | See `docs/releases/v1_metric_baseline.md` | Establish immutable v1 comparison point before Phase 2 | `evidence/releases/v1.0.0/` |

## Phase 2 entry template

```text
Date:
Milestone:
Commit or pull request:
Dataset release ID:
Generator version and seed:
Metric:
Previous value:
New value:
Reason:
Affected code/tables/measures:
Control result:
README updated: Yes/No
Screenshots updated: Yes/No
Release notes updated: Yes/No
Known limitations updated: Yes/No
```

V1 values must never be overwritten. Phase 2 metrics belong to a new dataset release and must be compared against, not substituted into, the v1 baseline.
