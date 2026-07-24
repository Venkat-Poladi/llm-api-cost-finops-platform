# Provider Field Validation

**Retrieval date:** 2026-07-21

## Why this document exists

The project must not pretend that provider response telemetry, organization usage reports, and cost reports have the same schema. They are separate sources with different grains and fields.

## OpenAI

### Organization completions usage

Official endpoint:

`GET /v1/organization/usage/completions`

Verified fields used by this project:

- `input_tokens`
- `input_cached_tokens`
- `output_tokens`
- `num_model_requests`
- `project_id`
- `api_key_id`
- `model`
- `batch`
- `service_tier`

Important correction:

The organization usage field is `input_cached_tokens`. It is not `cached_input_tokens`.

The organization usage object does not expose reasoning tokens in the reviewed schema, so `reasoning_tokens` is not invented in the raw aggregated usage source.

### OpenAI response telemetry

A response usage object uses:

- `usage.input_tokens`
- `usage.input_tokens_details.cached_tokens`
- `usage.output_tokens`
- `usage.output_tokens_details.reasoning_tokens`
- `usage.total_tokens`

Therefore reasoning-token analysis comes from request telemetry, not the organization usage report.

### OpenAI embeddings

Official organization usage endpoint:

`GET /v1/organization/usage/embeddings`

Verified fields:

- `input_tokens`
- `num_model_requests`
- `project_id`
- `api_key_id`
- `model`

Embedding rows have no output-token charge in the v1 model.

### OpenAI organization cost

Official endpoint:

`GET /v1/organization/costs`

Verified fields:

- `amount.value`
- `amount.currency`
- `line_item`
- `project_id`

The Costs API is financially authoritative for OpenAI provider-reported cost in this project. Synthetic invoice differences are created independently later.

## Anthropic

### Organization Messages usage report

Official endpoint:

`GET /v1/organizations/usage_report/messages`

Verified fields:

- `uncached_input_tokens`
- `cache_creation.ephemeral_5m_input_tokens`
- `cache_creation.ephemeral_1h_input_tokens`
- `cache_read_input_tokens`
- `output_tokens`
- `api_key_id`
- `workspace_id`
- `model`
- `service_tier`
- `context_window`

The project maps `workspace_id` to the cross-provider field `provider_project_id` in staging.

### Anthropic embeddings boundary

No native Anthropic embeddings endpoint was verified in the official documentation reviewed for this milestone.

Decision:

- OpenAI contributes text-generation and embedding usage.
- Anthropic contributes text-generation usage only.
- A third-party embedding provider is not silently represented as Anthropic.

## Raw versus normalized fields

The raw tables preserve provider-specific token columns.

The staging layer later creates cross-provider normalized columns. This avoids claiming that OpenAI and Anthropic cache semantics are identical.

## Official source register

- OpenAI Usage and Costs API:
  `https://platform.openai.com/docs/api-reference/usage/`
- OpenAI response usage:
  `https://platform.openai.com/docs/api-reference/responses`
- OpenAI model pricing:
  `https://developers.openai.com/api/docs/models`
- Anthropic Messages usage report:
  `https://docs.anthropic.com/en/api/admin-api/usage-cost/get-messages-usage-report`
- Anthropic pricing:
  `https://docs.anthropic.com/en/docs/about-claude/pricing`
- FOCUS 1.4:
  `https://focus.finops.org/focus-specification/v1-4/`
