# V1 Reconciliation Evidence

## Financial design

V1 deliberately preserves three different amounts:

1. **Usage cost estimate** — calculated in BigQuery from normalized tokens and historically effective rates.
2. **Provider-reported cost** — the provider financial record.
3. **Invoice-billed cost** — the final billed amount.

They are not silently blended.

```text
Usage-to-Reported Variance
= Provider-Reported Usage Cost - Usage Cost Estimate
```

```text
Reported-to-Invoice Variance
= Invoice-Billed Cost - Provider-Reported Cost
```

Only usage lines receive a token-derived estimate. Taxes, credits, corrections, true-ups, and adjustments remain visible as non-usage financial lines.

## Frozen source totals

| Financial evidence | Exact value |
|---|---:|
| Provider cost lines | 135 |
| Usage lines | 130 |
| Non-usage lines | 5 |
| Provider-reported cost | $20,243.727255 |
| Invoice-billed cost | $20,340.146796 |
| Reported-to-invoice difference | $96.419541 |

The raw provider-usage source intentionally contains no cost field. Therefore, the governed usage estimate is created only after model mapping, service-tier normalization, historical rate matching, and pricing in `stg_ai_provider_usage_priced`.

## Reconciliation path

```text
raw_ai_provider_usage
→ stg_ai_provider_usage_normalized
→ stg_ai_provider_usage_priced
→ stg_ai_usage_cost_monthly
→ fct_ai_cost_reconciliation
→ fact_ai_financial_monthly
→ Power BI canonical measures
```

Provider financial path:

```text
raw_ai_provider_cost
→ stg_ai_provider_cost
→ fct_ai_cost_reconciliation
→ fact_ai_financial_monthly
```

## Control evidence

The v1 control catalog contains 18 critical end-to-end controls. The reconciliation-critical controls include:

| Control | Purpose |
|---|---|
| E2E-07 | Every usage row resolves one valid historical model, tier, and rate. |
| E2E-08 | The complete token-derived usage estimate reaches monthly reconciliation. |
| E2E-09 | Provider-reported cost reconciles to the source. |
| E2E-10 | Invoice-billed cost reconciles to the source. |
| E2E-11 | Allocated plus unallocated daily usage equals source usage. |
| E2E-13 | Token-economics cost and token totals reconcile to priced usage. |
| E2E-14 | Allocated plus unallocated application invoice cost equals source invoice cost. |
| E2E-16 | Invoice usage cost reconciles and weak telemetry suppresses governed request-cost metrics. |

The previously completed M16 milestone recorded 18 of 18 controls passing. Public clean-clone CI validates code, SQL contracts, artifacts, linting, and tests; it does not execute authenticated BigQuery jobs because cloud credentials are intentionally absent from public CI.

## Power BI evidence

The four committed screenshots and PBIP artifacts are hashed in `evidence/releases/v1.0.0/powerbi_artifact_hashes.sha256`. The semantic model preserves separate measures for estimated, provider-reported, and invoice-billed cost, and the reconciliation waterfall ends at total invoice cost.

## M20 validation

The frozen repository state recorded:

- Source generation passed.
- 189 tests passed.
- Repository checks and Ruff passed.
- Local `main` and `origin/main` were synchronized.
- The working tree was clean.
