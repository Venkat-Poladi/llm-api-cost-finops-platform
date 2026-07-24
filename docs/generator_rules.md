# M4 Generator Rules

## Reporting window

Generate every date from `2025-01-01` through `2026-06-30`.

This is exactly 18 complete months.

## Request volume

For each active workload and date:

1. start with the workload's base daily request volume;
2. apply monthly growth;
3. apply the calendar profile;
4. apply month seasonality;
5. apply any predeclared known event;
6. draw the final count from the configured negative-binomial distribution.

## Token volume

Generate request-level token quantities from lognormal distributions around each workload's median.

Then aggregate provider usage to the locked raw usage grain.

## Provider cache treatment

### OpenAI

- Input already includes cached input.
- Cached input must never exceed input.
- Batch rows have zero cached input in v1.

### Anthropic

Keep separate quantities for:

- uncached input;
- cache reads;
- five-minute cache creation;
- one-hour cache creation.

Batch rows have zero cache quantities in v1.

## Reasoning tokens

Only GPT-5 telemetry may contain nonzero reasoning tokens.

Reasoning tokens are a subset of output tokens.

They are never added again to total tokens.

## Embeddings

OpenAI embedding rows have input tokens and request counts.

They have zero output and reasoning tokens.

Anthropic embedding rows are not generated.

## Telemetry

Generate one row per provider attempt.

The final attempt carries the logical request's terminal result.

Non-final attempts contribute retry cost but do not count as separate successful business requests.

## Financial disagreement

The usage source never stores cost.

M7 will derive the token-based estimate using the historical rate card.

The provider-cost generator uses a separate random stream and the rules in `synthetic_design.yaml`.

Predeclared non-usage cost lines are read from `cost_divergence_events.csv`.

## Allocation

The generator creates the bridge rows exactly as designed.

Allocation itself is not performed in M5; it is performed later in the daily fact.

## Honesty rule

Never manually edit generated output to reach a target total, savings amount, failure rate, allocation rate, or experiment result.

Run the fixed design, validate it, and report the actual outcome.
