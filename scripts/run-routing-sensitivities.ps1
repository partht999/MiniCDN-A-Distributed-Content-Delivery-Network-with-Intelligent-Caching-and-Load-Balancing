$ErrorActionPreference = 'Stop'
$culture = [System.Globalization.CultureInfo]::InvariantCulture

$composeFiles = @('-f', 'docker-compose.yml', '-f', 'docker-compose.experiments.yml')
$parameters = @()
foreach ($kib in @(16, 32, 64, 128, 256)) {
    $parameters += [pscustomobject]@{
        Name = "cache-$kib-KiB"
        CacheBytes = $kib * 1024
        OriginDelayMs = 20
        ZipfExponent = 1.1
    }
}
foreach ($delay in @(5, 20, 100)) {
    $parameters += [pscustomobject]@{
        Name = "origin-$delay-ms"
        CacheBytes = 65536
        OriginDelayMs = $delay
        ZipfExponent = 1.1
    }
}
foreach ($exponent in @(0.8, 1.1, 1.4)) {
    $parameters += [pscustomobject]@{
        Name = "zipf-$($exponent.ToString($culture).Replace('.', '-'))"
        CacheBytes = 65536
        OriginDelayMs = 20
        ZipfExponent = $exponent
    }
}

$env:WORKLOADS = 'zipf'
$env:POLICIES = 'consistent_hash,round_robin,adaptive'
$env:SLACKS = '2'
$env:REQUESTS = '3000'
$env:CONCURRENCY = '16'
$env:REPETITIONS = '10'
$env:WARMUP_REQUESTS = '256'
$env:SEED = '2100260'
$env:EDGE_MAX_CONCURRENT_REQUESTS = '0'
$outputs = @()

foreach ($parameter in $parameters) {
    $env:CACHE_BYTES = [string]$parameter.CacheBytes
    $env:ORIGIN_DELAY_MS = $parameter.OriginDelayMs.ToString($culture)
    $env:ZIPF_EXPONENT = $parameter.ZipfExponent.ToString($culture)
    $services = @('origin', 'edge-1', 'edge-2', 'edge-3')
    & docker compose @composeFiles up -d --no-deps --force-recreate @services
    if ($LASTEXITCODE -ne 0) {
        throw "Compose reconfiguration failed for $($parameter.Name), exit $LASTEXITCODE"
    }

    $stamp = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH-mm-ss-fffZ')
    $env:OUTPUT_PREFIX = "routing-sensitivity-$stamp-$($parameter.Name)"
    $env:EXPERIMENT_LABEL = $env:OUTPUT_PREFIX
    $logPath = Join-Path $env:TEMP "$($env:OUTPUT_PREFIX).log"
    node .\scripts\compare-routing.mjs *> $logPath
    $exitCode = $LASTEXITCODE
    Write-Output "condition=$($parameter.Name) exit=$exitCode"
    if (Test-Path -LiteralPath $logPath) {
        Get-Content -LiteralPath $logPath -Tail 2
    }
    if ($exitCode -ne 0) {
        throw "Sweep failed for $($parameter.Name), exit $exitCode. Log: $logPath"
    }
    $resultPath = Join-Path '.\docs\academic\results' "$($env:OUTPUT_PREFIX).json"
    if (-not (Test-Path -LiteralPath $resultPath)) {
        throw "Sensitivity sweep did not produce $resultPath"
    }
    $result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
    if ($result.rows.Count -ne 30) {
        throw "Expected 30 trials for $($parameter.Name), got $($result.rows.Count)"
    }
    $errors = ($result.rows | Measure-Object -Property errors -Sum).Sum
    Write-Output "result=$resultPath trials=$($result.rows.Count) errors=$errors"
    $outputs += $resultPath
    Remove-Item -LiteralPath $logPath
}

Write-Output "completed-sensitivity-results=$($outputs -join ';')"
