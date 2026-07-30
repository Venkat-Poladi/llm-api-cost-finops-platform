# M15 Installation

Copy these folders into the existing project:

- `config`
- `docs`
- `scripts`
- `sql`
- `src`
- `tests`

Allow Windows to merge them.

Then run one command:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_m15.ps1
```

Expected ending:

```text
M15 EXPERIMENT GOVERNANCE PASSED
18 controls passed
138 passed
All checks passed!
M15 COMPLETE: experiment governance passed.
```

Governance exception rows are allowed when they are explicitly classified and explained. The BigQuery controls fail only when the governance logic or reconciliation is incorrect.
