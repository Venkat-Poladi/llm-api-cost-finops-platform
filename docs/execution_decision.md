# Execution Decision — Standalone Repository

## Decision

Build this as a standalone GitHub repository named:

`llm-api-cost-finops-platform`

## Reason

The supplied locked scope describes the work as an extension of Project 1 and blocks execution until Project 1 is fully complete. For this new-project build, that dependency is intentionally removed.

The technical scope remains unchanged:

- independent provider usage, provider cost, and telemetry sources
- effective-dated model mapping and rates
- daily allocated usage and monthly cost reconciliation at different grains
- visible unallocated cost
- line-type-aware reconciliation
- experiment governance
- automated controls
- BigQuery and Power BI

## Integration policy

Project 1 integration is deferred to the final optional milestone. Until then:

- this repository owns its own dimensions, facts, marts, controls, and Power BI model
- total cloud cost comparison is represented through a clearly labeled synthetic comparison baseline
- no table or dashboard depends on the Project 1 repository
- later integration must not change existing source grains or reconciliation logic
