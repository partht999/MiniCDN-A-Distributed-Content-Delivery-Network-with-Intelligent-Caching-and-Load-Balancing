$ErrorActionPreference = 'Stop'
$engine = docker info --format '{{json .}}' | ConvertFrom-Json
$versions = docker version --format '{{json .}}' | ConvertFrom-Json
$services = @(docker compose -f docker-compose.yml -f docker-compose.experiments.yml ps --format json | ForEach-Object { $_ | ConvertFrom-Json } | ForEach-Object { [ordered]@{service=$_.Service; state=$_.State; image=$_.Image} })
$record = [ordered]@{
    capturedAt = (Get-Date).ToUniversalTime().ToString('o')
    nativeGo = (& 'C:/Program Files/Go/bin/go.exe' version)
    dockerDesktop = $versions.Server.Platform.Name
    dockerEngine = $versions.Server.Version
    compose = (docker compose version --short)
    dockerCPUs = $engine.NCPU
    dockerMemoryBytes = $engine.MemTotal
    kernel = $engine.KernelVersion
    architecture = $engine.Architecture
    gitBaseRevision = (git rev-parse HEAD)
    workingTreeContainsUncommittedImplementation = $true
    services = $services
    caveat = 'Recorded after trials; one local Docker host, not a regional CDN deployment. Exact tested working-tree sources must be retained with the results.'
}
$record | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath docs/academic/results/environment.json -Encoding utf8
Write-Output 'Saved experiment environment metadata'
