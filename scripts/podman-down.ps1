# Para Algorise. Sin argumentos conserva los datos; con -Purge no deja NINGUN rastro.
#   ./scripts/podman-down.ps1          -> para y elimina el pod (datos a salvo en el volumen)
#   ./scripts/podman-down.ps1 -Purge   -> borra pod + volumen de datos + imagenes
param([switch]$Purge)

podman pod exists algorise
if ($LASTEXITCODE -eq 0) {
    podman pod rm -f algorise | Out-Null
    Write-Host "Pod 'algorise' detenido y eliminado." -ForegroundColor Green
} else {
    Write-Host "El pod 'algorise' no estaba en marcha." -ForegroundColor DarkGray
}

if ($Purge) {
    podman volume exists algorise-data
    if ($LASTEXITCODE -eq 0) { podman volume rm algorise-data | Out-Null }
    try { podman image rm -f localhost/algorise-frontend:latest localhost/algorise-backend:latest | Out-Null } catch {}
    podman image prune -f | Out-Null
    Write-Host "PURGA COMPLETA: volumen e imagenes eliminados. Cero rastro." -ForegroundColor Yellow
} else {
    Write-Host "Datos conservados en el volumen 'algorise-data'. Usa -Purge para borrarlo todo." -ForegroundColor DarkGray
}
