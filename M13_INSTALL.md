# M13 Installation

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
powershell -ExecutionPolicy Bypass -File .\scripts\run_m13.ps1
```

Expected ending:

```text
M13 OPTIMIZATION AND EVALUATION GATE PASSED
16 controls passed
118 passed
All checks passed!
M13 COMPLETE: optimization and evaluation gate passed.
```
