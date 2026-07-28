$ErrorActionPreference = "Stop"

python .\scripts\run_m12.py
python -m pytest
python -m ruff check .

Write-Host ""
Write-Host "M12 COMPLETE: application cost and chargeback passed." -ForegroundColor Green
