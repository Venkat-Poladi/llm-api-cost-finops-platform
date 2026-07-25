# M5 Source Generation

## Purpose

Generate reproducible but imperfect source data for the LLM API Cost FinOps platform.

The generator creates provider usage, provider cost, and request telemetry with separate random-number streams. They share the locked business design but are not copies of one another.

## Generated files

All outputs are written to `data/generated/`.

### `raw_ai_provider_usage.csv`

Daily provider-native aggregated usage.

Important behavior:

- OpenAI carries request count, input tokens, cached input tokens, and output tokens.
- Anthropic carries separate uncached, cache-read, five-minute cache-write, one-hour cache-write, and output tokens.
- Anthropic request count is null because it was not verified in the official organization usage report.
- Raw usage contains no cost field.
- Reasoning tokens are not invented in aggregated provider usage.

### `raw_ai_provider_cost.csv`

Monthly provider-reported and invoiced financial lines.

It contains:

- usage;
- credits;
- commitment true-ups;
- corrections;
- adjustments;
- tax.

Provider-reported and invoice-billed amounts intentionally disagree through documented rules.

### `fct_ai_request_telemetry.csv`

One row per provider request attempt.

It supports:

- logical request versus attempt counts;
- retry cost;
- final request success;
- failure-stage cost;
- request-level token economics;
- experiment cost allocation drivers.

### `bridge_ai_usage_attribution.csv`

Copies the locked effective-dated attribution scenarios into a generated source file.

It includes:

- direct mappings;
- shared-key allocation;
- ownership change;
- late mapping;
- an intentionally unmapped key.

### `dim_ai_experiment_control.csv`

Experiment owners, limits, periods, thresholds, and current statuses.

### `fct_ai_experiment_decision.csv`

Append-only experiment decision history.

### `generation_manifest.json`

Records:

- seed and random streams;
- reporting period;
- output row counts;
- file sizes;
- SHA-256 hashes;
- generated financial totals.

## Reproducibility

The generator uses one locked seed and separate deterministic streams for:

- provider usage;
- provider cost;
- request telemetry;
- attribution;
- experiments.

Running the same installed dependency versions and configuration produces the same files.

## Validation

The validator checks:

- required files;
- manifest hashes;
- unique source grains;
- provider-specific token semantics;
- raw usage has no cost;
- telemetry attempt chains;
- retry and failure rules;
- USD-only financial records;
- required cost line types;
- allocation percentages;
- experiment history;
- source rows for every predeclared event.

## Generated-data policy

Generated files remain local and are excluded from Git by the existing `.gitignore` rule.

The generator code, design configuration, validation code, and summarized results can later be published to GitHub. The 69 MB telemetry file should not be committed.
