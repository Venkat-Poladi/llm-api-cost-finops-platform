# LLM API Cost FinOps Platform

A portfolio-grade FinOps platform for direct LLM API consumption across OpenAI and Anthropic.

The project independently generates provider usage, provider cost/invoice data, and request telemetry; reconciles estimated, reported, and invoiced cost; allocates imperfectly attributed usage; calculates token and request unit economics; governs experiments; identifies optimization opportunities; and presents the results in Power BI.

## Why this project exists

Traditional cloud FinOps does not fully explain direct LLM API economics. This project answers:

- How much are we spending on LLM APIs?
- Is cost growing faster than usage?
- Which applications, departments, and cost centers own the spend?
- How much spend is unallocated or low-confidence?
- What is the cost per request and successful response?
- Where are caching, batching, retries, failures, and model choice creating waste?
- Is experimentation spend controlled?

## Scope

Included in v1:

- OpenAI and Anthropic
- Text generation and embeddings
- Token usage and request telemetry
- Historical, effective-dated model pricing
- Estimated vs provider-reported vs invoiced cost reconciliation
- Imperfect attribution and visible unallocated cost
- Token economics, unit economics, optimization, and experiment governance
- BigQuery data model and Power BI reporting
- Automated financial and data-quality controls

Deferred:

- Vector database and RAG infrastructure cost
- GPU and provisioned-capacity economics
- Fine-tuning and training
- Multimodal workloads
- Product ROI and quality benchmarking
- Automated provider-side spending enforcement

## Architecture

```text
Provider Usage pipeline ───────┐
Provider Cost/Invoice pipeline ┼─> Monthly reconciliation fact
Request/Gateway telemetry ─────┤
Internal ownership maps ───────┘
                                      │
                                      ├─> Daily allocated usage fact
                                      ├─> Token and request economics
                                      ├─> Application chargeback/showback
                                      ├─> Optimization funnel
                                      ├─> Experiment governance
                                      └─> Power BI
```

## Technology

- Python: deterministic synthetic source generation and automated tests
- BigQuery SQL: raw, staging, facts, marts, and controls
- Power BI: semantic model and executive reporting
- GitHub Actions: automated validation
- Git: milestone branches, pull requests, and tagged releases

## Execution status

Current milestone: **M0 — Project Foundation**

See:

- `docs/milestone_plan.md`
- `docs/milestone_tracker.md`
- `docs/original_scope_v7_locked.md`
- `docs/execution_decision.md`

## Repository principle

The project is standalone and executable without Project 1. Integration with the Retail FinOps Platform is an optional final milestone, not a prerequisite.
