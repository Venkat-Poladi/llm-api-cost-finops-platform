$ErrorActionPreference = "Stop"

python .\scripts\run_m8.py
python -m pytest
python -m ruff check .

Write-Host ""
Write-Host "M8 COMPLETE: monthly cost reconciliation passed." -ForegroundColor Green
