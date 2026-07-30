# M14 Installation

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
powershell -ExecutionPolicy Bypass -File .\scripts\run_m14.ps1
```

Expected ending:

```text
M14 UNIT ECONOMICS PASSED
16 controls passed
128 passed
All checks passed!
M14 COMPLETE: unit economics passed.
```
