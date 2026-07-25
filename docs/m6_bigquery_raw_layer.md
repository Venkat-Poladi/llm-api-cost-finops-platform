# M6 — BigQuery Raw Layer

## What this milestone does

M6 moves the validated local source files into BigQuery without changing their business meaning.

The raw layer contains eight objects:

1. `raw_ai_provider_usage`
2. `raw_ai_provider_cost`
3. `fct_ai_request_telemetry`
4. `bridge_ai_usage_attribution`
5. `dim_ai_experiment_control`
6. `fct_ai_experiment_decision`
7. `dim_ai_model_map`
8. `dim_ai_model_rate`

## One-command execution

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_m6.ps1
```

The command:

1. uses existing M5 output, or creates it if missing;
2. reruns the M5 source validation;
3. creates the five BigQuery datasets;
4. replaces the eight project-owned raw tables;
5. checks local-to-BigQuery row counts;
6. runs ten raw-layer controls;
7. writes a local M6 manifest;
8. runs the complete Python test and Ruff suites.

## Safe rerun behavior

The loader replaces only these eight project-owned raw tables.

It does not delete datasets or unrelated tables.

## BigQuery objects created

### Raw dataset

`finops-learning-lab.llm_finops_raw`

### Control dataset

`finops-learning-lab.llm_finops_control`

Control tables:

- `pipeline_run_log`
- `raw_load_reconciliation`
- `raw_load_control_result`

## Acceptance criteria

M6 is complete only when:

- all eight table row counts equal their source files;
- all ten BigQuery controls report zero violations;
- the complete Python test suite passes;
- Ruff passes;
- `data/generated/m6_bigquery_manifest.json` is written.
