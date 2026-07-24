# M4 Installation

Copy these folders into the root of the existing project:

- `config`
- `docs`
- `tests`

Allow Windows to merge the folders.

No existing file should be replaced except if Windows confirms an identical folder merge.

Then run:

```powershell
python -m pytest
python -m ruff check .
```

Expected result:

```text
35 passed
All checks passed!
```

The total is 19 existing tests plus 16 M4 tests.
