# Capability Status

This is the authoritative high-level status document for the repository.

## Current release

| Item | Status |
|---|---|
| V1 implementation | Complete |
| M20 v1 evidence freeze | Complete |
| Release tag | `v1.0.0` |
| V1 branch | `main` |
| Phase 2 branch | `phase-2` |
| Phase 2 implementation | M21 complete; M22 next |

## Capability status

| Capability group | V1 | Phase 2 target |
|---|---|---|
| OpenAI direct | Complete | Common provider contract defined in M21; preserve v1 implementation |
| Anthropic direct | Complete | Common provider contract defined in M21; preserve v1 implementation |
| Amazon Bedrock | Not implemented | Channel, ownership, route, and contract foundation complete; adapter in M23 |
| Vertex AI/Gemini | Not implemented | Channel, ownership, route, and contract foundation complete; adapter in M24 |
| Supporting infrastructure | Not implemented | Categories and allocation-driver contract complete; implementation in M25–M26 |
| Hosted-inference/GPU economics | Not implemented | Channel and category foundation complete; economics in M25 |
| Reconciliation and allocation | Complete for v1 channels | Extend across all channels in M26 |
| Budgeting and forecasting | Not implemented | M22 and M27 |
| Quality and latency governance | Partial evaluation gate | Extend in M28 |
| Anomalies and guardrails | Not implemented | M29 |
| Optimization and experiments | Complete for v1 | Extend in M30 |
| Unit economics | Complete for v1 | Extend in M31 |
| Power BI | Four v1 pages complete | V2 semantic/report extension in M32–M33 |
| Excel and PowerPoint | Not implemented | M34 |
| Final enterprise release | Not implemented | M35 |

## Phase 2 foundation status

| M21 foundation element | Status |
|---|---|
| Provider-channel dimension | Complete |
| Eight production workloads | Complete |
| Four controlled experiments | Complete |
| Business, technical, and budget ownership | Complete |
| Effective-dated approved routes | Complete |
| Quality, latency, reliability, error, and retry thresholds | Complete |
| Data-governance policies | Complete |
| Common provider contract | Complete |
| Effective-dated rate-card contract | Complete |
| Supporting-infrastructure categories | Complete |
| Risk-based control matrix | Complete |
| New provider adapters or financial results | Not implemented until M23–M25 |
| Approved budget amounts | Not implemented until M22 |

## Status rule

A capability may be marked complete only when implementation, tests, evidence, README, capability status, release-note fragment, known limitations, and any affected metric-change entries are updated together.
