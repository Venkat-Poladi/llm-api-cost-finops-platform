# M17 Installation

Copy these folders into the existing project:

- `config`
- `docs`
- `powerbi`
- `scripts`
- `sql`
- `src`
- `tests`

Allow Windows to merge them.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_m17.ps1
```

Expected cloud ending:

```text
M17 POWER BI SEMANTIC LAYER PASSED
created_object_count: 10
controls_passed: 12
REPOSITORY CI PASSED
M17 CLOUD LAYER COMPLETE.
```

Then follow:

`docs/m17_power_bi_semantic_model.md`
