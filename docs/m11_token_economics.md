# M11 — Token Economics

## What this milestone does

M11 explains how tokens, caching, reasoning, batching, retries, and failures affect estimated LLM cost.

## Mart created

`llm_finops_mart.mart_ai_token_economics`

## Grain

One row per:

- billing month;
- provider;
- provider project;
- model;
- model snapshot;
- usage type.

## Financial basis

All token-efficiency metrics use:

`usage_cost_estimate`

Failed-attempt and retry costs are explicitly labeled as telemetry estimates. They are not presented as invoiced costs.

## Cache metric

```text
cache_read_share =
normalized cache-read tokens / normalized total input tokens
```

The result is null when total input is zero.

## Reasoning metric

```text
reasoning_overhead_pct =
reasoning tokens / output tokens
```

Reasoning tokens remain a subset of output tokens and are not charged twice.

## Batch metric

```text
batch_adoption_pct =
batch request count / total request count
```

The mart also estimates the opportunity from moving eligible nonbatch usage to the matching historical batch rate.

Because v1 does not assume that cache and Batch discounts stack, the batch comparison treats all input as batch input.

## Cache savings

The no-cache baseline prices all normalized input at the ordinary input rate.

```text
estimated cache savings =
no-cache baseline cost - actual estimated cost
```

Negative savings are floored at zero.

## Failure and retry waste

From request telemetry, the mart publishes:

- estimated retry cost;
- estimated failed-attempt cost;
- estimated mid-generation failure cost;
- retry cost share;
- failed-attempt cost share.

## One-command execution

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_m11.ps1
```

M11 is complete only when all 14 BigQuery controls, all Python tests, and Ruff pass.
