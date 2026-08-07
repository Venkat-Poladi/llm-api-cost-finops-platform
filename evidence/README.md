# Evidence Package

The provider-shape examples in this folder are synthetic, redacted examples. They are not represented as actual user billing records.

## V1 release evidence

The immutable M20 evidence package is under [`releases/v1.0.0/`](releases/v1.0.0/):

- `generation_manifest.json` — deterministic source counts, totals, hashes, generator version, and seed.
- `repository_validation.txt` — baseline commit, clean/synchronized state, source-generation result, and repository-CI result.
- `powerbi_artifact_hashes.sha256` — hashes for the committed v1 PBIP, semantic support files, and four screenshots.

The related narrative evidence is under [`docs/releases/`](../docs/releases/).

## Safety rules

Replace or supplement provider examples only when permission exists to access real organization-level provider APIs.

Never commit:

- API keys or admin keys
- Cloud credentials
- Organization identifiers
- Unredacted project or workspace identifiers
- Prompt or response content containing private information
- Confidential invoices, contracts, client names, or customer information

The project does not require real provider access because its portfolio dataset is deliberately controlled and non-confidential.

## Phase 2 evidence

- `evidence/m21/m21_foundation_summary.json` records deterministic counts and configuration hashes for the M21 enterprise workload and provider foundation.
- M21 contains no new financial outputs and does not replace the frozen v1 release evidence.
