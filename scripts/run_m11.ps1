$ErrorActionPreference = "Stop"

python .\scripts\run_m11.py
python -m pytest
python -m ruff check .

Write-Host ""
Write-Host "M11 COMPLETE: token economics passed." -ForegroundColor Green
