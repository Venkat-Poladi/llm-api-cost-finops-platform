$ErrorActionPreference = "Stop"

Write-Host "Generating deterministic source datasets..." -ForegroundColor Cyan
python .\scripts\generate_sources.py --overwrite

Write-Host "Validating generated source datasets..." -ForegroundColor Cyan
python .\scripts\validate_generated_sources.py

Write-Host "Running the complete automated test suite..." -ForegroundColor Cyan
python -m pytest

Write-Host "Running Python quality checks..." -ForegroundColor Cyan
python -m ruff check .

Write-Host "M5 SOURCE GENERATION PASSED" -ForegroundColor Green
