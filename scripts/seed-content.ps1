# seed-content.ps1 - Ensures default files exist in sample-content directory

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$ContentDir = Join-Path $RootDir "sample-content"
$AssetsDir = Join-Path $ContentDir "assets"

if (-not (Test-Path $AssetsDir)) {
    New-Item -ItemType Directory -Path $AssetsDir -Force | Out-Null
}

$IndexPath = Join-Path $ContentDir "index.html"
if (-not (Test-Path $IndexPath)) {
    Write-Host "Creating default index.html..."
    @"
<!DOCTYPE html>
<html>
<head><title>Mini CDN Default</title></head>
<body><h1>Mini CDN Default</h1></body>
</html>
"@ | Set-Content -Path $IndexPath -Encoding utf8
}

$AppJsPath = Join-Path $AssetsDir "app.js"
if (-not (Test-Path $AppJsPath)) {
    Write-Host "Creating default app.js..."
    'console.log("Default script loaded");' | Set-Content -Path $AppJsPath -Encoding utf8
}

$LogoPngPath = Join-Path $AssetsDir "logo.png"
if (-not (Test-Path $LogoPngPath)) {
    Write-Host "Creating dummy logo.png..."
    "DUMMY PNG DATA" | Set-Content -Path $LogoPngPath -Encoding utf8
}

Write-Host "Sample content directories and files seeded successfully." -ForegroundColor Green
