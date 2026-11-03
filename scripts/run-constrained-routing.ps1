$ErrorActionPreference = 'Stop'

$composeFiles = @('-f', 'docker-compose.yml', '-f', 'docker-compose.experiments.yml')
$env:WORKLOADS = 'zipf,uniform'
$env:POLICIES = 'consistent_hash,round_robin,adaptive'
$env:SLACKS = '0,2,8,1000'
$env:REQUESTS = '3000'
$env:WARMUP_REQUESTS = '256'
$env:REPETITIONS = '10'
$env:SEED = '2100260'
$env:CACHE_BYTES = '65536'
$env:ORIGIN_DELAY_MS = '20'
$env:ZIPF_EXPONENT = '1.1'
$env:EDGE_MAX_CONCURRENT_REQUESTS = '4'
$stamp = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH-mm-ss-fffZ')

$services = @('edge-1', 'edge-2', 'edge-3')
& docker compose @composeFiles up -d --build --no-deps --force-recreate @services
if ($LASTEXITCODE -ne 0) {
    throw "Could not recreate edge services with the concurrency limit; exit $LASTEXITCODE"
}

foreach ($concurrency in @(16, 64, 128)) {
    $env:CONCURRENCY = [string]$concurrency
    $env:OUTPUT_PREFIX = "routing-constrained-$stamp-c$concurrency"
    $env:EXPERIMENT_LABEL = $env:OUTPUT_PREFIX
    Write-Output "Starting constrained sweep: concurrency=$concurrency prefix=$($env:OUTPUT_PREFIX)"
    node .\scripts\compare-routing.mjs
    if ($LASTEXITCODE -ne 0) {
        throw "Constrained sweep failed at concurrency $concurrency; exit $LASTEXITCODE"
    }
    $resultPath = Join-Path '.\docs\academic\results' "$($env:OUTPUT_PREFIX).json"
    if (-not (Test-Path -LiteralPath $resultPath)) {
        throw "Constrained sweep did not produce $resultPath"
    }
    $result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
    if ($result.rows.Count -ne 120) {
        throw "Expected 120 trials at concurrency $concurrency, got $($result.rows.Count)"
    }
    $errors = ($result.rows | Measure-Object -Property errors -Sum).Sum
    Write-Output "result=$resultPath trials=$($result.rows.Count) errors=$errors"
}
