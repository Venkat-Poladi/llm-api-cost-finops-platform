# PROJECT 2 — LLM API Cost FinOps: Text Generation and Embeddings (Scope v7 — LOCKED)

**Context for any reader:** This extends the Retail Co. FinOps Cost Management Platform (Project 1) — a multi-cloud (AWS/GCP) synthetic billing platform with FOCUS-conformed data, allocation, forecasting, optimization, and unit economics, built through BigQuery marts and a Power BI semantic model. Project 2 adds a cost-side view of direct LLM API consumption (Claude API, OpenAI API) on top of that architecture. Self-contained — assumes no prior discussion.

**Version history.** v1: single clean dataset (too perfect to be credible). v2: introduced source disagreement, imperfect attribution, historical pricing, request telemetry, evaluation gates, disciplined backlog. v3: fixed six modeling inconsistencies (double-count grain, single-variance reconciliation, cache field mismatch, rate-card grain/column conflict, unreconciled telemetry, contradictory completion gate). v4: closed five executability gaps (telemetry `provider_project_id`; rate-card column/grain double-encoding; estimate-vs-billed failure-cost label; nullable-model cost lines; per-metric cost basis). v5: closed four basis/grain gaps (Cluster A invoiced basis; experiment invoiced-cost derivation; provider-native cache fields in telemetry; unique cost-line grain). v6: closed four consistency gaps (`is_batch` as rate-card key; experiment-decision table defined; eligible-usage-only experiment allocation; `dim_ai_model_map` for model→snapshot). **v7 (this version — LOCKED): closes the final 12-item lock list** — telemetry attempt grain defined; shared-key allocation formulas + source/allocated split; expanded daily-fact grain for pricing drivers; line-type-aware reconciliation (no usage variance on tax/credit lines); zero-denominator + residual (`allocated + unallocated = source`) rules; scope-aware experiment allocation; limit-period-aware experiment spend with percentage thresholds; USD-only v1 lock (+ removed meaningless `billing_currency` from the usage source); normalized-tier rate-card key; `dim_ai_model_map` added to the object inventory (now eight); an 18-test automated control set (Section 16); and the stale "v3 principle" wording fixed. No new scope. **This version is locked; remaining risk moves to the build.**

---

## 0. Preconditions — do not start building until these are true

Per Project 1's sequencing rule, Project 2 does not begin until every Project 1 phase passes acceptance criteria, reconciles, is documented, independently explainable, committed to GitHub, and accurately represented in the README. No parallel work. Two Project 1 items are still open and should close first: the README shows a stale baseline ($186,268.60 vs. the current canonical $188,009.96), and several Power BI polish items (forecast-accuracy color logic, status coloring, chart-title consistency, KPI horizon labeling) aren't confirmed fixed.

---

## 1. Purpose and scope boundary

**Purpose.** Model direct API-based LLM consumption (Claude, OpenAI) with the rigor Project 1 applies to cloud billing — reconciled financial cost, imperfect allocation, unit economics, cost-side optimization, experimentation governance — answering: how much are we spending on LLM APIs, is cost growing faster than the usage driving it, where is the waste, is experimentation spend controlled.

**In scope (v1 build):** text-generation and embedding token usage; estimated vs. reported vs. invoiced cost with modeled reconciliation; imperfect attribution to application/department/cost-center; request-level telemetry for success/failure economics; cost-side optimization with an evaluation gate; experiment cost governance.

**Explicitly excluded (honest boundary):** vector-database/RAG cost (supporting infra, not text inference — backlog); ROI/value/quality/latency without real benchmarking (permitted framing: "establishes the cost side of LLM unit economics; value/ROI needs product-outcome integration"); multimodal, fine-tuning/training, GPU/provisioned capacity, server-side tool charges (all backlog, Section 12). The name declares the boundary rather than implying broader coverage than is built.

## 2. Architecture principle — realism through disagreement

Reuses Project 1's pattern and integrity rule (generate from documented rules, run once, report the real result including misses — never tune to a target). Defining project principle: **production realism is simulated through source disagreement, attribution uncertainty, and incomplete telemetry — not by adding services.** A synthetic project can't obtain real invoices, but it can generate independent sources that legitimately fail to reconcile perfectly, then explain the variance.

```
Provider Usage pipeline ───────┐
Provider Cost/Invoice pipeline ┼─> Reconciliation fact (monthly) ─> Allocation, Unit econ,
Request/Gateway telemetry ─────┤   Allocated usage fact (daily)     Experiment gov, Optimization
Internal ownership maps ───────┘
```

## 3. Core objects (eight: seven primary + one decision-event companion)

| Object | Role |
|---|---|
| `raw_ai_provider_usage` | Independently generated aggregated usage (tokens, requests), provider-native dimensions only. |
| `raw_ai_provider_cost` | Independently generated cost/invoice data (reported + invoiced amounts, credits, adjustments). |
| `fct_ai_request_telemetry` | Request-level operational fact — attempt-grained; success/failure, failure stage, per-attempt tokens + estimated cost. |
| `bridge_ai_usage_attribution` | Effective-dated, imperfect API-key/project → application/department/cost-center mapping. |
| `dim_ai_model_rate` | Effective-dated rate card (wide format). |
| `dim_ai_model_map` | Effective-dated provider model name → model_snapshot mapping (so usage `model` resolves to a priced snapshot). |
| `dim_ai_experiment_control` | Experiment governance registry. |
| `fct_ai_experiment_decision` | Companion decision **event/history** table (auditable Stop/Continue/Modify/Scale trail; columns in 4f-b). |

`dim_ai_model_map` controls: no overlapping model-map effective windows; every usage `model` resolves to exactly one `model_snapshot` for its month; every `model_snapshot` resolves to exactly one applicable rate row.

Two derived facts are built from these (Section 4g), at **explicitly different grains**, to prevent the daily-usage-to-monthly-invoice fan-out.

---

## 4. Data generator — sources and fields

Provider Usage/Cost APIs report data *grouped* by dimensions with a request count, not one row per call. The three provider-facing sources are generated **independently** so reconciliation is real.

### 4a. `raw_ai_provider_usage` (daily aggregated usage — provider-native only)
Grain: (`usage_date`, `provider`, `provider_project_id`, `api_key_id`, `model`, `provider_service_tier`, `is_batch`, `context_window_tier`).

Fields: `request_count`, `input_tokens`, `output_tokens`, `reasoning_tokens` (⊆ output_tokens; 0 for non-reasoning models), plus **provider-native cache fields** (see 5b for why these differ by provider):
- OpenAI rows: `cached_input_tokens` (⊆ `input_tokens`).
- Anthropic rows: `uncached_input_tokens`, `cache_read_input_tokens`, `cache_creation_5m_tokens`, `cache_creation_1h_tokens` (Anthropic's `input_tokens` excludes cache; these four are separate quantities).
Also: `is_synthetic`. (**No `billing_currency`** — the usage source carries no financial amount, so a currency field here is meaningless; currency lives only on cost/limit records.)

**No cost field here.** `usage_cost_estimate` is *derived in staging* from token math × `dim_ai_model_rate`, keeping the raw layer provider-native (a raw source wouldn't contain your rate assumptions).

### 4b. `raw_ai_provider_cost` (billing-period reported/invoiced cost)
Grain: (`billing_period`, `provider`, `provider_project_id`, `model`, `line_item_type`, `provider_line_item_id`). **`model` is nullable** — tax, account-level credits, commitment true-ups, and corrections often apply at project or invoice level, not to one model. `provider_line_item_id` is **part of the grain** — without it, two invoice-level corrections or credits in the same period/project/null-model/type would collide; including it guarantees uniqueness. (If a source doesn't supply a stable line-item id, aggregate source lines to this grain before load rather than leaving it ambiguous.)

Fields: `line_item_scope` (model / project / invoice — states what the row applies to, so null `model` is meaningful rather than missing data), `line_item_type` (usage / credit / commitment_true_up / correction / adjustment / tax), `provider_reported_cost`, `invoice_billed_cost`, `billing_currency`, `credit_amount`, `adjustment_reason`, `invoice_issue_date`, `is_restatement`, `is_synthetic`.

When reconciling to model-grained usage, non-model-scoped line items (`line_item_scope` in {project, invoice}) are allocated across models by a documented driver or held at their own scope — never silently attributed to a single model.

Generated independently of usage, with modeled divergence from the staged estimate: rounding, late-arriving usage, invoice-period cutoffs, credits, contractual discounts, minimum-commitment true-ups, corrections/restatements, tax. Some periods should legitimately miss reconciliation tolerance.

### 4c. `fct_ai_request_telemetry` (request-level, minimal)
**Grain: one row per provider request *attempt*.** A retried logical request produces several provider attempts; conflating them corrupts request counts, failure rates, retry cost, and cost-per-successful-request.
Identity/outcome fields: `logical_request_id` (the business request), `provider_request_id` (this attempt), `attempt_number`, `attempt_status` (success / failed / cancelled — this attempt's outcome), `is_final_attempt` (bool), `final_request_status` (the logical request's terminal outcome), `retry_reason`.
Context fields: `usage_date`, `provider`, `provider_project_id`, `api_key_id`, `application_name`, `experiment_id`, `model`, `failure_stage` (`rejected_pre_processing` — typically unbilled / `mid_generation_error` — may still cost).
Measures: `input_tokens`, `output_tokens`, `reasoning_tokens`, and the **provider-native cache fields** — `cached_input_tokens` (OpenAI) and `uncached_input_tokens` / `cache_read_input_tokens` / `cache_creation_5m_tokens` / `cache_creation_1h_tokens` (Anthropic, nullable for OpenAI) — then `usage_cost_estimate`.
(`provider_project_id`/`api_key_id` let telemetry reconcile to `raw_ai_provider_usage` on `date + provider + project + model` per Phase 14. Anthropic cache fields mirror 4a so request-level estimated cost is reproducible when 5-minute and 1-hour cache-write rates differ. Success-rate and cost-per-successful-request metrics operate on `is_final_attempt = true` / `final_request_status`; retry cost sums non-final attempts.)

### 4d. `bridge_ai_usage_attribution` (imperfect, effective-dated)
`provider`, `provider_project_id`, `api_key_id`, `application_name`, `department_name`, `cost_center`, `allocation_percentage`, `effective_start_date`, `effective_end_date`, `mapping_status`, `allocation_method`, `allocation_confidence`.
Realistic cases required: clean 1:1 key→app; shared key percentage-allocated (percentages sum to 100% per key per effective window — enforced as a control); key changing ownership mid-period; some usage unallocated (surfaced, never force-assigned); one late mapping causing historical restatement.

### 4e. `dim_ai_model_rate` (effective-dated rate card — WIDE format)
Grain: (`provider`, `model_snapshot`, `normalized_processing_tier`, `is_batch`, `context_window_tier`, `effective_start`, `effective_end`). **`billable_unit` is not in the grain** — rates are columns, not rows. The tier key is `normalized_processing_tier` (the project-normalized value), so downstream joins from `fct_ai_usage_daily` are consistent; `provider_service_tier` is retained only as the provider-native source value, not a join key. `is_batch` is a separate grain key (consistent with 4a and 5d) — batch is **not** a tier value.
Because `normalized_processing_tier`, `is_batch`, and `context_window_tier` are all grain keys, each row carries only the rates that *apply to that tier/batch/context combination* — no separate batch/priority/long-context rate columns (those would double-encode dimensions that are already keys). Rate columns: `input_rate`, `cached_input_rate`, `cache_write_5m_rate`, `cache_write_1h_rate`, `output_rate`, `contracted_discount`. So the batch input rate is the `input_rate` on the `is_batch = true` row; the long-context output rate is the `output_rate` on the `context_window_tier = long` row. Metadata: `rate_source`, `rate_retrieved_date`, `model_launch_date`, `model_retirement_date`.

**Model join rule.** Usage sources carry a provider `model` string; the rate card is keyed by `model_snapshot` (a specific dated model version). Resolve via an effective-dated mapping so the historical lookup is executable, not just conceptual:
```
dim_ai_model_map: provider, provider_model_name, model_snapshot, effective_start, effective_end
```
Usage `model` → `provider_model_name` → `model_snapshot` (for the usage month) → rate row. If a provider `model` maps 1:1 and never re-versions, the map is trivial, but it must exist so re-versioned models price correctly across the 18 months.
18-month rule: usage in month M is priced with the rate row whose effective window contains M — never a current price/model applied to a historical period.

### 4f. `dim_ai_experiment_control` (fully specified)
`experiment_id`, `owner`, `approver`, `hypothesis`, `application_name`, `cost_center`, `spending_limit`, `spending_limit_period` (day / month / lifetime), `limit_currency`, `warning_threshold`, `hard_stop_threshold`, `start_date`, `planned_end_date`, `current_status`, `override_reason`.

### 4f-b. `fct_ai_experiment_decision` (decision event/history)
Grain: one row per experiment decision event.
`experiment_decision_id`, `experiment_id`, `decision` (Stop / Continue / Modify / Scale), `decision_date`, `decided_by`, `rationale`, `previous_status`, `new_status`.
Keeping decisions as an append-only event table (rather than one mutable field on `dim_ai_experiment_control`) preserves an auditable trail; `dim_ai_experiment_control.current_status` reflects the `new_status` of the latest event.

### 4g. Two derived facts at DIFFERENT grains (the fix for double-counting)
- **`fct_ai_usage_daily`** — grain: daily, (`usage_date`, `provider`, `provider_project_id`, `api_key_id`, `model`, `model_snapshot`, `provider_service_tier`, `normalized_processing_tier`, `is_batch`, `context_window_tier`, plus attributed `application_name`/`department_name`/`cost_center` via the bridge). The extra dimensions are required so batch adoption, cache analysis, and historical-rate validation remain possible downstream. Additive measures (tokens, requests, cost estimate) are not grain keys. This is the daily allocated-usage fact for trends and chargeback.

  **Allocation formulas (locked) — shared keys must not duplicate usage.** Retain source *and* allocated columns separately:
  ```
  allocated_usage_cost_estimate = source_usage_cost_estimate × allocation_percentage
  allocated_input_tokens        = source_input_tokens        × allocation_percentage
  allocated_output_tokens       = source_output_tokens       × allocation_percentage
  allocated_request_count       = source_request_count       × allocation_percentage
  ```
  A shared key mapped to two applications thus splits its cost/tokens, never doubles them.

  **Zero-denominator and residual rules (locked).** For any allocation that divides by an estimate-share denominator:
  ```
  if eligible denominator > 0:  allocate by estimate share
  if denominator = 0:           allocated_cost = 0; unallocated_cost = source_cost;
                                allocation_status = "No eligible driver"
  ```
  Every allocation must satisfy `allocated_cost + unallocated_cost = source_cost`. For ratio metrics (cache share, reasoning overhead, telemetry coverage, cost per request), return `NULL` when the denominator is zero — never 0.
- **`fct_ai_cost_reconciliation`** — grain: **monthly**, (`billing_month`, `provider`, `provider_project_id`, `model`, `line_item_type`, `provider_line_item_id`). Carries `usage_cost_estimate` (daily estimate rolled up to month, usage lines only), `provider_reported_cost`, `invoice_billed_cost`, and the reconciliation columns in Section 5c.

Monthly invoice cost is **never joined directly to daily usage rows.** Where daily invoice-level cost is needed, monthly invoiced cost is allocated down to days using a documented driver (daily estimate share), with the method recorded — not fanned out by join.

**Experiment invoiced cost (allocation rule).** `experiment_id` exists in `fct_ai_request_telemetry`, not in monthly invoice data, so experiment spend on an invoiced basis is allocated, but **only from eligible usage-related invoice lines**, and **within the source line's own scope**:
```
eligible lines: line_item_type = 'usage' only

model-scoped usage line (line_item_scope = model):
  allocate within provider + provider_project_id + month + model
project-scoped usage line (line_item_scope = project):
  allocate within provider + provider_project_id + month

experiment_invoiced_cost =
  eligible_invoice_cost
  × (experiment telemetry usage_cost_estimate ÷ total telemetry usage_cost_estimate,
     computed within that same scope)
```
Non-usage lines — tax, commitment true-ups, project-level credits, corrections — are **not** charged to experiments; they stay at project/invoice scope unless an explicit documented policy says otherwise. Method and driver recorded alongside the result.

**Experiment spend vs. limit — align basis to the limit period.** `spending_limit_period` drives which cumulative window is compared:
```
day limit:      daily allocated invoiced cost
month limit:    monthly allocated invoiced cost
lifetime limit: cumulative allocated invoiced cost, experiment start_date → current_date
```
`warning_threshold` and `hard_stop_threshold` are **percentages of `spending_limit`** (v1 choice — simpler than currency amounts): e.g. warn at 0.80, hard-stop at 1.00.

---

## 5. Corrected semantics (locked)

### 5a. Token math
```
total_tokens          = input_tokens + output_tokens        (reasoning is WITHIN output)
reasoning_tokens     <= output_tokens
visible_output_tokens = output_tokens - reasoning_tokens
```
Do not add reasoning tokens as a separate billed quantity unless a rate card bills them separately.

### 5b. Cache — provider-native fields, one documented normalization, no universal "hit ratio"
The v2 schema/formula mismatch is resolved: Anthropic now stores `uncached_input_tokens` + `cache_read_input_tokens` + `cache_creation_5m_tokens` + `cache_creation_1h_tokens` (matching the formula); OpenAI stores `cached_input_tokens` (⊆ `input_tokens`). Normalization layer:
```
normalized_total_input_tokens =
  OpenAI:    input_tokens                                (already includes cached)
  Anthropic: uncached_input_tokens + cache_read_input_tokens
             + cache_creation_5m_tokens + cache_creation_1h_tokens
normalized_cache_read_tokens =
  OpenAI:    cached_input_tokens
  Anthropic: cache_read_input_tokens
cache_read_share = normalized_cache_read_tokens / normalized_total_input_tokens
```
Publish `cache_read_share` (normalized), not a reads-over-writes ratio.

### 5c. Reconciliation — TWO variances, and line-type aware
Three amounts imply two reconciliations with different causes — but only *usage* lines have a token-derived estimate, so the usage-side reconciliation doesn't apply to tax/credit/true-up/invoice-only lines:
```
usage lines (line_item_type = 'usage'):
  usage_to_reported_variance = provider_reported_cost - usage_cost_estimate
      (causes: pricing assumptions, late usage, rounding)

tax / credit / commitment_true_up / correction / adjustment lines:
  usage_cost_estimate        = NULL
  usage_to_reported_variance = NULL
  reconciliation_applicability = "Not applicable"

all applicable cost lines:
  reported_to_invoice_variance = invoice_billed_cost - provider_reported_cost
      (causes: credits, true-ups, taxes, corrections, adjustments)
```
`fct_ai_cost_reconciliation` carries: `reconciliation_applicability`, `usage_to_reported_variance`, `reported_to_invoice_variance`, `usage_reconciliation_status`, `invoice_reconciliation_status`, `variance_reason_code`, `exception_status`. The dashboard shows *which* financial layer disagreed, never a single blended variance, and never charges a usage-estimate miss against a line that has no usage estimate.

### 5d. Service tier — do not force one enum
`provider_service_tier` (native), `normalized_processing_tier` (project-defined, the downstream join key), `is_batch` (separate boolean). Exact native values (OpenAI `default`/`flex`/`priority`; Anthropic `standard`/`batch`/`priority`) are medium-confidence from secondary sources — verify against live API/pricing in the evidence step (Section 9) before locking enums.

### 5e. Currency — USD-only for v1 (locked)
```
billing_currency = "USD"   limit_currency = "USD"   reporting_currency = "USD"
```
No FX conversion in v1; multi-currency is backlog (Section 12). Without this lock, experiment-spend-vs-limit comparisons across currencies aren't guaranteed valid. All cost and limit records assert USD; a non-USD value is a data-quality failure, not a conversion trigger.

---

## 6. Metrics — by the decision each drives

**Cost basis — every metric declares which of the three amounts it uses (locked rule):** financial KPIs (Cluster A cost-share and growth, Cluster D chargeback, Cluster E experiment spend vs. limit) use allocated `invoice_billed_cost` — Cluster A specifically because it is compared against Project 1's billed/effective `fct_cloud_cost`, and comparing an *estimate* against a *billed* figure would mix two financial bases; operational/efficiency metrics (Clusters B–C, waste, unit economics) use `usage_cost_estimate`; reconciliation pages show all three (`usage_cost_estimate`, `provider_reported_cost`, `invoice_billed_cost`). No metric silently mixes bases; each visual labels its basis.

**A — Is LLM cost growing faster than the usage driving it?** LLM cost as % of total cloud cost (invoiced basis, vs. Project 1 `fct_cloud_cost`); cost MoM growth; request-volume MoM growth; the *gap* between them (the signal).
**B — Where is the waste?** `cache_read_share` (normalized, 5b); estimated cache savings; **estimated cost of failed requests** (telemetry, `failure_stage`-filtered — labeled *estimated*, since telemetry carries `usage_cost_estimate`, not billed cost); reasoning overhead % (`reasoning_tokens / output_tokens`); batch adoption % and savings.
**C — Is cost per unit improving?** Cost per request; cost per successful response (telemetry); cost per model (gated, Section 8); avg tokens per request (diagnostic only). Caveat: cost-per-request is labeled as such, not cost-per-task (agentic task economics are backlog).
**D — Who owns it?** Cost by app/dept/cost-center **through the imperfect bridge**, with a visible unallocated bucket and allocation-confidence.
**E — Is experimentation controlled?** Spending-limit consumption % (respecting period + currency); experiments over warning/hard-stop threshold; decision distribution from `fct_ai_experiment_decision`. Reporting, not enforcement (automated controls are backlog).
**F — Optimization funnel.** Project 1 Section 6 discipline (gross/net/overlap), applied to caching, batch migration, model right-sizing (gated). Identified ≥ Approved ≥ Implemented ≥ Realized, net only.
**Excluded:** ROI/value/quality/latency without benchmarking.

---

## 7. Marts
`fct_ai_usage_daily` and `fct_ai_cost_reconciliation` (facts, Section 4g); `mart_ai_token_economics`, `mart_ai_application_cost` (via bridge), `mart_ai_optimization`, `mart_ai_unit_economics`, `mart_ai_experiments`. (GPU/vector/multimodal marts are backlog.)

## 8. Evaluation gate on model-right-sizing (required)
Cost alone can't approve a model swap without violating the "don't fabricate quality" boundary. Fields on recommendations: `recommendation_status`, `evaluation_required_flag`, `evaluation_reference`, `quality_gate_status`, `latency_gate_status`, `security_gate_status`, `eligible_for_implementation`. Permitted language: "Estimated potential savings *if* the alternative model passes quality, latency, and security evaluation." Savings move to Approved/Implemented only after the gate passes. No actual evaluation platform required — only honest representation in the funnel.

## 9. Evidence package (live API validation)
Three distinct shapes; a request-level response does not prove the org API shapes:
```
evidence/
├── openai_response_usage_redacted.json   (request-level — token semantics)
├── openai_org_usage_redacted.json        (org Usage API bucket shape)
├── openai_org_cost_redacted.json         (org Costs API record shape)
├── anthropic_response_usage_redacted.json
└── provider_field_validation.md          (doc vs. observed, with retrieval date)
```
Org files only where permissions allow. This step confirms the token fix, the cache field names, the exact service-tier enums, and the OpenAI surface before they're locked.

## 10. FOCUS decision (resolved)
Financials (billed cost, effective cost, billing periods, invoice reconciliation, provider/service/product) map to FOCUS. Operational fields (reasoning tokens, cache-token categories, request status, experiment IDs) go in `x_` extension columns or the companion telemetry fact. **Pin the exact FOCUS version at build time** — candidate is FOCUS 1.4 (referenced for its invoice/billing-period/correction/reconciliation support), to be confirmed against the FOCUS spec during Phase 12 and recorded in the doc; do not leave it as "reuse Project 1's pattern."

## 11. Phase plan with acceptance criteria
- **Phase 11 — Source generation.** Three sources generated independently, 18 months, seeded. *Complete when:* seed reproduces output; no ROI/value fields; usage and cost sources show modeled divergence (some periods miss tolerance); estimate derived in staging, not raw.
- **Phase 12 — Staging + rate card + bridge + FOCUS version pinned.** *Complete when:* historical months price against effective-dated rates; bridge includes shared-key/ownership-change/unallocated/restatement cases and allocation percentages sum to 100% per key per window; FOCUS version recorded.
- **Phase 13 — Two derived facts.** Build `fct_ai_usage_daily` (daily) and `fct_ai_cost_reconciliation` (monthly). *Complete when:* grain tests prove no monthly-cost fan-out across daily rows; both variances (`usage_to_reported`, `reported_to_invoice`) + `variance_reason_code` + per-layer `reconciliation_status` present; unallocated cost visible.
- **Phase 14 — Telemetry reconciliation control.** *Complete when:* `telemetry_token_coverage_pct = telemetry_tokens / provider_usage_tokens` computed by (`date`,`provider`,`project`,`model`); telemetry coverage %, untraceable provider-usage cost, request-count variance, and token-count variance reported — proving the two facts describe the same consumption.
- **Phase 15 — Token economics.** *Complete when:* normalized cache metric, reasoning overhead, cost-per-token reconcile within tolerance.
- **Phase 16 — Application cost via bridge.** *Complete when:* allocation reconciles to the reconciliation fact; unallocated + confidence surfaced; no double-count; no over-allocation (percentages validated).
- **Phase 17 — Optimization + evaluation gate.** *Complete when:* funnel holds on net savings; right-sizing recs carry gate fields and "potential savings if…" language; batch-migration category present.
- **Phase 18 — Unit economics.** *Complete when:* cost-per-request and cost-per-successful-response reproducible from telemetry; failure cost grounded in `failure_stage`; cost-per-request labeled (not cost-per-task).
- **Phase 19 — Experiment governance.** *Complete when:* experiments fully specified (limit + period + currency + thresholds); decisions in the event table; consumption reconciles.
- **Phase 20 — Reporting.** Surface decision pending. *Complete when:* totals reconcile to BigQuery within tolerance; canonical-measure-reuse discipline followed.

## 12. Backlog (deferred, `future_backlog.md`, one-line rationale each)
Multimodal billing; vector-DB meters + RAG; fine-tuning/training and GPU/provisioned capacity + `mart_ai_gpu_economics`; driver-based forecast/budget marts + scenarios; automated runaway-agent controls; direct-provider vs. reseller routing; agent-run/business-task unit economics.

## 13. Success metrics — fill in only after Phase 11 runs
Project 1 Section 4 format (Baseline / Target / Modeled Result / Status), empty here so nothing is worked backward from a target. Set limit periods and units explicitly (day/month/lifetime) to avoid the monthly-vs-annual unit error caught in Project 1.

## 14. Open decisions (reduced)
1. OpenAI API surface (Responses vs. Chat Completions) — evidence step.
2. Exact native service-tier enums — evidence step.
3. Power BI reporting surface (new page vs. separate report) — before Phase 20.
4. Which synthetic models are reasoning-capable (only those carry nonzero reasoning tokens).
5. Exact FOCUS version — confirm and pin in Phase 12.

## 15. Completion gate (reworded to match modeled divergence)
Deliberate reconciliation misses are required by Section 4, so "all phases reconcile within tolerance" would contradict the design. Correct gate: **every reconciliation must either pass tolerance, or carry a documented, approved exception with an identified variance cause (`variance_reason_code`).** No *unexplained* failures. Beyond that, Project 2 is complete only when all phases pass acceptance criteria, grain tests prevent duplication, usage/telemetry/reported/invoiced amounts reconcile or are explained, allocation never over-allocates, effective-dated rates resolve correctly, and Power BI totals match BigQuery — committed to GitHub and accurately documented, to Project 1's standard.

## 16. Automated control set (locked into acceptance criteria)
Every item is a pass/fail test, run in the pipeline, not a manual check:
```
1  raw_ai_provider_usage grain is unique
2  raw_ai_provider_cost line grain is unique (incl. provider_line_item_id)
3  fct_ai_request_telemetry attempt grain is unique
4  reasoning_tokens <= output_tokens (all rows)
5  OpenAI cached_input_tokens <= input_tokens (all OpenAI rows)
6  no overlapping dim_ai_model_map effective windows
7  no overlapping dim_ai_model_rate effective windows
8  every usage row resolves to exactly one model-map row
9  every staged usage row resolves to exactly one rate row
10 shared-key allocation_percentage sums to <= 100% per key per effective window
11 allocated_cost + unallocated_cost = source_cost (every allocation)
12 no monthly invoice cost fanned out into daily rows (grain test)
13 non-usage lines carry no token-derived estimate (usage_cost_estimate IS NULL)
14 telemetry token coverage is computed, not assumed
15 every reconciliation exception has a variance_reason_code
16 experiment decisions form a valid chronological history (previous_status chains)
17 all cost/limit records assert USD
18 Power BI totals equal BigQuery totals
```