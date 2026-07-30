$ErrorActionPreference = "Stop"

python .\scripts\run_m15.py
python -m pytest
python -m ruff check .

Write-Host ""
Write-Host "M15 COMPLETE: experiment governance passed." -ForegroundColor Green
