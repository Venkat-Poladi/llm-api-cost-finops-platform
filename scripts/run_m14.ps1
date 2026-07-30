$ErrorActionPreference = "Stop"

python .\scripts\run_m14.py
python -m pytest
python -m ruff check .

Write-Host ""
Write-Host "M14 COMPLETE: unit economics passed." -ForegroundColor Green
