$ErrorActionPreference = "Stop"

python .\scripts\run_m17.py

Write-Host ""
Write-Host "M17 CLOUD LAYER COMPLETE." -ForegroundColor Green
Write-Host "Next: build the Power BI relationships and measures using the files in powerbi\semantic_model." -ForegroundColor Yellow
