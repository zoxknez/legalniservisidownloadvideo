# One-shot dev setup (Windows)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $Root "..")

Write-Host "==> Python venv"
if (-not (Test-Path ".venv")) {
  python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -r requirements.txt
pip install -e ".[dev]"

Write-Host "==> Frontend"
Set-Location frontend
if (-not (Test-Path "node_modules")) {
  npm ci
} else {
  npm install
}
npm run build
Set-Location ..

Write-Host ""
Write-Host "Gotovo. Pokrenite: python run.py"
Write-Host "Razvoj UI: cd frontend && npm run dev  (backend na :8000)"
