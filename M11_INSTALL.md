# M11 Installation

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
powershell -ExecutionPolicy Bypass -File .\scripts\run_m11.ps1
```

Expected ending:

```text
M11 TOKEN ECONOMICS PASSED
14 controls passed
98 passed
All checks passed!
M11 COMPLETE: token economics passed.
```
