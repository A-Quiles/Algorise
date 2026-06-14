# Arranca el frontend (PWA) de Algorise en http://localhost:5173
# Uso: pwsh ./scripts/start-frontend.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend"
Set-Location $frontend

if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Host "Instalando dependencias de Node..." -ForegroundColor Cyan
    npm install
}

Write-Host "Iniciando frontend en http://localhost:5173 (accesible en tu red local) ..." -ForegroundColor Green
npm run dev
