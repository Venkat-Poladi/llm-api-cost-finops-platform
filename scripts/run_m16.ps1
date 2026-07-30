$ErrorActionPreference = "Stop"

python .\scripts\run_m16.py
python .\scripts\run_repo_ci.py

Write-Host ""
Write-Host "M16 COMPLETE: automated controls and repository CI passed." -ForegroundColor Green
