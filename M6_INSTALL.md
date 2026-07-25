# M6 Installation

Copy these folders into the root of the existing local project:

- `config`
- `docs`
- `scripts`
- `sql`
- `src`
- `tests`

Allow Windows to merge the folders.

Then run only:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_m6.ps1
```

Expected ending:

```text
M6 BIGQUERY RAW LAYER PASSED
50 passed
All checks passed!
M6 COMPLETE: BigQuery raw layer loaded and validated.
```
