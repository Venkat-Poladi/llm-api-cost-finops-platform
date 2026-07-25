# M5 Installation

Copy these folders into the root of the existing local project:

- `src`
- `scripts`
- `tests`
- `docs`

Allow Windows to merge the folders.

Do not copy the outer `m5-source-generation` folder into the project.

## Run M5

From the activated virtual environment at the project root:

```powershell
python .\scripts\generate_sources.py --overwrite
python .\scripts\validate_generated_sources.py
python -m pytest
python -m ruff check .
```

Expected validation result:

```text
SOURCE GENERATION PASSED
SOURCE VALIDATION PASSED
43 passed
All checks passed!
```

The exact row counts are produced by the locked seed and installed dependency versions. They must remain within these acceptance ranges:

- provider usage: 4,000–9,000 rows;
- request telemetry: 150,000–450,000 attempt rows.

No Git commands are required.
