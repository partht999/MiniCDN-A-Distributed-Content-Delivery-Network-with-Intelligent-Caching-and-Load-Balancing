# Work Report

## Task 0 — Housekeeping and current-work commits

**Status: complete for existing artifacts.** The result folder contains large
raw request exports: the slack-sweep request CSV is 132,727,666 bytes, the
router-local baseline request CSV is 38,942,773 bytes, the instrumented
baseline request CSV is 3,627,586 bytes, and its JSON duplicate is
10,346,510 bytes. The CSV exports total about 1.23 million per-request rows.
The largest single file is approximately 126.6 MiB.

**Storage decision:** use Git LFS for request CSV exports matching
`docs/academic/results/*requests*.csv` and generated request JSON exports
matching `docs/academic/results/routing-requests-*.json`; keep trial summaries, analysis JSON/CSV,
scripts, and figures as normal Git files. This retains all local source files
and avoids placing the bulky row-level logs in normal Git blobs. No data was
deleted or compressed, and the source files remain unchanged in the worktree.
Git LFS 3.7.1 created local LFS objects and the existing GitHub remote has an
LFS endpoint, but this environment reports `AccessUpload=none`; LFS uploads
and pushes were not attempted. A fresh clone needs Git LFS and successful
access to fetch the raw exports.

Current-work commits created:

| Commit | Scope |
| --- | --- |
| `bdb9f55` | Router owner headers, router-local modes, Compose variants, and request/sweep harness |
| `45c584c` | Reproduction and analysis scripts, dated result tables, LFS-backed request exports, and vector analysis figures |
| `0024267` | Markdown and IEEEtran paper drafts, bibliography, compiled PDF, and academic design/research notes |
| Pending | This report's update and subsequent task records |

The retained 10 October inputs were not staged or modified. The existing
`routing-sweep-2026-10-25T19-23-50-602Z.partial.json` currently describes a
**complete** 320-trial resumed sweep, not the earlier aborted run. The
separately described aborted manifest has not yet been located; it must not be
reconstructed from guessed request data.

### Commands and outcomes

| Command/action | Exit | Summary |
| --- | ---: | --- |
| `git status --short`; recent and author commit logs | 0 | Confirmed the preexisting worktree changes and `feat:`/`docs:` message convention. |
| PowerShell file-size listing of `docs\academic\results` and `figures` | 0 | Recorded request export sizes above; PDFs/SVGs and analysis tables remain small. |
| `git lfs version`; `git lfs env`; `git remote -v` | 0 | Git LFS 3.7.1 available; GitHub remote present; LFS access upload not authenticated. |
| `git lfs track "docs/academic/results/*requests*"` | 0 | Initial LFS rule; it also matched the retained JSONL source until corrected. |
| `git lfs untrack "docs/academic/results/*requests*"` and `git lfs track "docs/academic/results/*requests*.csv" "docs/academic/results/routing-requests-*.json"` | 0 | Restricted LFS rules to generated CSV/JSON request exports; retained `routing-requests.jsonl` remains a normal unchanged file. |
| `git lfs ls-files` | 0 | Verified four request exports have local LFS object IDs. |
| `git commit -m "feat: add routing sweep baselines and request instrumentation"` | 0 | Created `bdb9f55`. Its body contains a literal `\n\n` before the co-author text, so Git does not parse that text as a trailer; it was not amended. |
| `git commit -m "analysis: add reproducible routing results and figures"` | 0 | Created `45c584c`; analysis and results grouped together. |
| `git commit -m "docs: add routing research paper drafts"` | 0 | Created `0024267`; paper and reference package committed. |

## Task 1 — Validator fix and tests

**Status: complete and committed.** `cmd/origin/main.go` evaluates
`If-Modified-Since` only when `If-None-Match` is absent. The regression test
invokes the real `fileHandler` and checks all three requested cases:
mismatching ETag plus future modification date -> 200; matching ETag -> 304;
and `If-Modified-Since` alone -> 304.

Docker Desktop was installed but its daemon was initially stopped. Starting
the service directly was denied; launching Docker Desktop made `docker info`
responsive. The full Go suite then passed:

```text
	mini-cdn/cmd/control		coverage: 0.0% of statements
ok  	mini-cdn/cmd/edge	0.070s	coverage: 48.7% of statements
ok  	mini-cdn/cmd/origin	0.021s	coverage: 51.4% of statements
ok  	mini-cdn/cmd/router	0.022s	coverage: 40.0% of statements
ok  	mini-cdn/pkg/cache	0.053s	coverage: 84.6% of statements
ok  	mini-cdn/pkg/hash	0.010s	coverage: 95.6% of statements
total:					(statements)			46.1%
```

Total coverage is **46.1%**, compared with the prior retained figure of 52.8%.
No coverage profile was retained in the worktree.
After the router baseline tests were added, the full suite was run again and
passed with **46.9%** total statement coverage; this is the latest coverage
result for the current uncommitted code.

### Commands and outcomes

| Command | Exit | Summary |
| --- | ---: | --- |
| `docker run --rm -v "${PWD}:/src" -w /src golang:1.22 go test ./... -count=1 -coverprofile=coverage.out` | 1 | Docker daemon unavailable at first; Go tests did not start. |
| `Start-Service com.docker.service` | 1 | Permission denied opening Docker service. |
| Launch Docker Desktop; `docker info --format '{{.ServerVersion}}'` | 0 | Docker server responded with version `29.4.3`. |
| `docker run --rm -v "${PWD}:/src" -w /src golang:1.22 go test ./... -count=1 -coverprofile=coverage.out` | 0 | All packages passed; profile appeared as `coverage` in the mounted worktree. |
| `docker run --rm -v "${PWD}:/src" -w /src golang:1.22 go tool cover -func=coverage.out` | 1 | Profile not found under that name (`too many arguments`). |
| `docker run --rm -v "${PWD}:/src" -w /src golang:1.22 go tool cover -func=coverage` | 0 | Reported total statement coverage 46.1%. |
| `docker run --rm -v "${PWD}:/src" -w /src golang:1.22 go test ./... -count=1 -coverprofile=/src/coverage.out` | 0 | All packages passed with the same package coverage. |
| `docker run --rm -v "${PWD}:/src" -w /src golang:1.22 go tool cover -func=/src/coverage.out` | 1 | Profile still appeared as `coverage`, not `coverage.out`. |
| `docker run --rm -v "${PWD}:/src" -w /src golang:1.22 sh -c 'ls -la coverage*; head -n 2 coverage.out 2>/dev/null; head -n 2 coverage 2>/dev/null'` | 0 | Confirmed generated profile name was `coverage`. |
| `git diff --cached --check` | 0 | No whitespace errors in staged changes. |
| `git commit -m "origin: give If-None-Match precedence over If-Modified-Since (RFC 9110 13.1.2)" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"` | 0 | Created commit `f9c2bd3`; only origin handler and regression test included. |

The Go test command was run in a Docker container from the repository root.
These handler tests do not require Redis or network sockets.

## Task 2 — Reproduce retained results

**Status: complete.** Added `scripts/reproduce-routing-results.mjs`. It reads
the retained 10 October comparison JSON and request JSONL without modifying
them, validates the expected HIT rates and Zipf origin-attempt means, derives
distinct-key floors and excess origin attempts for each of the 36 trials, and
writes dated JSON, CSV and Markdown tables.

Reproduction checks passed: Zipf HIT is CH 80.34%, RR 65.49%, adaptive 76.69%;
Zipf origin attempts are 151, 265, 179; uniform HIT is 60.89%, 21.09%, 48.44%.
Mean distinct keys are Zipf 151.00, changing-hot 176.33, uniform 242.67 and
cold-burst 1.00. These are generated from
`docs/academic/results/routing-reproduction-2026-10-25.json` and its
per-trial CSV; the source retained JSON and JSONL hashes remained unchanged:

- `routing-comparison.json`: `D07493C1E7C6432BAC5AB471F7223887584519C0792AFBA0C49E286253053CBB`
- `routing-requests.jsonl`: `08FA07023CF13B8F51713BEC7FBDB50155B8E2BBF70E1933BE8F4A36B98A4AE8`

### Commands and outcomes

| Command | Exit | Summary |
| --- | ---: | --- |
| `node .\scripts\reproduce-routing-results.mjs` | 0 | `status: PASS`; parsed 36 trials; all nine supplied HIT/origin checks and four distinct-key mean checks passed; wrote the three dated outputs. |
| `Get-FileHash` on retained `routing-comparison.json` and `routing-requests.jsonl` (before and after) | 0 | SHA-256 hashes identical; retained dataset untouched. |
| `git diff --check` | 0 | No whitespace errors. |

## Task 3 — Per-request instrumentation

**Status: complete for the instrumented 3-repetition baseline.** The router
now returns the healthy-ring hash owner in `X-Hash-Owner`; its existing
`X-Edge-Node` identifies the serving edge. A router regression test verifies
that a failed owner with successful fallback still reports the original owner
and actual serving edge. The harness records trial ID, key, serving edge,
hash-owner edge, spill flag, cache status, latency, HTTP status and errors for
every request. It writes dated CSV/JSON outputs and does not overwrite the
retained 10 October files.

The 27,648-request instrumented baseline contains zero HTTP/body-validation
errors and no missing required instrumentation fields. Adaptive is configured
with slack 2. The table below gives pooled request-level nearest-rank P50/P95
in milliseconds, split by adaptive HIT/MISS and spill status, from
`routing-spill-latency-2026-10-25.csv`. Counts pool the three 768-request
repetitions per workload/policy; these observations are not independent
trial-level confidence intervals.

| Workload | Cache | Spilled n | Spilled P50/P95 (ms) | Non-spilled n | Non-spilled P50/P95 (ms) |
| --- | --- | ---: | ---: | ---: | ---: |
| uniform | MISS | 254 | 54.018 / 84.509 | 947 | 54.809 / 82.875 |
| uniform | HIT | 18 | 12.181 / 45.110 | 1,085 | 9.633 / 26.843 |
| zipf | MISS | 152 | 54.075 / 77.805 | 426 | 56.651 / 75.996 |
| zipf | HIT | 158 | 10.896 / 22.290 | 1,568 | 11.424 / 24.531 |
| changing_hot | MISS | 193 | 55.040 / 81.444 | 507 | 57.119 / 83.862 |
| changing_hot | HIT | 143 | 11.001 / 33.929 | 1,461 | 10.996 / 28.602 |
| cold_burst | MISS | 6 | 42.741 / 48.453 | 3 | 32.929 / 33.244 |
| cold_burst | HIT | 992 | 13.039 / 30.835 | 1,303 | 13.319 / 28.400 |

This baseline does **not** support a general claim that spilled requests
explain adaptive's higher P95 by landing on cold edges: spill-MISS P95 is
higher in uniform and cold-burst, lower in Zipf and changing-hot. Several
spilled groups are small, especially cold-burst misses. The longer, repeated
slack sweep is still needed before drawing a stronger conclusion.

### Commands and outcomes

| Command | Exit | Summary |
| --- | ---: | --- |
| `docker run --rm -v "${PWD}:/src" -w /src golang:1.22 go test ./... -count=1` | 0 | All Go packages passed after adding owner reporting and the fallback assertion. |
| `docker compose -f docker-compose.yml -f docker-compose.experiments.yml up -d --build` | 0 | Built and started Redis, origin, control, three edges, and three routers. |
| Node health/request probe on ports 8080, 8084, 8085 | 0 | Each returned serving and owner headers. Probe path was not seeded yet and returned HTTP 404; harness later seeded it and checked all actual benchmark responses. |
| `node .\scripts\compare-routing.mjs` | 0 | Ran all 36 baseline trials; detailed stdout was captured by the tool; dated result outputs written. |
| Node validation of `routing-requests-2026-10-25.json` | 0 | 27,648 requests, 0 errors, 0 malformed rows; 8,036 spilled and 19,612 non-spilled requests. |
| `git diff --check` | 0 | No whitespace errors. |

## Task 4 — Slack sweep

**Status: complete.** Adaptive slack is configurable, reported in router
health, and available through six Compose services. The harness runs 10
repetitions, 3,000 measured requests and 256 warm-up requests per trial,
concurrency 16, deterministic `seed + run` traces, 256 1-KiB objects, 64-KiB
body capacity per edge, and 20-ms origin delay. An acknowledged cache purge
separates warm-up from measured requests.

The resumed sweep contains 320 completed trials and 960,000 measured requests.
There was one warm-up retry. One condition,
`run-8-uniform-adaptive-slack-1000`, recorded 19 request errors; the error
count is retained in the data and report. The cause is not established.

Authoritative outputs:
`routing-sweep-2026-10-25T19-23-50-602Z.json`, `.csv`,
`-requests.csv`, `-spill-latency.csv`, and `.partial.json`. The JSON contains
the per-trial results and configuration metadata.

## Task 5 — Router-local baselines

**Status: complete.** Added and tested `least_loaded_router_local` and
`bounded_load_router_local`. The latter uses router-local in-flight counts
with capacity factor 2; neither policy shares load state between routers.
This implementation is a request-routing heuristic, not the Mirrokni et al.
bounded-load consistent-hashing algorithm.

The common harness completed 80 baseline trials / 240,000 measured requests
with zero request errors. Outputs:
`routing-sweep-2026-10-26T04-11-47-711Z.json`, `.csv`,
`-requests.csv`, `-spill-latency.csv`, and `.partial.json`.

## Task 6 — Optional sensitivity sweeps

**Status: not run.** Per-edge cache size (16, 32, 64, 128, 256 KiB), origin
delay (5, 20, 100 ms), and Zipf exponent (0.8, 1.1, 1.4) remain unmeasured.
No values for these conditions are asserted in the manuscript.

## Task 7 — Analysis and figures

**Status: complete.** Added `scripts/analyze-routing-sweep.py`. It reads both
trial JSON files and request CSV exports and generated trial summaries, spill
summaries, Markdown, JSON, CSV, and four vector figure pairs (PDF/SVG) under
`docs/academic/results/`. The generated prefix is
`routing-analysis-2026-10-26`.

The current analysis uses two-sided 95% Student t-intervals over independent
trial values for HIT ratio, origin attempts, distinct keys/floor, excess
attempts, and request CV. P50/P95/P99 and error-count means use deterministic
10,000-resample percentile bootstrap intervals (seed 3102026); request-level
latency is first reduced to per-trial percentiles. This replaced the earlier
latency t-interval output, whose P95 lower endpoint was negative for the
error-bearing uniform/slack-1000 condition. Regenerated bootstrap P95
endpoints are nonnegative; that condition's P95 mean is 176.2 ms, interval
[62.4, 384.9] ms, with 19 errors.

The analysis reports 400 trial rows, 40 condition groups, 873 per-trial spill
groups, and 90 spill-summary groups. The two request exports contain 1,200,000
rows, all required instrumentation fields, and 19 error rows.

Generated outputs include:

- `routing-analysis-2026-10-26.md` and `.json`
- `routing-analysis-2026-10-26-summary.csv`
- `routing-analysis-2026-10-26-spill-trials.csv`
- `routing-analysis-2026-10-26-spill-summary.csv`
- `figures/routing-analysis-2026-10-26-{pareto,hit-ratio,p95,spilled-latency}.{svg,pdf}`

The spill result is mixed, not universally adverse: at adaptive slack 2,
spilled MISS P95 exceeds non-spilled MISS P95 for cold burst (39.0 vs.
35.0 ms), but is lower for changing hot (91.0 vs. 99.7 ms), uniform (92.0
vs. 93.1 ms), and Zipf (126.5 vs. 128.7 ms).

## Task 8 — Paper and citation work

**Status: manuscript files created; final submission steps remain.**
`docs/academic/paper-draft.md` contains the Markdown manuscript, and
`docs/academic/ieee/paper.tex` plus `references.bib` provide an IEEEtran
two-column version using the generated PDF figures. Both drafts cite only
file-backed MiniCDN measurements and disclose the single-host, closed-loop,
synthetic, router-local, and error-bearing limitations.

Related-work claims are scoped to five collected research papers plus RFC
9110. Bibliographic records were checked against Crossref DOI metadata;
primary-source content was retrieved from the MIT author copy, arXiv, AAAI,
Google Research publication page, UCSD author copy, and RFC Editor. ACM and
SIAM publisher DOI pages returned 403 during this pass; their source PDFs
were already recorded in `docs/academic/papers/sources-manifest.json`. The
research survey still has only five research papers, below the 12-paper
institutional template target in `docs/academic/submission-plan.md`.

The author/affiliation block in LaTeX is intentionally a placeholder; it must
be completed by the authors. The requested cache-size, origin-delay, and
Zipf-exponent sensitivity runs are also still outstanding.

### Commands and outcomes since the prior report

| Command/action | Exit | Summary |
| --- | ---: | --- |
| `docker run --rm -v "${PWD}:/src" -w /src python:3.13-slim sh -c 'pip install --quiet matplotlib && python scripts/analyze-routing-sweep.py docs/academic/results/routing-sweep-2026-10-25T19-23-50-602Z.json docs/academic/results/routing-sweep-2026-10-26T04-11-47-711Z.json docs/academic/results/routing-sweep-2026-10-25T19-23-50-602Z-requests.csv docs/academic/results/routing-sweep-2026-10-26T04-11-47-711Z-requests.csv'` | 0 | Regenerated all analysis tables and four PDF/SVG figure pairs with bootstrap latency/error intervals. |
| Initial inline `python -c` validation command | 1 | PowerShell embedded-newline quoting caused a Python syntax error; it did not edit data. |
| Piped Python validation in `python:3.13-slim` Docker | 0 | 40 trial groups; no negative P95 lower endpoints; 19 total request errors; 1,200,000 request rows; required fields present; eight vector files nonempty. |
| Primary-source and DOI metadata retrieval | mixed | MIT author PDF, arXiv full text, AAAI PDF, Google Research page, UCSD author PDF, RFC Editor, and Crossref DOI metadata retrieved; ACM/SIAM publisher DOI pages returned 403. |
| `docker run --rm ghcr.io/tectonic-typesetting/tectonic:latest --version` | 125 | Registry denied access to the initially tried image. |
| `docker search tectonic --limit 10` | 0 | Found public lightweight Tectonic images. |
| `docker run --rm rekka/tectonic --version` | 127 | Image has an entrypoint; Docker tried to execute `--version` as the program. |
| `docker run --rm --entrypoint tectonic rekka/tectonic --version` | 0 | Tectonic 0.1.12-dev available. |
| `docker run --rm -v "${PWD}:/work" -w /work --entrypoint tectonic rekka/tectonic --keep-logs --keep-intermediates docs/academic/ieee/paper.tex` | 0 | First compile produced `paper.pdf`; the initial overfull line was revised. |
| Same Tectonic compile command after the line-break fix | 0 | Final IEEEtran PDF compiled with bibliography and all four PDF figures; no overfull boxes or unresolved citations. Tectonic emitted non-blocking font-substitution and underfull-box warnings. |
| Initial inline `python -c` PDF inspection | 1 | PowerShell quoting split the Python code; no repository files were changed. |
| Piped `pypdf` inspection in Docker | 0 | Produced a four-page PDF; text extraction showed font-encoding omissions, so bibliography and image checks were verified from the TeX `.bbl` and `.log` instead. |
| Piped final PDF/build-log validation in Docker | 0 | Four pages, six bibliography entries, four imported PDF figures, zero overfull boxes; log has font-substitution warnings only. |
| `docker run --rm -v "${PWD}:/src" -w /src golang:1.22 sh -c 'go test ./... -count=1 -coverprofile=/tmp/coverage.out && go tool cover -func=/tmp/coverage.out \| tail -n 1'` | 0 | Full current suite passed; 46.9% total statement coverage. |
| `git diff --check` | 0 | Passed; Git reported only existing LF-to-CRLF normalization warnings for modified Go source files. |

## Remaining work and TODOs

- **Paper completion:** fill in author affiliations/contact details and obtain
  author review; expand the literature survey to at least 12 research papers
  if required by the institutional template.
- **LaTeX build:** IEEEtran source compiled successfully with bibliography and
  vector PDF figures. Tectonic's font-substitution warnings remain; review the
  final PDF visually and compile with the target venue's TeX toolchain.
- **Optional experiments:** run the cache-size, origin-delay, and Zipf-exponent
  sensitivity sweeps; investigate the cause of the 19 uniform/slack-1000
  errors.
- **Submission checks:** verify the final target venue template, final
  bibliography and every source citation after author edits.
- **Validator coverage:** initial validator-fix suite coverage was 46.1%;
  latest full suite after router-baseline tests passed with 46.9%. The
  committed validator change remains `f9c2bd3`.
