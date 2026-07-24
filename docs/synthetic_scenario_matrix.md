# M4 Synthetic Scenario Matrix

## Why the design is written before the generator

A synthetic project becomes untrustworthy when the data is repeatedly changed until the dashboard looks impressive.

This milestone records the business rules, imperfections, and known events first. M5 must run these rules with a fixed seed and report the real result.

## Source independence

The three main sources use different deterministic random-number streams:

1. provider usage;
2. provider cost and invoice lines;
3. request telemetry.

They share the same calendar, provider projects, keys, and workload definitions, but one source is not copied directly from another.

That creates controlled disagreement while preserving reproducibility.

## Workload coverage

The design contains 12 workloads across:

- OpenAI text generation;
- OpenAI embeddings;
- Anthropic text generation;
- standard and batch processing;
- standard and long-context workloads;
- production applications and controlled experiments.

## Realism scenarios

### Shared key

`oa-key-shared` is mapped:

- 60% to Campaign Assistant;
- 30% to Growth Experiment Assistant;
- 10% remains unallocated.

The daily fact must split the source measures rather than copy the complete source row to both applications.

### Ownership change

`an-key-developer` belongs to Engineering through December 2025 and Platform Engineering beginning January 2026.

### Late mapping and restatement

`an-key-lab` is effective from September 2025 but is not recorded until February 2026.

This creates a historical allocation restatement case.

### Completely unmapped key

`an-key-unmapped` has usage but no attribution row.

Its usage must remain in an explicit unallocated bucket.

### Incomplete telemetry

Telemetry coverage varies by workload from 62% to 98%.

Coverage must later be measured, not assumed.

### Retries and failures

Telemetry uses attempt grain.

A logical request can have up to four attempts. Failed attempts are classified as pre-processing rejection or mid-generation failure so estimated failure cost can distinguish likely unbilled from potentially billed failure.

### Cost disagreement

Provider usage estimate, provider-reported cost, and invoice-billed cost are generated separately.

The design includes rounding, late usage, invoice cutoff, credits, commitment true-ups, tax, corrections, and adjustments.

### Experiments

Four experiments demonstrate daily, monthly, and lifetime spending limits with an append-only decision history.

## Predeclared known usage events

The design locks six events before generation:

- support demand spike;
- retry storm;
- embedding re-indexing spike;
- long-context investigation spike;
- cache-read collapse;
- runaway experiment.

These are validation targets, not values to tune after generation.
