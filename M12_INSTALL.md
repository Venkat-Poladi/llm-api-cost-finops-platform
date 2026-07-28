# M12 Installation

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
powershell -ExecutionPolicy Bypass -File .\scripts\run_m12.ps1
```

Expected ending:

```text
M12 APPLICATION COST AND CHARGEBACK PASSED
16 controls passed
108 passed
All checks passed!
M12 COMPLETE: application cost and chargeback passed.
```
