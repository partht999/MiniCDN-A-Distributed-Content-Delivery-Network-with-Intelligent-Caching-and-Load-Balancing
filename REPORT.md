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
| `882ed5a` | Task 0 report and corrected LFS selectors |

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

Related work now covers twelve peer-reviewed research/survey papers, RFC 9110,
and the official HAProxy configuration manual. Existing DOI metadata and
primary-source checks are recorded in
`docs/academic/papers/sources-manifest.json`. Crossref confirmed the metadata
for Vakali and Pallis, “Content Delivery Networks: Status and Trends”
(10.1109/MIC.2003.1250586), and Chen, Katz, and Kubiatowicz, “Dynamic Replica
Placement for Scalable Content Delivery” (10.1007/3-540-45748-8_29). The
official HAProxy 3.0 manual identified version 3.0.30-2, dated 2026-10-14,
and documents `hash-balance-factor`; Vimeo's suggested deployment write-up
was not verified and is not cited.

The author/affiliation block in LaTeX remains a placeholder. The authors must
fill in names (Jaynish Thakar, Anshul Warade, and Parth Thakkar), each
author's affiliation(s) and email address, and the guide attribution for
Dr. Sudhir N. Dhage.

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

- The user-described aborted 494-error manifest is still absent and cannot be
  reconstructed. Its per-request details and cause remain unverified.
- The required follow-up Task 2 same-session baseline sweep stopped at 68/200
  trials with 1,563 request errors. Its incomplete manifest and request log
  are retained; see the incident entry below. Do not use this partial run for
  baseline comparisons.
- Primary-sweep paired analysis, capacity check, spill-rate/regression output,
  paper edits, and a fresh IEEE PDF have now been generated from completed
  same-session data only. This does not replace the missing interleaved
  router-local baselines.
- The constrained-service experiment and cache-size/origin-delay/Zipf
  sensitivity sweeps remain unrun. The baseline comparisons from the separate
  Compose session remain excluded from primary claims.
- Final bibliography/build checks and page-layout review are being recorded
  below; no venue-specific source bundle or blind-submission copy has been
  prepared because no target venue has been selected.
- The requested logical commits were not created; the working tree still has
  uncommitted implementation, paper, script, and result files. Do not treat
  this worktree as a submission-ready snapshot.
- The authors must still supply affiliations and email addresses for Jaynish
  Thakar, Anshul Warade, and Parth Thakkar, and the guide attribution for
  Dr. Sudhir N. Dhage.
- The author block intentionally remains a placeholder per the study
  instructions. A blind-submission version will require venue-specific
  anonymization and removal of identifying source paths.
- IEEE 2026 venue calls checked here are past; confirm the next call's scope,
  page limit, double-blind rules, AI-use policy, and deadline before
  submission.
- The prior committed validator fix remains `f9c2bd3`; do not include a
  coverage number in the paper.

## Follow-up Task 1 — Failures and instability

**Status: partially complete; blocked on the missing aborted-run artifact.
Tasks 2–9 were not started, in accordance with the stop-on-failure rule.**

The results directory contains only the three listed `.partial.json` files,
all describing completed sweeps (the earlier two contain 320 and 80 trials;
the new replay contains 10). No original manifest for the reported aborted
trial 287/320 was found in the results folder or tracked history. It has not
been recreated or overwritten. Consequently, its 494 individual failed
requests, statuses, messages, timestamps, and surrounding logs cannot be
reported without inventing data.

For the available original 19-error trial,
`run-8-uniform-adaptive-slack-1000`, the request export provides index, key,
HTTP status and a generic error string, but no timestamps or response-body
text. Each 502 row has
`status=502, bodyLength=47, servingEdge=null, hashOwnerEdge=null`; each 503
row has `status=503, bodyLength=44, servingEdge=null, hashOwnerEdge=null`.
The exact response body for each request is not retained.

| Trial ID | Index | Key | Status | Stored error |
| --- | ---: | ---: | ---: | --- |
| `run-8-uniform-adaptive-slack-1000` | 468 | 53 | 502 | status=502; bodyLength=47; servingEdge/hashOwnerEdge null |
| same | 1061 | 18 | 502 | status=502; bodyLength=47; servingEdge/hashOwnerEdge null |
| same | 1068 | 156 | 502 | status=502; bodyLength=47; servingEdge/hashOwnerEdge null |
| same | 1107 | 199 | 503 | status=503; bodyLength=44; servingEdge/hashOwnerEdge null |
| same | 1108 | 136 | 503 | status=503; bodyLength=44; servingEdge/hashOwnerEdge null |
| same | 1109 | 131 | 503 | status=503; bodyLength=44; servingEdge/hashOwnerEdge null |
| same | 1457 | 76 | 503 | status=503; bodyLength=44; servingEdge/hashOwnerEdge null |
| same | 1458 | 201 | 503 | status=503; bodyLength=44; servingEdge/hashOwnerEdge null |
| same | 1459 | 77 | 503 | status=503; bodyLength=44; servingEdge/hashOwnerEdge null |
| same | 1460 | 182 | 503 | status=503; bodyLength=44; servingEdge/hashOwnerEdge null |
| same | 1461 | 235 | 503 | status=503; bodyLength=44; servingEdge/hashOwnerEdge null |
| same | 1462 | 248 | 503 | status=503; bodyLength=44; servingEdge/hashOwnerEdge null |
| same | 1463 | 87 | 503 | status=503; bodyLength=44; servingEdge/hashOwnerEdge null |
| same | 1464 | 0 | 503 | status=503; bodyLength=44; servingEdge/hashOwnerEdge null |
| same | 2211 | 73 | 503 | status=503; bodyLength=44; servingEdge/hashOwnerEdge null |
| same | 2212 | 148 | 503 | status=503; bodyLength=44; servingEdge/hashOwnerEdge null |
| same | 2213 | 26 | 503 | status=503; bodyLength=44; servingEdge/hashOwnerEdge null |
| same | 2214 | 105 | 503 | status=503; bodyLength=44; servingEdge/hashOwnerEdge null |
| same | 2215 | 224 | 503 | status=503; bodyLength=44; servingEdge/hashOwnerEdge null |

The saved adaptive-router log output for 03:59:09–03:59:47 UTC contains
upstream `timeout awaiting response headers` errors, “all edge nodes failed to
respond” at 03:59:14 and 03:59:22, and “no healthy edge nodes available in
the hash ring” from 03:59:22 through 03:59:47. These are consistent with the
failure class, but request IDs were not logged and the errors cannot be
matched one-to-one to the 19 CSV rows. Earlier saved router output also
contains control-discovery deadline errors at 03:52:55 and 03:54:12 UTC; no
evidence ties those to individual failed requests. The queried control and
edge logs in the focused 03:45–04:05 UTC range did not establish a separate
lease-expiry, origin, port-exhaustion, or process-crash cause. Historical
resource telemetry from the failed run is unavailable.

The exact 10-trial uniform/adaptive/slack-1000 rerun used the same deterministic
run seeds and base configuration (3,000 measured requests, 256 warm-up
requests, concurrency 16, 64-KiB cache bodies per edge, 256 1-KiB objects,
20-ms origin delay). It was run in the same existing Compose session and the
original data was left untouched:

| Dataset | Trial outcomes | Requests | Errors |
| --- | --- | ---: | ---: |
| Original `routing-sweep-2026-10-25T19-23-50-602Z.json` | 9 trials with 0 errors; run 8 has 19 (3 HTTP 502, 16 HTTP 503) | 30,000 | 19 |
| Replay `routing-sweep-2026-10-26T05-10-19-985Z.json` | All 10 trials have 0 errors | 30,000 | 0 |

The replay request CSV has timestamps on all 30,000 rows and zero error rows.
During the replay, Docker stats sampled 18 containers eight times each; the
maximum observed container CPU was 65.89% and maximum memory was 152.3 MiB.
This repeat-run snapshot does not establish historical resource pressure.
Cause remains **undetermined**; proxy timeouts and unhealthy-ring exhaustion
were observed, but no direct failed-request correlation or root trigger was
captured.

The harness now accepts a `WORKLOADS` comma-separated filter (defaulting to
all workloads), records request start/completion timestamps, and includes a
bounded response-body excerpt in new HTTP-error rows. Existing request exports
were not edited. The replay data and its Docker-stat samples are new dated
files under `docs/academic/results/`.

### Commands and outcomes

| Command/action | Exit | Summary |
| --- | ---: | --- |
| `node --check .\scripts\compare-routing.mjs`; filtered `--dry-run` with `WORKLOADS=uniform`, `POLICIES=adaptive`, `SLACKS=1000` | 0 | Planned 10 trials; 3,000 requests, 256 warm-up, concurrency 16. |
| Filtered `node .\scripts\compare-routing.mjs` with the same variables plus 10 repetitions | Wrapper: 0; child exit code not captured | Harness emitted `status: complete`, 10 trials / 30,000 measured requests, and 0 errors; generated JSON, CSV, partial checkpoint, request CSV, and spill-latency CSV with prefix `routing-sweep-2026-10-26T05-10-19-985Z`. |
| PowerShell Docker-stat sampling loop during replay | 0 | Wrote `routing-docker-stats-2026-10-26T10-40-19.csv`; 144 container samples. |
| `docker ps -a --format ...` | 0 | Confirmed the experiment routers, edges, origin, and control services were running during inspection. |
| `Import-Csv` on original 1.2M-row request export filtered to run 8 | 0 | Extracted all 19 failures and exact indices, keys, statuses, stored error strings; no timestamp/body text present. |
| `docker logs` for adaptive router, control and edge containers, incident time filters | 0 / output-limit `-1` on broad router capture | Focused output confirms proxy timeouts, all-edge-failed and no-healthy-ring messages; no one-to-one request correlation. Broad output was retained only in the temporary tool file, not as a new dataset. |
| Results-folder `.partial.json` listing and `git log --all --name-only -- docs/academic/results` search | 0 | Only completed sweep manifests found; aborted 494-error manifest absent. |
| `Import-Csv` validation of replay request CSV | 0 | 30,000 rows; 0 missing timestamps; 0 errors. |
| `node --check .\scripts\compare-routing.mjs`; `git diff --check` | 0 | Both passed. |

**Files changed/created in this follow-up:** `scripts/compare-routing.mjs`;
`routing-docker-stats-2026-10-26T10-40-19.csv`; and five persistent replay
outputs with prefix `routing-sweep-2026-10-26T05-10-19-985Z`: `.json`, `.csv`,
`.partial.json`, `-requests.csv`, and `-spill-latency.csv`. The harness also
created then removed its temporary `-requests.partial.csv` after successful
completion. No paper, Go, or retained dataset file was changed.

## Follow-up Task 2 — Same-session baselines

**Status: failed and blocked; Tasks 3–9 were not started.** The prescribed
interleaved baseline sweep did not complete, so its partial output must not be
used for policy comparisons. All partial evidence is retained, and a new run
must use a different dated prefix.

The run used seed `2100260` with seed derivation `seed + run index`, 10
repetitions, four workloads, five policies (consistent hash, round robin,
adaptive slack 2, least-loaded router-local, and bounded-load router-local),
3,000 measured requests after 256 warm-up requests, concurrency 16, 64-KiB
cache bodies per edge, 256 1-KiB objects, and 20-ms origin delay. It planned
200 trials and completed 68 trials / 204,000 measured requests before aborting
during warm-up for `run-3-zipf-round_robin`, key 5, with HTTP 502. The warm-up
failure was not included in the measured-request CSV. The partial manifest
records status `incomplete`, expected/completed trials `200/68`, the failed
trial ID, and the harness error.

The request-level failure export contains all 1,563 failed measured requests,
including trial ID, request timestamp, key, HTTP status, and response error
text. The grouped export contains the following exhaustive trial/status
breakdown; its first/last timestamp columns preserve each group's time range:

| Trial ID | Status | Failed requests | Stored response error |
| --- | ---: | ---: | --- |
| `run-0-uniform-round_robin` | 503 | 133 | `Service Unavailable (No healthy edge nodes)` |
| `run-0-uniform-least_loaded_router_local` | 503 | 100 | `Service Unavailable (No healthy edge nodes)` |
| `run-0-zipf-round_robin` | 503 | 128 | `Service Unavailable (No healthy edge nodes)` |
| `run-0-changing_hot-consistent_hash` | 503 | 68 | `Service Unavailable (No healthy edge nodes)` |
| `run-0-changing_hot-consistent_hash` | 502 | 12 | `Bad Gateway (All edge nodes failed to respond)` |
| `run-0-changing_hot-round_robin` | 503 | 176 | `Service Unavailable (No healthy edge nodes)` |
| `run-0-changing_hot-least_loaded_router_local` | 502 | 2 | `Bad Gateway (All edge nodes failed to respond)` |
| `run-0-changing_hot-least_loaded_router_local` | 503 | 5 | `Service Unavailable (No healthy edge nodes)` |
| `run-1-uniform-round_robin` | 503 | 305 | `Service Unavailable (No healthy edge nodes)` |
| `run-1-uniform-bounded_load_router_local` | 503 | 3 | `Service Unavailable (No healthy edge nodes)` |
| `run-1-zipf-adaptive-slack-2` | 503 | 15 | `Service Unavailable (No healthy edge nodes)` |
| `run-1-zipf-least_loaded_router_local` | 503 | 1 | `Service Unavailable (No healthy edge nodes)` |
| `run-2-uniform-least_loaded_router_local` | 503 | 100 | `Service Unavailable (No healthy edge nodes)` |
| `run-2-zipf-adaptive-slack-2` | 503 | 62 | `Service Unavailable (No healthy edge nodes)` |
| `run-2-changing_hot-consistent_hash` | 502 | 5 | `Bad Gateway (All edge nodes failed to respond)` |
| `run-3-zipf-least_loaded_router_local` | 502 | 139 | `Bad Gateway (All edge nodes failed to respond)` |
| `run-3-zipf-least_loaded_router_local` | 503 | 205 | `Service Unavailable (No healthy edge nodes)` |
| `run-3-zipf-consistent_hash` | 503 | 38 | `Service Unavailable (No healthy edge nodes)` |
| `run-3-zipf-consistent_hash` | 502 | 66 | `Bad Gateway (All edge nodes failed to respond)` |

Across those rows, there were 1,339 HTTP 503 responses in 14 groups from
2026-10-26T08:02:25.260Z through 08:35:59.927Z, and 224 HTTP 502 responses
in five groups from 08:06:59.857Z through 08:36:27.192Z. Exact per-request
timestamps, indices, keys, and messages are in
`docs/academic/results/routing-sweep-2026-10-26T08-01-04-828Z-failures.csv`;
group counts and timestamp bounds are in
`docs/academic/results/routing-sweep-2026-10-26T08-01-04-828Z-failure-summary.csv`.

The immediate router-side failure mechanism is supported by logs: routers
reported `net/http: timeout awaiting response headers`, then
`all edge nodes failed to respond` (502), and/or
`no healthy edge nodes available in the hash ring` (503). For example,
`router-rr-1` logged those conditions at 08:36:52 UTC during the final
round-robin warm-up failure. Edge logs around 08:36:30–08:36:39 show origin
fetches ending in `context canceled`, consistent with upstream cancellation.
Across the captured router logs there were 811 upstream-header-timeout lines,
1,217 empty-ring warning lines, six discovery-error lines, and four
health-check-failure lines. These log counts are line counts, not unique
request counts; logs contain no request IDs to join to the CSV.

The router's configured response-header timeout is 1,500 ms
(`cmd/router/main.go`); proxy failures mark nodes unhealthy in that router's
local ring. An empty local ring explains the 503 responses, and exhausting
candidate edges after upstream timeouts explains the 502 responses. The
underlying reason response headers exceeded 1,500 ms remains **undetermined**.
Control registration uses a 15-second lease and edge heartbeats run every
five seconds; no direct lease-expiry evidence was found. Containers were
running when checked, with no confirmed crash or port-exhaustion evidence.
The post-run `docker stats --no-stream` snapshot showed container memory
generally below 153 MiB and CPU below 25% (Prometheus was the highest at
24.84%); this was not a peak measurement and does not rule out transient host
or container pressure. No contemporaneous host-level resource or port
telemetry was collected.

| Command/action | Exit | Summary |
| --- | ---: | --- |
| Docker Compose config validation of the experiment overlay by itself | 1 | Expected failure: the override is not a standalone Compose project. |
| Docker Compose config validation with the base file and experiment overlay | 0 | Merged configuration validated. |
| Same-session 200-trial baseline sweep via `node .\scripts\compare-routing.mjs` | 1 | Stopped at 68/200; warm-up for `run-3-zipf-round_robin` failed with HTTP 502. |
| Failure CSV generation and aggregation | 0 | Wrote 1,563 per-request failures and 19 grouped trial/status rows; totals are 1,339 HTTP 503 and 224 HTTP 502. |
| Router/control/edge log inspection and grouping | 0 | Found the timeout / unhealthy-ring mechanism above; six discovery-error and four health-check-failure lines, without direct evidence of lease expiration. |
| `docker compose ps` and post-run `docker stats --no-stream` | 0 | Containers were up; snapshot was not contemporaneous peak telemetry. |
| `node --check .\scripts\compare-routing.mjs`, Python AST checks, PowerShell parser checks, and Docker `gofmt` | 0 | Passed at the time recorded; the full Go suite and final paper build have not been rerun after the latest edits. |
| `git diff --check` after this report update | 0 | Passed; Git emitted only LF-to-CRLF normalization warnings for the two modified Go files. |

**Files created by the failed run:** `docs/academic/results/routing-sweep-2026-10-26T08-01-04-828Z.partial.json`,
`docs/academic/results/routing-sweep-2026-10-26T08-01-04-828Z-requests.partial.csv`,
`docs/academic/results/routing-sweep-2026-10-26T08-01-04-828Z-failures.csv`,
and `docs/academic/results/routing-sweep-2026-10-26T08-01-04-828Z-failure-summary.csv`.
The router logs were inspected from Docker's retained container logs; no
persistent log excerpt file was created. These files are evidence of an
incomplete run only and are not valid completed baseline results.

**Remaining TODOs:** resolve whether to rerun the baseline sweep with a
separately disclosed, configurable router response-header timeout (keeping
the current 1,500-ms default unchanged), or retain Task 2 as blocked. Any
rerun must use a new dated prefix and preserve this failed attempt. Until a
valid same-session baseline run completes, paired analysis, capacity-model
checks using the new baseline run, constrained-service experiments, sensitivity
sweeps, final paper results/figures, and final validation remain paused.
