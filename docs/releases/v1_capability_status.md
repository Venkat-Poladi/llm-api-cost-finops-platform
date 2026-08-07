# V1 Capability Status

## Release position

Version 1 is a completed OpenAI and Anthropic direct-API FinOps implementation. M20 freezes the implementation before Phase 2 begins.

| Capability | V1 status | Primary evidence |
|---|---|---|
| Provider usage, cost, and invoice ingestion | Complete | `docs/m6_bigquery_raw_layer.md` |
| Effective-dated model and tier pricing | Complete | `docs/m7_staging_normalization_pricing.md` |
| Three-layer financial reconciliation | Complete | `docs/m8_monthly_cost_reconciliation.md` |
| Daily allocation and visible unallocated cost | Complete | `docs/m9_daily_usage_allocation.md` |
| Request telemetry and retry reconciliation | Complete | `docs/m10_telemetry_reconciliation.md` |
| Token economics | Complete | `docs/m11_token_economics.md` |
| Application showback and chargeback | Complete | `docs/m12_application_cost_chargeback.md` |
| Optimization evaluation gates | Complete | `docs/m13_optimization_evaluation_gate.md` |
| Governed unit economics | Complete | `docs/m14_unit_economics.md` |
| Experiment financial governance | Complete | `docs/m15_experiment_governance.md` |
| Eighteen end-to-end controls and CI | Complete | `docs/m16_automated_controls_ci.md` |
| Shared guarded BigQuery deployment runner | Complete | `src/llm_finops/bigquery/deployment_runner.py` |
| Identifier validation and failure logging | Complete | `src/llm_finops/bigquery/identifiers.py`, `pipeline_logging.py` |
| Power BI semantic model | Complete | `docs/m17_power_bi_semantic_model.md`, `powerbi/` |
| Four-page management report | Complete | `powerbi/screenshots/` |
| Clean-repository validation | Complete | `evidence/releases/v1.0.0/repository_validation.txt` |

## V1 limitations

Version 1 does not include Bedrock, Vertex AI/Gemini, supporting infrastructure, GPU economics, budgeting, forecasting, anomaly case management, simulated financial guardrails, Excel workbooks, or executive PowerPoint. Those items are Phase 2 work and must not be represented as completed in v1.

V1 does not claim production provider-side enforcement, actual business ROI, or realized company savings.
