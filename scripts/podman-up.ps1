# Levanta Algorise en Podman con comandos nativos (no requiere podman-compose).
# Todo vive dentro de la VM de Podman (WSL): no instala nada en Windows.
#   Web:  http://localhost:5173      API/docs: http://localhost:8000/docs
#   Usuario por defecto: admin / admin   (modo paper, sin dinero real)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "==> Construyendo imagenes..." -ForegroundColor Cyan
podman build -t localhost/algorise-backend:latest  (Join-Path $root "backend")
if ($LASTEXITCODE -ne 0) { throw "Fallo construyendo el backend" }
podman build -t localhost/algorise-frontend:latest (Join-Path $root "frontend")
if ($LASTEXITCODE -ne 0) { throw "Fallo construyendo el frontend" }

# Volumen de datos (persiste entre reinicios; se borra con podman-down.ps1 -Purge).
podman volume exists algorise-data
if ($LASTEXITCODE -ne 0) { podman volume create algorise-data | Out-Null }

# Pod que publica los puertos al host (los contenedores comparten su red).
podman pod exists algorise
if ($LASTEXITCODE -ne 0) {
    podman pod create --name algorise -p 8000:8000 -p 5173:80 | Out-Null
}

Write-Host "==> Arrancando contenedores..." -ForegroundColor Cyan
# Si ya existian (de un arranque previo), los quitamos para reusar los nombres.
podman rm -f algorise-backend algorise-frontend 2>$null | Out-Null
# --rm: al pararlos se eliminan (sin restos). El volumen conserva los datos.
podman run -d --rm --pod algorise --name algorise-backend `
    -e DATABASE_URL=sqlite:////data/algorise.db `
    -e CORS_ORIGINS=* `
    -v algorise-data:/data `
    localhost/algorise-backend:latest | Out-Null

podman run -d --rm --pod algorise --name algorise-frontend `
    localhost/algorise-frontend:latest | Out-Null

Write-Host ""
Write-Host "Algorise EN MARCHA:" -ForegroundColor Green
Write-Host "  Web   ->  http://localhost:5173" -ForegroundColor Green
Write-Host "  API   ->  http://localhost:8000/docs" -ForegroundColor Green
Write-Host "  Login ->  admin / admin" -ForegroundColor Green
Write-Host ""
Write-Host "Parar:        ./scripts/podman-down.ps1" -ForegroundColor DarkGray
Write-Host "Borrar TODO:  ./scripts/podman-down.ps1 -Purge" -ForegroundColor DarkGray
