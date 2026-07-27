# M10 Installation

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
powershell -ExecutionPolicy Bypass -File .\scripts\run_m10.ps1
```

Expected ending:

```text
M10 TELEMETRY RECONCILIATION PASSED
14 controls passed
88 passed
All checks passed!
M10 COMPLETE: telemetry reconciliation passed.
```
