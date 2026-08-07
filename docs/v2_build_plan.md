# Phase 2 Build Plan

# AI FinOps Governance, Budgeting, and Optimization Platform

## Objective

Extend the completed v1 platform without rebuilding working OpenAI and Anthropic capabilities. Phase 2 adds Amazon Bedrock, Vertex AI/Gemini, limited supporting infrastructure, one small hosted-inference endpoint, budgeting, forecasting, fully loaded cost, quality and latency governance, anomalies, guardrails, provider economics, and management deliverables.

The platform remains a financial-control and analytics system. It must not become a chatbot or autonomous AI-management agent.

## Fixed and generated values

The only predetermined financial output is the approved annual AI budget:

**$76,438.52**

Actual cost, forecast, variances, opportunities, implemented run-rate, and verified modeled savings must be generated from documented assumptions and must not be manually targeted after generation.

## Milestone sequence

### M21 — Enterprise Workload and Provider Foundation

Build the eight-workload/four-experiment inventory, provider-channel dimension, ownership, approved provider/model mapping, effective-dated rate-card contract, quality/latency/reliability thresholds, data-governance restrictions, infrastructure categories, and risk-based control matrix.

**Gate:** Every production workload has business and technical owners, department, cost center, approved provider/model, budget owner, thresholds, and effective dates.

### M22 — Budget Foundation

Create effective-dated and approved decompositions of the same $76,438.52 total by provider channel, application, department, cost center, environment, production/experiment, and direct-model/infrastructure view.

**Gate:** Every decomposition independently totals exactly $76,438.52; no view is added to another; shared pools have documented drivers.

### Architecture Review 1 — after M22

Run fresh-clone CI, dependency compatibility, tracked-artifact verification, duplication review, documentation reconciliation, and whole-repository architecture review before provider implementation.

### M23 — Amazon Bedrock Adapter

Build Bedrock usage and AWS CUR-style financial adapters, model/inference-profile/region mappings, token estimates, credits, adjustments, tags, provider-reported cost, and AWS billed cost.

**Gate:** Usage estimate, provider reporting, cloud billing, and invoice-style totals reconcile with explained differences while provider-specific fields remain available.

### M24 — Vertex AI/Gemini Adapter

Build Vertex usage and GCP detailed-billing adapters, service/SKU/model/region mappings, credits, labels, project allocation, token estimates, provider-reported cost, and GCP billed cost.

**Gate:** The same three-layer reconciliation and provider-field-retention standards used for M23 pass independently.

### M25 — Supporting Infrastructure and GPU Economics

Build direct model, retrieval, orchestration, observability, storage, network, and hosted-inference components. Calculate provisioned, active, and idle GPU hours, utilization, minimum-replica effect, unit cost, managed-API alternative, and break-even volume.

**Gate:** Infrastructure and GPU components reconcile to cloud billing; shared allocations conserve cost; direct and fully loaded cost remain separately reportable.

### M26 — Multi-Channel Reconciliation and Allocation

Apply allocation precedence: request application ID, API key, cloud account/project, endpoint, provider workspace, application map, shared driver, and unallocated fallback. Calculate direct, derived, shared, and unallocated coverage by channel and fully loaded scope.

**Gate:** Retries do not duplicate logical requests; allocation adds or removes no cost; unknown mappings remain unallocated; fully loaded cost equals its components.

### Architecture Review 2 — after M26

Repeat the release-candidate checks and confirm that provider adapters use shared contracts, runners, controls, and logging rather than copied deployment boilerplate.

### M27 — Driver-Based Budgeting and Forecasting

Build base and scenario forecasts from active users, requests, tokens, input/output ratio, model/provider mix, caching, batch, retries, adoption, launches, GPU demand, rate changes, and discounts. Calculate month-end projection, rolling forecasts, budget and forecast variance, MAPE, WAPE, bias, and driver bridges.

**Gate:** Outputs are reproducible, compared with a naive baseline, explainable, and not manually tuned. Generated annual actual remains below the budget through documented assumptions.

### M28 — Quality, Latency, and Reliability

Track quality score, evaluation evidence, task completion, groundedness, P50/P95 latency, errors, and timeouts. Every routing/substitution recommendation evaluates cost, quality, latency, reliability, security, regional restrictions, effort, and reversibility.

**Gate:** A cheaper alternative fails when any approved threshold fails.

### M29 — Anomalies and Financial Guardrails

Detect runaway requests/tokens, retry storms, unit-cost spikes, output/context spikes, cache/batch degradation, model-mix shifts, unapproved providers/models, GPU decline, idle endpoints, experiment overspend, billing delays, price changes, and allocation degradation. Simulate financial decisions without claiming provider-side enforcement.

**Gate:** Detection and simulated enforcement remain separate; every exception has an owner; ground-truth precision/recall is reported honestly.

### M30 — Optimization and Experiment Governance v2

Extend recommendations across caching, batch, retries, failures, context/output reduction, model routing, provider route, retrieval, logging, endpoints, GPUs, and managed-API alternatives. Preserve identified, eligible, approved, implemented, validation-pending, verified, realized, cost-avoidance, rejected, and expired states. Extend experiment budget, quality, latency, production approval, and retirement controls.

**Gate:** No savings total is predetermined; quality and latency affect approval; verified/realized values are labeled modeled; v1 controls continue passing.

### Architecture Review 3 — after M30

Perform full repository, clean-clone, metric-change, control-traceability, and documentation review before semantic/report expansion.

### M31 — Unit Economics and Provider Economics

Classify governed financial measures, illustrative operational measures, and prohibited business-value claims. Compare direct APIs, Bedrock, Vertex, discounts, commitments, hosted inference, concentration, break-even, and downside exposure.

**Gate:** Class A metrics reconcile; Class B visuals carry the required disclaimer; Class C claims are absent.

### M32 — Power BI Semantic Model v2

Extend the star schema and canonical measures for budget, forecast, fully loaded cost, quality, latency, anomalies, guardrails, infrastructure, GPU, and provider economics.

**Gate:** No fact-to-fact ambiguity; canonical measures reconcile to governed SQL; technical columns and formatting metadata are tracked.

### M33 — Power BI Management Reporting v2

Create only the pages, drill-through, bookmarks, and tooltips needed to support management decisions. Document audience, question, decision, measure, drill path, refresh dependency, and disclaimer for every visual.

**Gate:** Every decision is supported, repetitive visuals are removed, and report totals equal SQL.

### M34 — Excel and PowerPoint Decision Deliverables

Build governed budget/forecast, provider comparison, routing, hosted-inference, and experiment workbooks plus the quarterly AI FinOps review deck. No metric may be independently recalculated in PowerPoint.

**Gate:** Excel and PowerPoint trace to governed warehouse measures and display required disclaimers.

### Architecture Review 4 — after M34

Run the final pre-release clean-clone, dependency, artifact, metric synchronization, documentation, and recruiter-review gate.

### M35 — Final Enterprise Release

Complete documentation, runbooks, data/KPI dictionaries, methodology guides, walkthroughs, release notes, limitations, demo script, presentation, résumé bullets, and LinkedIn description.

**Gate:** All four primary provider channels reconcile; fully loaded cost and budgets reconcile; forecasting is reproducible; quality gates and anomaly evaluation work; artifacts agree; clean-clone CI passes; release is tagged.

## Publishable gate for every milestone

Every milestone must include implementation, tests, evidence, README update, capability-status update, release-note fragment, metric-change entry when applicable, and known-limitations update.

## Same-commit metric rule

Any change to published cost, requests, tokens, allocation, budget, forecast, savings, quality, latency, or dashboard measures must update all affected SQL/tests, README, screenshots, release notes, and metric-change evidence in the same pull request.

## Blocked-gate rule

Two consecutive gate failures require a documented decision record. Tier 1 financial controls cannot be waived for a completed release. Deferred work cannot be presented as implemented.

## Project boundary

Phase 2 may export a summarized monthly AI FinOps dataset to Project 1. Project 1 must not recreate AI token, pricing, retry, experiment, quality, or provider-reconciliation logic. Phase 2 must not recreate the full infrastructure FinOps platform.
