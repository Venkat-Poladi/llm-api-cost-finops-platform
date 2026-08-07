# V1 Metric Baseline

## Purpose

This file freezes the governed v1 metric set before Phase 2 changes provider coverage, cost totals, usage volumes, tables, or report measures.

## Release identity

| Field | Frozen value |
|---|---|
| Release | `v1.0.0` |
| Implementation baseline commit | `c2a2449c5e8dbba0237dd9abd8be3b747a247e26` |
| Generator version | `1.0.0` |
| Master seed | `42` |
| Reporting period | 2025-01-01 through 2026-06-30 |
| Provider channels | OpenAI direct and Anthropic direct |
| Reporting currency | USD |

## Deterministic source evidence

These exact values come from `evidence/releases/v1.0.0/generation_manifest.json`.

| Measure | Exact frozen value |
|---|---:|
| Provider usage rows | 4,431 |
| OpenAI usage rows | 2,786 |
| Anthropic usage rows | 1,645 |
| Provider cost rows | 135 |
| Usage financial lines | 130 |
| Non-usage financial lines | 5 |
| Provider-reported cost | $20,243.727255 |
| Invoice-billed cost | $20,340.146796 |
| Reported-to-invoice difference | $96.419541 |
| Request telemetry attempts | 369,921 |
| Logical requests | 347,775 |
| Retry attempts | 22,146 |
| Successful logical requests | 339,178 |
| Failed logical requests | 8,597 |
| Telemetry-side usage-cost estimate | $22,318.045998 |
| Attribution rows | 13 |
| Experiment-control rows | 4 |
| Experiment-decision rows | 9 |

The telemetry-side cost estimate is an operational source metric. It must not be substituted for the separately governed provider-usage estimate used in warehouse reconciliation.

## Published v1 portfolio metrics

These are the rounded values published in the committed README and Power BI evidence.

| Published measure | Frozen display value | Basis |
|---|---:|---|
| Invoice-billed LLM cost | $20,340.15 | Final invoice-billed total |
| Provider-reported cost | $20,243.73 | Provider financial reporting |
| Logical requests | 347,775 | Distinct logical requests |
| Request telemetry records | 369,921 | Provider attempts captured by telemetry |
| Retry attempts | 22,146 | Attempts beyond the initial attempt |
| Allocation coverage | Approximately 99.95% | Invoice-aligned usage allocation coverage |
| Modeled annualized optimization opportunity | Approximately $9.29K | Latest optimization snapshot only |

The allocation and optimization values are governed warehouse/report outputs rather than fields in the source-generation manifest. Their v1 display values are preserved by the committed PBIP and screenshots.

## Change rule

V1 metrics are immutable release evidence. Phase 2 may produce different values, but it must not overwrite this file. Every published metric change must be recorded in `docs/metric_change_log.md` and updated across SQL, tests, README, screenshots, release notes, and reporting artifacts in the same pull request.

## Claim boundary

The optimization amount is an identified and modeled opportunity. It is not actual company savings and is not presented as approved, implemented, verified, or realized business value.
