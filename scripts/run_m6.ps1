$ErrorActionPreference = "Stop"

python .\scripts\run_m6.py
python -m pytest
python -m ruff check .

Write-Host ""
Write-Host "M6 COMPLETE: BigQuery raw layer loaded and validated." -ForegroundColor Green
