# Arranca el backend de Algorise (API + bot) en http://localhost:8000
# Uso: pwsh ./scripts/start-backend.ps1   (o ejecútalo desde PowerShell)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
Set-Location $backend

# Crea el entorno virtual la primera vez.
if (-not (Test-Path (Join-Path $backend ".venv"))) {
    Write-Host "Creando entorno virtual..." -ForegroundColor Cyan
    python -m venv .venv
}

$py = Join-Path $backend ".venv\Scripts\python.exe"

Write-Host "Instalando/actualizando dependencias..." -ForegroundColor Cyan
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt

# Copia .env si no existe.
if (-not (Test-Path (Join-Path $backend ".env"))) {
    Copy-Item ".env.example" ".env"
    Write-Host "Creado backend/.env desde el ejemplo." -ForegroundColor Yellow
}

Write-Host "Iniciando API en http://0.0.0.0:8000 ..." -ForegroundColor Green
& $py -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
