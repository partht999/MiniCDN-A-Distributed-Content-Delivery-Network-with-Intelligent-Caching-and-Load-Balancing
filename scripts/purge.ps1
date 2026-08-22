# purge.ps1 - Purge cache entries for a specific path
param (
    [Parameter(Mandatory=$true, Position=0, HelpMessage="Enter the path to purge (e.g. /assets/logo.png)")]
    [string]$PathToPurge
)

Write-Host "Purging asset: $PathToPurge" -ForegroundColor Cyan

$body = @{
    urls = @($PathToPurge)
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "http://localhost:7000/api/v1/purge" `
                                  -Method Post `
                                  -ContentType "application/json" `
                                  -Body $body
    Write-Host "Purge Response: $($response | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    Write-Host "Purge failed: $_" -ForegroundColor Red
}
