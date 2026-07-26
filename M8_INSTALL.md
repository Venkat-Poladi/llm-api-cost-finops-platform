# M8 Installation

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
powershell -ExecutionPolicy Bypass -File .\scripts\run_m8.ps1
```

Expected ending:

```text
M8 MONTHLY COST RECONCILIATION PASSED
12 controls passed
68 passed
All checks passed!
M8 COMPLETE: monthly cost reconciliation passed.
```
