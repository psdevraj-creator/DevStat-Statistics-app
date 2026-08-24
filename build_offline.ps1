# DevStat offline desktop build (Windows).
# 1) Bundle the Python analysis engine with PyInstaller -> dist/DevStatEngine/DevStatEngine.exe
# 2) Build the Electron app pointing at that engine -> frontend/release/
# Run from the repo root:  powershell -ExecutionPolicy Bypass -File build_offline.ps1
$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"

Write-Host "==> Building backend static (frontend npm build)" -ForegroundColor Cyan
Push-Location $frontend
npm run build
Pop-Location

Write-Host "==> Bundling offline engine with PyInstaller" -ForegroundColor Cyan
Push-Location $backend
# Ensure pyinstaller is present.
python -m PyInstaller --version *> $null
if (-not $?) { python -m pip install pyinstaller }
python -m PyInstaller devstat_engine.spec --noconfirm
if (-not $?) { throw "PyInstaller build failed." }
$engineExe = Join-Path $backend "dist\DevStatEngine\DevStatEngine.exe"
if (-not (Test-Path $engineExe)) { throw "Engine not found at $engineExe" }
Pop-Location

Write-Host "==> Building Electron app (engine: $engineExe)" -ForegroundColor Cyan
Push-Location $frontend
$env:DEVSTAT_ENGINE_EXE = $engineExe
$env:DEVSTAT_API_URL = "https://devstat-statistics-app-991466352708.europe-west1.run.app"
npm run desktop:build
Pop-Location

Write-Host "==> DONE. Installer in frontend/release/." -ForegroundColor Green
