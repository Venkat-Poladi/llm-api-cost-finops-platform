# M7 Installation

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
powershell -ExecutionPolicy Bypass -File .\scripts\run_m7.ps1
```

Expected ending:

```text
M7 STAGING NORMALIZATION AND PRICING PASSED
58 passed
All checks passed!
M7 COMPLETE: staging, normalization, and pricing passed.
```
