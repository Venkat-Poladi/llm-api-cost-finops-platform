$ErrorActionPreference = "Stop"

python .\scripts\run_m9.py
python -m pytest
python -m ruff check .

Write-Host ""
Write-Host "M9 COMPLETE: daily usage allocation passed." -ForegroundColor Green
