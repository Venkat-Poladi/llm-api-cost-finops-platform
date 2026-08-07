# M21 Release Note — Enterprise Workload and Provider Foundation

## Added

- Five-channel provider dimension
- Eight-production-workload and four-experiment inventory
- Business, technical, budget, department, team, and cost-center ownership
- Effective-dated approved provider/model routes
- Quality, latency, reliability, and retry thresholds
- Data-governance policies
- Common provider usage and financial contract
- Effective-dated rate-card contract
- Fully loaded cost component categories
- Risk-based control matrix
- Deterministic M21 foundation validator and evidence

## Preserved

- V1 OpenAI and Anthropic source, pricing, reconciliation, allocation, unit-economics, optimization, experiment, semantic-model, and reporting behavior
- Frozen v1 metrics and evidence

## Metric impact

None. M21 creates governance foundations only. Approved budget amounts begin in M22; Bedrock, Vertex, hosted-inference, and new financial results are not yet implemented.

## Known limitations

- Bedrock provider-native model and billing mappings begin in M23.
- Vertex provider-native model and billing mappings begin in M24.
- Hosted endpoint and GPU economics begin in M25.
- M21 route approvals marked `APPROVED_FOR_DESIGN` are not evidence of deployed provider integrations.
