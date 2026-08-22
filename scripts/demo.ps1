# demo.ps1 - End-to-end Mini CDN demonstration script in PowerShell

Write-Host "======================================================================" -ForegroundColor Blue
Write-Host "                    MINI CDN PROTOTYPE DEMO                           " -ForegroundColor Blue
Write-Host "======================================================================" -ForegroundColor Blue

# 1. Check containers
Write-Host "`n[1/6] Verifying all containers are healthy..." -ForegroundColor Yellow
if (Get-Command docker -ErrorAction SilentlyContinue) {
    docker compose ps
} else {
    Write-Host "Docker CLI not detected on PATH. Skipping container status check." -ForegroundColor DarkGray
}

# Helper function to get response with headers
function Invoke-CdnRequest {
    param([string]$Uri)
    try {
        $resp = Invoke-WebRequest -Uri $Uri -Method Get -UseBasicParsing -TimeoutSec 10
        return @{
            StatusCode = $resp.StatusCode
            CacheStatus = $resp.Headers["X-Cache"]
            EdgeNode = $resp.Headers["X-Edge-Node"]
            Headers = $resp.Headers
        }
    } catch {
        if ($_.Exception.Response) {
            $resp = $_.Exception.Response
            return @{
                StatusCode = [int]$resp.StatusCode
                CacheStatus = $resp.Headers["X-Cache"]
                EdgeNode = $resp.Headers["X-Edge-Node"]
                Headers = $resp.Headers
            }
        }
        throw $_
    }
}

# 2. Test Cache MISS
Write-Host "`n[2/6] Requesting logo.png (Expect: Cache MISS)..." -ForegroundColor Yellow
try {
    $res1 = Invoke-CdnRequest -Uri "http://localhost:8080/assets/logo.png"
    Write-Host "HTTP Status: $($res1.StatusCode)"
    Write-Host "X-Cache: $($res1.CacheStatus)"
    Write-Host "X-Edge-Node: $($res1.EdgeNode)"

    if ($res1.CacheStatus -eq "MISS") {
        Write-Host "✓ Success: Got Cache MISS as expected." -ForegroundColor Green
    } else {
        Write-Host "✗ Error: Did not get Cache MISS. (Got: $($res1.CacheStatus))" -ForegroundColor Red
    }
} catch {
    Write-Host "Request failed: $_" -ForegroundColor Red
}

# 3. Test Cache HIT
Write-Host "`n[3/6] Requesting logo.png again (Expect: Cache HIT)..." -ForegroundColor Yellow
$cachedNode = ""
try {
    $res2 = Invoke-CdnRequest -Uri "http://localhost:8080/assets/logo.png"
    Write-Host "HTTP Status: $($res2.StatusCode)"
    Write-Host "X-Cache: $($res2.CacheStatus)"
    Write-Host "X-Edge-Node: $($res2.EdgeNode)"

    if ($res2.CacheStatus -eq "HIT") {
        Write-Host "✓ Success: Got Cache HIT as expected." -ForegroundColor Green
    } else {
        Write-Host "✗ Error: Did not get Cache HIT. (Got: $($res2.CacheStatus))" -ForegroundColor Red
    }
    $cachedNode = $res2.EdgeNode
    Write-Host "Currently cached on edge node: $cachedNode" -ForegroundColor Blue
} catch {
    Write-Host "Request failed: $_" -ForegroundColor Red
}

# 4. Invalidate cache via Control Plane
Write-Host "`n[4/6] Purging /assets/logo.png via Control Plane..." -ForegroundColor Yellow
try {
    $purgeBody = @{ urls = @("/assets/logo.png") } | ConvertTo-Json
    $purgeRes = Invoke-RestMethod -Uri "http://localhost:7000/api/v1/purge" -Method Post -ContentType "application/json" -Body $purgeBody
    Write-Host "Control Plane response: $($purgeRes | ConvertTo-Json -Compress)"
} catch {
    Write-Host "Purge failed: $_" -ForegroundColor Red
}

# 5. Test Cache MISS after purge
Write-Host "`n[5/6] Requesting logo.png after purge (Expect: Cache MISS)..." -ForegroundColor Yellow
try {
    $res3 = Invoke-CdnRequest -Uri "http://localhost:8080/assets/logo.png"
    Write-Host "HTTP Status: $($res3.StatusCode)"
    Write-Host "X-Cache: $($res3.CacheStatus)"
    Write-Host "X-Edge-Node: $($res3.EdgeNode)"

    if ($res3.CacheStatus -eq "MISS") {
        Write-Host "✓ Success: Got Cache MISS after purge as expected." -ForegroundColor Green
    } else {
        Write-Host "✗ Error: Did not get Cache MISS after purge." -ForegroundColor Red
    }
} catch {
    Write-Host "Request failed: $_" -ForegroundColor Red
}

# 6. Test Failover Capability
Write-Host "`n[6/6] Demonstrating automated failover..." -ForegroundColor Yellow
if (Get-Command docker -ErrorAction SilentlyContinue) {
    if (-not $cachedNode) { $cachedNode = "edge-1" }
    Write-Host "Stopping container for serving node: $cachedNode..." -ForegroundColor Blue
    docker compose stop $cachedNode

    Write-Host "Waiting 2 seconds for router to detect..." -ForegroundColor Yellow
    Start-Sleep -Seconds 2

    Write-Host "Requesting logo.png again while $cachedNode is down..." -ForegroundColor Yellow
    try {
        $resFailover = Invoke-CdnRequest -Uri "http://localhost:8080/assets/logo.png"
        Write-Host "HTTP Status: $($resFailover.StatusCode)"
        Write-Host "X-Cache: $($resFailover.CacheStatus)"
        Write-Host "X-Edge-Node: $($resFailover.EdgeNode)"

        if ($resFailover.EdgeNode -and ($resFailover.EdgeNode -ne $cachedNode)) {
            Write-Host "✓ Success: Failover occurred! Request routed to healthy node: $($resFailover.EdgeNode)" -ForegroundColor Green
        } else {
            Write-Host "✗ Error: Failover failed or routed to same node." -ForegroundColor Red
        }
    } catch {
        Write-Host "Failover request failed: $_" -ForegroundColor Red
    }

    Write-Host "`nRestarting stopped node $cachedNode to restore cluster health..." -ForegroundColor Yellow
    docker compose start $cachedNode
    Write-Host "Restarted container $cachedNode." -ForegroundColor Green
} else {
    Write-Host "Docker CLI not detected. Skipping live container stop/start failover step." -ForegroundColor DarkGray
}

Write-Host "`n======================================================================" -ForegroundColor Green
Write-Host "                      DEMO COMPLETED                                  " -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
