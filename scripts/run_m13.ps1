$ErrorActionPreference = "Stop"

python .\scripts\run_m13.py
python -m pytest
python -m ruff check .

Write-Host ""
Write-Host "M13 COMPLETE: optimization and evaluation gate passed." -ForegroundColor Green
