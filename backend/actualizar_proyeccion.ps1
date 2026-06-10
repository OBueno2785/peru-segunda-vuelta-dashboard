# Actualiza la proyección de la segunda vuelta y la publica en GitHub Pages.
# Pensado para correr en la máquina local (IP residencial; ONPE bloquea IPs de datacenter).
# Solo commitea si el scrape se completó SIN bloqueos (el scraper sale !=0 si quedó incompleto).
#
# Uso manual:   powershell -ExecutionPolicy Bypass -File backend\actualizar_proyeccion.ps1
# Programado:   ver "Tarea programada" más abajo.

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot          # raíz del repo
$backend = Join-Path $repo "backend"
$py = Join-Path $backend "venv\Scripts\python.exe"
$log = Join-Path $backend "actualizar_proyeccion.run.log"

function Log($m) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $m" | Tee-Object -FilePath $log -Append }

Set-Location $backend
Log "=== Inicio actualización proyección ==="

# 1. Descargar actas E/P (solo JSON). Si falla (bloqueo/incompleto), abortar sin tocar nada.
& $py scraper_actas.py --no-pdf
if ($LASTEXITCODE -ne 0) { Log "Scrape incompleto (exit $LASTEXITCODE). Abortado, sin commit."; exit 1 }

# 2. Refrescar el contabilizado al mismo momento del scrape.
& $py -c "import asyncio, refresher; print('refresh ok =', asyncio.run(refresher.fetch_fresh()))"

# 3. Regenerar la proyección (escribe frontend/public/data/proyeccion.json).
& $py proyeccion.py
if ($LASTEXITCODE -ne 0) { Log "proyeccion.py falló (exit $LASTEXITCODE). Abortado."; exit 1 }

# 4. Publicar si cambió.
Set-Location $repo
git add frontend/public/data/proyeccion.json
git diff --cached --quiet
if ($LASTEXITCODE -eq 0) { Log "Proyección sin cambios. Nada que publicar."; exit 0 }

git commit -m "chore(proyeccion): actualizar proyeccion ONPE"
git pull --rebase origin main
git push origin main
Log "Proyección publicada en GitHub Pages."
