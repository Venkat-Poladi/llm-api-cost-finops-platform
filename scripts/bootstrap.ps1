\
$ErrorActionPreference = "Stop"

Write-Host "Creating Python virtual environment..." -ForegroundColor Cyan
python -m venv .venv

Write-Host "Activating virtual environment..." -ForegroundColor Cyan
& .\.venv\Scripts\Activate.ps1

Write-Host "Upgrading pip..." -ForegroundColor Cyan
python -m pip install --upgrade pip

Write-Host "Installing project dependencies..." -ForegroundColor Cyan
python -m pip install -r requirements.in

Write-Host "Freezing exact installed versions..." -ForegroundColor Cyan
python -m pip freeze | Set-Content requirements.txt

Write-Host "Running initial tests..." -ForegroundColor Cyan
python -m pytest

Write-Host "Environment setup completed." -ForegroundColor Green
