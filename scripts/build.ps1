# Yerel paketleme (Windows PowerShell).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
Write-Host "Bağımlılıklar yükleniyor..."
pip install -r requirements.txt -r build-requirements.txt
Write-Host "Paketleniyor..."
pyinstaller --noconfirm build.spec
Write-Host "Tamam. Çıktı: dist\BeyannameTransfer.exe"
