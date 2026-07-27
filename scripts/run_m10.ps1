$ErrorActionPreference = "Stop"

python .\scripts\run_m10.py
python -m pytest
python -m ruff check .

Write-Host ""
Write-Host "M10 COMPLETE: telemetry reconciliation passed." -ForegroundColor Green
