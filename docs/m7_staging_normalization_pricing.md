# M7 — Staging, Normalization, and Historical Pricing

## What this milestone does

M7 converts provider-native source fields into consistent analytical fields and calculates the historical token-based cost estimate.

## Tables created

### `dim_ai_service_tier_map`

Maps provider-native service tiers into the project's normalized processing tier.

### `stg_ai_provider_usage_normalized`

Adds:

- stable source usage key;
- effective-dated model snapshot;
- normalized processing tier;
- normalized input and cache quantities;
- visible output tokens;
- model, service-tier, and token validation statuses.

### `stg_ai_provider_usage_priced`

Adds:

- effective-dated historical rate;
- pricing inputs;
- `usage_cost_estimate`;
- pricing status.

### `stg_ai_provider_cost`

Normalizes billing month, currency, nullable model, and reconciliation applicability.

### `stg_ai_request_telemetry`

Adds usage type, normalized token quantities, successful logical-request indicator, retry indicator, and telemetry validation status.

## Cost calculation

### OpenAI

OpenAI input tokens already include cached tokens.

The calculation separates:

- uncached input;
- cached input;
- output.

Reasoning tokens remain inside output and are not charged twice.

### Anthropic

The calculation separately prices:

- uncached input;
- cache reads;
- five-minute cache writes;
- one-hour cache writes;
- output.

## Important protection

Every raw usage row remains one staging row.

Effective-dated model and rate lookups are resolved using arrays and match counts, so a bad overlapping dimension cannot silently duplicate the source row.

## One-command execution

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_m7.ps1
```

M7 is complete only when all 14 BigQuery controls, all Python tests, and Ruff pass.
