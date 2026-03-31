param(
    [string]$Version = "dev-local"
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host 'Installing Python dependencies...'
uv sync

Write-Host 'Installing frontend dependencies...'
npm ci --prefix frontend

Write-Host 'Building frontend...'
npm run build --prefix frontend

Write-Host 'Building Windows bundle with PyInstaller...'
uv run --with pyinstaller pyinstaller packaging/windows/prism-llm-eval.spec --noconfirm

$archiveBaseName = "prism-llm-eval-$Version-windows-x86_64"
$archivePath = Join-Path $repoRoot "dist/$archiveBaseName.zip"
$hashPath = "$archivePath.sha256"

Write-Host "Creating portable ZIP: $archivePath"
Compress-Archive -Path dist/prism-llm-eval/* -DestinationPath $archivePath -Force

$hash = (Get-FileHash -Algorithm SHA256 $archivePath).Hash.ToLower()
"$hash  $([System.IO.Path]::GetFileName($archivePath))" | Set-Content -Path $hashPath -Encoding ascii

Write-Host 'Bundle created at dist/prism-llm-eval/'
Write-Host "Portable ZIP created at $archivePath"
Write-Host "SHA256 created at $hashPath"
