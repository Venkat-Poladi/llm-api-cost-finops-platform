# Milestone Plan

Each milestone must satisfy four rules before moving forward:

1. Acceptance criteria pass.
2. Automated tests pass.
3. Documentation matches the implemented result.
4. The milestone is committed and pushed to GitHub.

---

## M0 — Project Foundation

**Goal:** Create a clean standalone repository and lock the execution plan.

**Deliverables**
- Repository scaffold
- README
- Original locked scope preserved
- Standalone execution decision
- Milestone plan and tracker
- Git ignore rules
- Initial CI workflow
- Initial project configuration

**Acceptance**
- Folder structure exists
- `pytest` can discover the test directory
- Git repository has a clean initial commit
- README accurately describes only planned or completed work

---

## M1 — Development Environment

**Goal:** Create a reproducible local Python and BigQuery development environment.

**Deliverables**
- Python virtual environment
- Installed and frozen dependencies
- Google Cloud authentication instructions
- BigQuery project and region configuration
- Environment validation script

**Acceptance**
- Python version is recorded
- Dependencies install from the committed lock file
- BigQuery authentication succeeds
- A test query runs against the configured project

---

## M2 — Architecture and Data Contracts

**Goal:** Convert the locked scope into executable schemas and grain contracts.

**Deliverables**
- Architecture document
- Source-to-target mapping
- Data dictionary
- Grain definition for every object
- Dataset naming convention
- Control matrix mapping all 18 controls to implementation files

**Acceptance**
- Every table has a declared grain and primary business key
- Daily and monthly facts are explicitly separated
- No ambiguous or duplicated rate-card dimensions remain

---

## M3 — Provider Evidence and Pricing Model

**Goal:** Validate provider token semantics and design historical pricing inputs.

**Deliverables**
- Redacted evidence files where permissions allow
- Provider field validation document
- `dim_ai_model_map` seed
- `dim_ai_model_rate` seed
- Native-to-normalized service-tier mapping

**Acceptance**
- Every synthetic usage model resolves to one model snapshot
- Every snapshot resolves to one effective rate row
- No overlapping effective windows
- Exact observed fields and assumptions are documented

---

## M4 — Synthetic Source Design

**Goal:** Define deterministic source-generation rules before writing the generator.

**Deliverables**
- Scenario matrix
- Provider/model/application/project/key population design
- Usage distributions
- Retry and failure rules
- Cache and reasoning-token rules
- Cost divergence and invoice adjustment rules
- Attribution imperfection rules
- Experiment scenarios

**Acceptance**
- 18-month design is complete
- Independent source disagreement is documented
- Known anomalies and exceptions are defined before generation
- No output value is manually targeted

---

## M5 — Source Generation

**Goal:** Generate three independent source datasets.

**Deliverables**
- `raw_ai_provider_usage`
- `raw_ai_provider_cost`
- `fct_ai_request_telemetry`
- Attribution bridge source
- Experiment-control and decision-event source
- Generator metadata and run summary

**Acceptance**
- Seed reproduces identical output
- Source grains are unique
- Reasoning and cache constraints pass
- Usage and cost sources legitimately diverge
- No cost is stored in raw provider usage

---

## M6 — BigQuery Raw Layer

**Goal:** Load generated sources into typed BigQuery raw tables.

**Deliverables**
- Dataset creation SQL
- Raw table DDL
- Load scripts
- Row-count and schema controls
- Pipeline run log

**Acceptance**
- Every source loads without manual edits
- Row counts match generated files
- Raw values remain source-native
- Reload is idempotent or safely replaceable

---

## M7 — Staging, Normalization, and Historical Pricing

**Goal:** Normalize provider differences and derive usage cost estimates.

**Deliverables**
- Model mapping joins
- Effective-dated rate joins
- Provider cache normalization
- Normalized processing tiers
- Staged token and cost calculations
- Attribution-window resolution

**Acceptance**
- Every eligible usage row resolves to exactly one map and one rate
- Historical months use historical rates
- Zero denominators return `NULL` for ratio metrics
- Non-USD records fail validation

---

## M8 — Monthly Cost Reconciliation

**Goal:** Build `fct_ai_cost_reconciliation`.

**Deliverables**
- Monthly reconciliation fact
- Usage-to-reported variance
- Reported-to-invoice variance
- Line-type-aware applicability
- Variance reason codes
- Exception status

**Acceptance**
- Non-usage lines carry no usage estimate
- Every exception has a reason code
- No unexplained reconciliation failure
- Fact grain is unique

---

## M9 — Daily Usage Allocation

**Goal:** Build `fct_ai_usage_daily` without duplicating shared-key usage.

**Deliverables**
- Effective-dated attribution join
- Source and allocated measures
- Unallocated residual
- Allocation confidence and method
- Shared-key percentage allocation
- Ownership-change and restatement handling

**Acceptance**
- Allocated plus unallocated equals source
- Allocation percentage never exceeds 100%
- Shared keys split rather than duplicate usage
- Unallocated usage remains visible

---

## M10 — Telemetry Reconciliation

**Goal:** Prove request telemetry and provider usage describe the same consumption.

**Deliverables**
- Token coverage
- Request-count variance
- Token-count variance
- Untraceable usage cost
- Retry-cost measures
- Final-request success metrics

**Acceptance**
- Coverage is calculated by date, provider, project, and model
- Attempt and logical-request counts are not mixed
- Retry cost uses non-final attempts
- Coverage gaps are visible and explained

---

## M11 — Token Economics

**Goal:** Build reliable token-level cost diagnostics.

**Deliverables**
- `mart_ai_token_economics`
- Normalized cache-read share
- Reasoning overhead
- Cost per input/output/total token
- Batch adoption and estimated savings
- Failed-request estimated cost

**Acceptance**
- Token math reconciles
- Reasoning tokens remain a subset of output tokens
- Provider cache semantics remain distinct in raw data
- Every metric labels its financial basis

---

## M12 — Application Cost and Chargeback

**Goal:** Attribute financial cost to business owners while preserving uncertainty.

**Deliverables**
- `mart_ai_application_cost`
- Application, department, and cost-center views
- Allocation confidence
- Unallocated bucket
- Invoice-basis chargeback measures

**Acceptance**
- Application totals reconcile to source financial totals
- Low-confidence and unallocated cost are visible
- No direct monthly-invoice-to-daily-usage fan-out occurs

---

## M13 — Optimization and Evaluation Gate

**Goal:** Build financially honest optimization recommendations.

**Deliverables**
- `mart_ai_optimization`
- Caching recommendations
- Batch-migration recommendations
- Retry/failure waste recommendations
- Model-right-sizing recommendations
- Identified/Approved/Implemented/Realized funnel
- Quality, latency, and security gate fields

**Acceptance**
- Net savings are used
- Funnel hierarchy holds
- Model swaps remain potential savings until gates pass
- Overlapping recommendations are not double-counted

---

## M14 — Unit Economics

**Goal:** Build request-level operational unit economics.

**Deliverables**
- `mart_ai_unit_economics`
- Cost per request
- Cost per successful response
- Average tokens per request
- Cost of retries
- Cost of failed attempts

**Acceptance**
- Metrics reproduce from telemetry
- Final status is evaluated at the logical-request level
- Cost per request is not mislabeled as cost per task

---

## M15 — Experiment Governance

**Goal:** Govern experiment spend on an allocated invoiced-cost basis.

**Deliverables**
- `mart_ai_experiments`
- Limit-period-aware consumption
- Warning and hard-stop reporting
- Eligible usage-line allocation
- Decision history
- Current-status derivation

**Acceptance**
- Day, month, and lifetime limits use correct windows
- Only eligible usage invoice lines are allocated to experiments
- Decision history chains chronologically
- Spend reconciles to eligible invoice cost

---

## M16 — Automated Control Suite and CI

**Goal:** Implement the locked 18-test control set in SQL/Python and run it automatically.

**Deliverables**
- Grain tests
- Effective-window tests
- Allocation tests
- Reconciliation tests
- Currency tests
- Telemetry tests
- Power BI reconciliation test design
- GitHub Actions workflow

**Acceptance**
- All executable controls pass in CI
- Intentional misses are represented as approved exceptions
- A failed control blocks merge

---

## M17 — Power BI Semantic Model

**Goal:** Build a clean star schema and canonical measures.

**Deliverables**
- Dimensions
- Fact relationships
- Measure table
- Display folders
- Formatting and sorting
- Hidden technical columns
- BigQuery-to-Power BI reconciliation page

**Acceptance**
- One-to-many single-direction relationships
- No fact-to-fact spiderweb
- Canonical measures are reused
- Totals match BigQuery

---

## M18 — Power BI Reporting

**Goal:** Build an executive-quality portfolio report.

**Recommended pages**
1. Executive Overview
2. Cost Growth and Reconciliation
3. Token Economics and Waste
4. Application Ownership and Allocation
5. Optimization Funnel
6. Unit Economics
7. Experiment Governance
8. Data Quality and Controls

**Acceptance**
- Every visual labels its cost basis
- Titles state the decision answered
- Unallocated and exceptions are visible
- Filters and totals reconcile
- Screenshots are ready for README

---

## M19 — Documentation and Portfolio Release

**Goal:** Make the repository independently understandable and interview-ready.

**Deliverables**
- Final README
- Architecture diagram
- Data dictionary
- Control evidence
- Screenshots
- Known limitations
- Interview walkthrough
- Tagged GitHub release

**Acceptance**
- README matches implemented results
- No fabricated business impact claims
- Reproduction steps work from a clean clone
- Repository is public and professionally presented

---

## M20 — Freeze and Release v1

**Goal:** Freeze the completed OpenAI and Anthropic implementation before Phase 2 changes providers, tables, metrics, and reporting.

**Deliverables**
- Corrected milestone tracker
- Immutable v1 metric baseline
- V1 capability-status document
- Reconciliation and Power BI evidence manifest
- Repository-validation evidence
- Metric-change log
- Phase 2 build plan and known-limitations register
- `v1.0.0` release tag
- `phase-2` development branch

**Acceptance**
- README, tracker, backlog, and capability status agree
- Source generation and full repository CI pass
- Required Power BI artifacts and screenshots are tracked
- Baseline implementation commit is recorded
- Local `main` and `origin/main` are synchronized
- V1 release is tagged before Phase 2 implementation begins

---

## Phase 2 Continuation

Milestones M21 through M35 are governed by [`v2_build_plan.md`](v2_build_plan.md). The optional cross-project retail integration remains a future integration boundary rather than a v1 milestone.
