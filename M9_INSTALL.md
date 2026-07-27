# M9 Installation

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
powershell -ExecutionPolicy Bypass -File .\scripts\run_m9.ps1
```

Expected ending:

```text
M9 DAILY USAGE ALLOCATION PASSED
16 controls passed
78 passed
All checks passed!
M9 COMPLETE: daily usage allocation passed.
```
