# M16 Installation

Copy these folders into the existing project:

- `.github`
- `config`
- `docs`
- `scripts`
- `sql`
- `src`
- `tests`

Allow Windows to merge them.

Then run one command:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_m16.ps1
```

Expected ending:

```text
M16 AUTOMATED CONTROLS PASSED
18 controls passed
148 passed
All checks passed!
REPOSITORY CI PASSED
M16 COMPLETE: automated controls and repository CI passed.
```
