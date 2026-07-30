# M16 — Automated Controls and CI

## What this milestone does

M16 creates a single completion gate for the entire platform.

It does not replace the detailed milestone controls. It adds 18 end-to-end controls that prove the major layers still reconcile after the complete build.

## Control catalog

`llm_finops_control.dim_ai_control_catalog`

The catalog contains exactly 18 controls with:

- control ID;
- name;
- domain;
- severity;
- data layer;
- description.

## Control results

`llm_finops_control.m16_end_to_end_control_result`

Every M16 run writes one result per control.

## Reporting marts

### `mart_ai_control_status`

Shows the latest result for each of the 18 controls.

### `mart_ai_pipeline_status`

Shows the latest status for M6 through M15.

## What fails M16

M16 fails for technical defects such as:

- duplicate grains;
- missing rows between layers;
- unresolved pricing;
- unreconciled estimated, reported, or invoiced cost;
- broken allocation mathematics;
- false realized-savings claims;
- weak telemetry publishing governed request-cost metrics;
- unexplained governance exceptions;
- missing or failed prerequisite pipelines.

## What does not fail M16

A business exception is allowed when it is explicitly classified and explained.

Examples:

- usage estimate differs from provider-reported cost;
- telemetry coverage is incomplete;
- an experiment decision has a financial-evidence mismatch.

Those conditions remain visible in their source marts. M16 checks that the control treatment is complete and honest.

## Repository CI

The package adds:

`.github/workflows/quality.yml`

GitHub Actions runs:

1. Python compilation;
2. the complete Pytest suite;
3. Ruff.

Cloud BigQuery execution is intentionally not run in public CI because it requires project credentials. The authenticated local M16 command performs the cloud validation.

## One-command execution

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_m16.ps1
```

M16 is complete only when:

- all 18 end-to-end BigQuery controls pass;
- every Python file compiles;
- all tests pass;
- Ruff passes.
