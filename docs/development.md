# Local development and testing

Go 1.27.0 is installed at `C:\Program Files\Go\bin\go.exe`. Docker Desktop was updated to 4.94.0 with Docker Engine 29.8.2 (Linux containers) on 10 October 2026. A newly opened terminal should pick up the installer PATH change; an existing terminal can invoke Go by its full path.

From the project root:

```powershell
go version
docker version
docker compose version
go test ./...
go test ./cmd/edge -run TestConcurrentColdBurst -count=10
```

If the current terminal has not refreshed PATH:

```powershell
& 'C:\Program Files\Go\bin\go.exe' test ./...
```

The project Dockerfiles use Go 1.21. To repeat that compatibility check:

```powershell
docker run --rm -v "${PWD}:/app" -w /app golang:1.21-alpine go test ./...
```

For race detection without installing a native Windows C compiler:

```powershell
docker run --rm -v "${PWD}:/app" -w /app golang:1.21-alpine sh -c 'apk add --no-cache gcc musl-dev && go test -race ./...'
```

The container downloads modules and compiler packages as needed and is removed after completion. Docker Desktop must be running; `docker desktop start` starts the installed engine. Docker access and module downloads may require approval when run from the Codex workspace sandbox.

To start the application stack when ready:

```powershell
docker compose up --build -d
```

Router: `http://localhost:8080`; control: `http://localhost:7000`; Grafana: `http://localhost:3000`; Prometheus: `http://localhost:9090`.

Setup checks already passed: native Windows Go 1.27.0 tests, Docker hello-world, Compose configuration validation, Go 1.21 container tests, Linux race tests, and 10 repetitions of the cold-burst regression. The burst regression compares 32 origin fetches without coordination with one fetch when coordination is enabled; it is not a deployed performance benchmark.

The Docker Desktop startup error involved inaccessible runtime socket reparse points (`dockerInference`, then `SecretsEngine`). The runtime directory was preserved as `C:\Users\jayni\AppData\Local\Docker\run.stale-20261010-152223`; Docker was updated from its official installer. Images and volumes were preserved; no factory reset was used. The engine and all 11 experimental-stack services subsequently ran successfully.

For the comparison stack, use `docker compose -f docker-compose.yml -f docker-compose.experiments.yml up --build -d`. Ports 8084 and 8085 expose round robin and adaptive routers. The experiments use 64 KiB of cached response bodies per edge and a synthetic 20 ms origin delay. Run `scripts/integration-check.mjs` and `scripts/compare-routing.mjs` with Node; they save their evidence under `docs/academic/results`.
