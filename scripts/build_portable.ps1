# =====================================================================
#  ikao portable builder  (Windows PowerShell)
#  Usage:  powershell -ExecutionPolicy Bypass -File scripts\build_portable.ps1
#
#  Steps: 1) build frontend  2) install backend deps + pyinstaller
#         3) run PyInstaller  4) assemble release\ikao-1.0
#
#  IMPORTANT (encoding):
#  Windows PowerShell 5.1 decodes a .ps1 WITHOUT BOM using the system ANSI
#  code page (GBK on zh-CN), which turns any non-ASCII literal in this file
#  into mojibake. Therefore this script is kept 100% ASCII on purpose:
#  all generated file names are ASCII too (e.g. start-ikao.bat).
#  DO NOT paste raw non-ASCII characters into this file.
# =====================================================================

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot          # project root
Set-Location $Root

$Version = "1.0"
$ReleaseDir = Join-Path $Root "release\ikao-$Version"
$BatName = "start-ikao.bat"

function Step($n, $text) {
    Write-Host ""
    Write-Host "[$n/4] $text" -ForegroundColor Cyan
}

Write-Host "=======================================================" -ForegroundColor Green
Write-Host "  ikao portable package builder  (v$Version)" -ForegroundColor Green
Write-Host "  project: $Root" -ForegroundColor Green
Write-Host "=======================================================" -ForegroundColor Green

# ---------------------------------------------------------------- 1) frontend
Step 1 "Building frontend (web/dist)"
Push-Location (Join-Path $Root "web")
try {
    if (-not (Test-Path "node_modules")) {
        Write-Host "  node_modules not found, running npm install ..." -ForegroundColor Yellow
        npm install
        if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
    }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }
}
finally {
    Pop-Location
}
Write-Host "  frontend built: web/dist" -ForegroundColor Green

# ---------------------------------------------------------------- 2) backend deps
Step 2 "Installing backend dependencies + PyInstaller"
python -m pip install --upgrade pip | Out-Null
python -m pip install -r "server\requirements.txt" pyinstaller
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

# ---------------------------------------------------------------- 3) pyinstaller
Step 3 "Running PyInstaller (packaging/ikao.spec)"
python -m PyInstaller "packaging\ikao.spec" --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
Write-Host "  built: dist\ikao\ikao.exe" -ForegroundColor Green

# ---------------------------------------------------------------- 4) assemble
Step 4 "Assembling release\ikao-$Version"
if (Test-Path $ReleaseDir) { Remove-Item $ReleaseDir -Recurse -Force }
New-Item -ItemType Directory -Path $ReleaseDir | Out-Null
Copy-Item "dist\ikao\*" $ReleaseDir -Recurse -Force

# writable data dir (keep it when upgrading)
$DataDir = Join-Path $ReleaseDir "data"
New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
$Sample = Join-Path $Root "data\sample_questions.json"
if (Test-Path $Sample) { Copy-Item $Sample $DataDir -Force }

# double-click launcher (content is pure ASCII, so cmd never shows mojibake)
$LauncherBat = @"
@echo off
cd /d "%~dp0"
echo Starting ikao ... a browser window will open shortly.
start "" "ikao.exe"
exit
"@
Set-Content -Path (Join-Path $ReleaseDir $BatName) -Value $LauncherBat -Encoding ASCII

# ship all markdown docs from docs\ (incl. the installation guide)
$DocsDir = Join-Path $Root "docs"
if (Test-Path $DocsDir) {
    Get-ChildItem -Path $DocsDir -Filter "*.md" -File | Copy-Item -Destination $ReleaseDir -Force
}

# version marker
Set-Content -Path (Join-Path $ReleaseDir "VERSION.txt") -Value "ikao v$Version" -Encoding ASCII

$SizeMB = [math]::Round(((Get-ChildItem $ReleaseDir -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB), 1)

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Green
Write-Host "  DONE" -ForegroundColor Green
Write-Host "  package : $ReleaseDir" -ForegroundColor Green
Write-Host "  size    : $SizeMB MB" -ForegroundColor Green
Write-Host "  entry   : ikao.exe  (or the .bat launcher)" -ForegroundColor Green
Write-Host "=======================================================" -ForegroundColor Green
Write-Host "  Zip the folder above and send it to your teammate." -ForegroundColor Yellow
