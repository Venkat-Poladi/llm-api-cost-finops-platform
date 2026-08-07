# Phase 2 Known Limitations Register

These limitations apply unless a later milestone explicitly closes them with implementation, tests, and evidence.

| Limitation | Treatment |
|---|---|
| Controlled non-confidential data | Demonstrates methodology; does not represent actual company operations. |
| No production credentials in the repository | Provider and cloud access must use external secrets and authenticated environments. |
| Public CI does not execute billable BigQuery workloads | Static, formula, contract, artifact, and repository tests run publicly; authenticated cloud execution remains separate. |
| Provider contract assumptions are illustrative | Do not claim actual negotiated pricing or contractual terms without real evidence. |
| Supporting infrastructure is intentionally limited | Include only the components required to demonstrate fully loaded AI cost. |
| Hosted inference is one small endpoint | Do not generalize results to a large GPU fleet. |
| Guardrail enforcement is simulated unless implemented | Detection, recommendation, and provider-side enforcement must remain distinct. |
| Verified or realized savings are modeled | Never describe them as actual company savings. |
| Operational unit economics are illustrative | Required disclaimer must appear on Class B visuals. |
| No actual business ROI | Revenue, productivity, labor displacement, customer satisfaction, and profit claims are prohibited. |
| Single currency | USD only; no foreign-exchange logic. |
| No large-scale training | Training and fine-tuning economics remain excluded. |
| No Azure OpenAI | Azure belongs to a separate portfolio project. |
| No autonomous AI FinOps agent | The platform remains analytical and control-oriented. |
| No autonomous shutdown | Idle-endpoint shutdown may be modeled as a decision, not falsely claimed as live enforcement. |
| No confidential data | Do not add client names, customer data, proprietary contracts, or unredacted invoices. |

This register must be updated in the same pull request whenever a limitation is closed, narrowed, or newly discovered.
