$ErrorActionPreference = "Stop"

python .\scripts\run_m7.py
python -m pytest
python -m ruff check .

Write-Host ""
Write-Host "M7 COMPLETE: staging, normalization, and pricing passed." -ForegroundColor Green
