# M21 — Enterprise Workload and Provider Foundation

## Objective

Establish the governed Phase 2 foundation before generating new usage, billing, budget, forecast, anomaly, or optimization outputs.

M21 defines what may be used, who owns it, what quality and latency it must meet, how provider-specific data is retained, and which controls block release or deployment.

## Implemented foundation

### Provider channels

Five effective-dated channels are defined in `config/v2_provider_channels.csv`:

1. OpenAI direct
2. Anthropic direct
3. Amazon Bedrock
4. Vertex AI/Gemini
5. Hosted open-source inference

OpenAI and Anthropic preserve the working v1 implementation. Bedrock, Vertex, and hosted inference are foundation contracts only until M23, M24, and M25 respectively.

### Workload inventory

`config/v2_workload_inventory.csv` defines:

- Eight production AI applications
- Four controlled experiments
- Four departments
- Six engineering or product teams
- Business, technical, and budget ownership
- Cost center and environment
- Approved provider route
- Deployment method
- Data sensitivity
- Review and effective dates

M21 assigns budget ownership but intentionally leaves budget amounts blank with status `PENDING_M22`. M22 owns the approved $76,438.52 decompositions.

### Approved routes

`config/v2_approved_routes.csv` creates one effective-dated route per workload. Existing v1 model identifiers are marked verified. Bedrock, Vertex, and hosted model identifiers are design approvals whose provider-native identifiers must be mapped in their implementation milestones.

### Quality, latency, and reliability thresholds

`config/v2_workload_thresholds.csv` defines one policy per workload containing:

- Quality metric and minimum score
- Latency metric and maximum threshold
- Minimum success rate
- Maximum error rate
- Maximum retry rate
- Effective dates

These thresholds exist before optimization so a cheaper route cannot later be approved merely because it costs less.

### Data governance

`config/v2_data_governance_policies.csv` defines internal, confidential, PII-sensitive, and restricted policies. The policies constrain region, environment, logging content, retention, and review requirements.

### Common provider contract

`config/v2_provider_contract.yaml` defines common usage, telemetry, and financial fields while preserving provider extensions for each channel.

Normalization must not discard Bedrock account/region/inference-profile fields, Vertex billing/SKU/label fields, direct-provider project or workspace fields, or hosted endpoint/GPU fields.

### Effective-dated rate-card contract

`config/v2_rate_card_contract.yaml` defines the common key, metadata, cost components, and controls for direct API, cloud-managed, provisioned-capacity, hosted endpoint, storage, and network rates.

No new provider price is implemented in M21. OpenAI and Anthropic rates remain governed by v1; Bedrock, Vertex, and hosted endpoint rates belong to M23–M25.

### Supporting-infrastructure categories

`config/v2_supporting_infrastructure_categories.csv` defines direct model, retrieval, orchestration, observability, storage, network, and hosted-inference components and their planned allocation drivers.

### Risk-based controls

`config/v2_risk_control_matrix.csv` defines:

- Nine Tier 1 financially critical controls that block release
- Eight Tier 2 operational controls that block deployment pending review
- Three Tier 3 reporting controls that create documented exceptions

The matrix defines control ownership and implementation milestone. It does not falsely claim that controls scheduled for later milestones already execute.

## Automated validation

Run:

```powershell
& .\.venv\Scripts\python.exe .\scripts\validate_m21_foundation.py
```

The validator checks:

- Five unique provider channels
- Eight production workloads and four experiments
- Four departments and six teams
- Complete ownership and governance metadata
- One effective-dated approved route per workload
- One quality/latency/reliability threshold per workload
- Valid governance-policy references
- Complete infrastructure categories
- Correct risk-tier failure actions
- Effective-dated rate-card requirements
- Provider-extension contracts for every channel

The deterministic evidence output is stored at `evidence/m21/m21_foundation_summary.json`.

## Gate result

M21 passes when the validator and full repository CI pass and all milestone artifacts are committed together.

No published v1 financial, request, token, allocation, savings, quality, or latency metric changes in M21.
