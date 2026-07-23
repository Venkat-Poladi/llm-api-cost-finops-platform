\
$ErrorActionPreference = "Stop"

& .\.venv\Scripts\Activate.ps1
python -m ruff check .
python -m pytest --cov=src --cov-report=term-missing
