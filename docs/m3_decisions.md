# M3 Decisions

## 1. Reporting period

The generated dataset will cover 18 complete months:

- Start: `2025-01-01`
- End: `2026-06-30`

July 2026 is excluded because it is an incomplete month when the design was locked.

## 2. FOCUS version

FOCUS `1.4` is pinned.

Financial billing, invoice, correction, and allocation semantics may map to FOCUS.

Operational LLM fields remain project extensions.

## 3. Usage types

Allowed values:

- `text_generation`
- `embedding`

`usage_type` is added to usage, model-map, rate-card, and daily-fact grains so text-generation and embedding records cannot be confused.

## 4. Provider scope

- OpenAI: text generation and embeddings
- Anthropic: text generation only

No third-party embedding service is disguised as Anthropic usage.

## 5. Models selected for the 18-month synthetic period

### OpenAI

- `gpt-4o-mini-2024-07-18`
- `gpt-5-2025-08-07`
- `text-embedding-3-small`

### Anthropic

- `claude-3-5-haiku-20241022`
- `claude-sonnet-4-20250514`

Only GPT-5 telemetry carries nonzero reasoning tokens in v1.

## 6. Service tiers used by the generator

### OpenAI

- Provider tier: `default`
- Batch: separate boolean

### Anthropic

- Provider tiers: `standard`, `batch`
- Anthropic `batch` normalizes to `normalized_processing_tier = standard` and `is_batch = true`

Observed but not generated in v1:

- OpenAI `flex`, `priority`
- Anthropic `priority`

This prevents us from inventing unsupported price rows.

## 7. Batch and cache rule

The official Batch discount is used.

To avoid assuming that cache and Batch discounts stack identically across providers, v1 synthetic batch rows carry zero cache-token quantities.

## 8. Rate-card unit

All rate columns are USD per one million tokens.

The rate card stores rates in columns, not separate billable-unit rows.
