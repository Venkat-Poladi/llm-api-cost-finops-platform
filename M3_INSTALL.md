# M3 Installation

Copy these folders into the root of the existing project:

- `config`
- `docs`
- `evidence`
- `tests`

Allow Windows to merge folders and replace `config/table_contracts.yaml`.

Then run:

```powershell
python -m pytest
python -m ruff check .
```

Expected result:

```text
19 passed
All checks passed!
```

The total is 6 existing tests plus 13 M3 tests.
