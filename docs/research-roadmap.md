# MiniCDN research gaps and provisional implementation plan

Historical baseline below predates the 10 October 2026 implementation. Current status: [SRS](academic/design-and-srs.md), [five-paper review](academic/research-review.md), [measured experiments](academic/results/routing-comparison.csv), and [submission ledger](academic/submission-plan.md). The phase documents have now been read; their corrected dates are recorded in the ledger.

Source: [team research spreadsheet](https://docs.google.com/spreadsheets/d/13rEOH9j8I06yjXPwloEVA6oUUNkNzP6fuSS_WThoX5U/edit).
Both tabs were read. The three ranking tables repeat candidate topics; they are prioritization opinions, not evidence of novelty. This plan is provisional until the separate phase-deliverables document is supplied.

## What the repository actually implements

- `cmd/origin`: static files, fixed one-hour cache lifetime, ETag and Last-Modified, client conditional requests.
- `pkg/cache`: synchronized memory map, TTL expiry on lookup, counters, exact-key deletion. No disk tier, byte limit, LRU, LFU, or retention of expired entries for revalidation.
- `pkg/hash`: CRC32 consistent-hash ring, virtual nodes and clockwise fallback candidates.
- `cmd/router`: 50 virtual nodes per edge, fixed discovery/health checks and proxy fallback. Selection is based on path, not load, region, query, or measured latency. The advertised node weight is unused.
- `cmd/control`: Redis registration with a 15-second lease, URL purge broadcast to currently registered nodes. There is no durable invalidation history, anti-entropy, prefix purge, or config endpoint.
- `cmd/edge`: five-second registration heartbeat, GET cache and HEAD support, origin fetching and Prometheus instrumentation. Before this increment, every cold concurrent request could fetch independently.
- Compose: three edges, origin, Redis, router, Prometheus and Grafana. All edges are local; region labels alone do not simulate network distance.
- Existing tests cover cache operations, hash-ring behavior, TTL parsing, hit flow, and query isolation. The demo scripts demonstrate basic behavior; `demo_mock.js` prints simulated output and is not experimental evidence.

The README is a blueprint with unchecked tasks, not a reliable completion ledger. Origin-side conditional handling already exists, but edge-to-origin conditional revalidation of expired objects does not.

## All 14 distinct gaps

### 1. Adaptive load balancing

Hashing spreads keys, but traffic is requests: if one key receives most requests, its assigned edge can become a hotspot. Prefer the hash owner until its measured load exceeds a bound, then choose a less-loaded healthy candidate. The research question is how much P99 latency and load imbalance improve, and how much locality is lost. Compare against plain consistent hashing and round robin with the same skewed workload. Define load explicitly (in-flight requests, queue delay or utilization). An object-count bound from a paper is not automatically a request-load guarantee.

### 2. Dynamic virtual nodes

The current router uses a fixed 50 virtual nodes per edge. Varying allocation can change how much hash space each edge owns as capacity or traffic changes. This differs from adaptive routing: it changes ownership, rather than making a temporary per-request choice. Measure remapped keys, cold misses, update overhead and load variance. Use smoothing and hysteresis to avoid continuous remapping. More virtual nodes alone cannot split traffic to one extremely hot key.

### 3. Adaptive cache invalidation

A frequently changing page and a stable logo should not necessarily use the same freshness policy. Estimate update frequency and popularity, then choose when to revalidate or invalidate under a specified freshness budget. Compare fixed TTL and fixed revalidation intervals against the adaptive rule. Measure stale responses against origin versions, origin fetches and invalidation latency. Popularity does not imply that content is unchanged; do not extend freshness beyond the origin's permitted policy without an explicit application contract.

### 4. Failure detection and heartbeat optimization

Short intervals detect failures quickly but generate more control traffic; long intervals reduce overhead but prolong incorrect routing. Adapt the probing interval or suspicion threshold to recent behavior. Compare against the current five-second heartbeat, 15-second registry lease and fixed router checks. Measure detection delay, false failure suspicions, failed requests and control messages. Test crash, slow node and network delay separately; a slow response is not proof of failure.

### 5. Cache locality versus fault tolerance / popularity-aware replication

One preferred edge gives good locality until it fails. Keeping every object everywhere improves survival but consumes storage and transfer bandwidth. Replicate hot objects to a small number of independent peers and leave cold objects less replicated. Compare no replication, a fixed replica count, and adaptive replication. Measure post-failure hit ratio, availability, recovery latency and replication bytes. Copies need the same version and invalidation rules as their source.

### 6. Popularity-prediction prefetching

Reactive caching waits for the first user to incur the miss. Use past demand to fetch probable future requests before they arrive. Start with a rolling popularity count before introducing a prediction model. Measure useful prefetches divided by all prefetches, extra origin bytes, eviction of useful objects and user latency. HTML-discovered asset prefetching in the ranking table is a specific extension: it predicts dependencies from references, rather than predicting general popularity. Evaluate it separately and constrain fetch targets and budget.

### 7. Latency-aware cache placement

An object may exist on an edge far from its users even when another edge would serve them faster. Use client-region demand and network measurements to choose where copies should live. This changes placement; latency-based routing only changes which existing edge handles a request. Measure client-observed latency, hit ratio and movement bytes. Router-to-edge RTT is not client-to-edge RTT; local Compose needs explicit emulated delays for a credible region experiment.

### 8. Workload-aware eviction policy switching

LRU rewards recency; LFU rewards repeated popularity. Their usefulness may change between scans, repeated hot keys and shifting demand. Detect a workload shift and select or blend policies. First implement bounded storage and both baseline policies: the current map has neither. Compare at an identical byte capacity and account for policy state, switching overhead and warm-up. Measure hit ratio, evictions and memory use.

### 9. Network-congestion-aware routing

A healthy, lightly loaded server may still be reached through a slow network path. Combine locality and server load with measured latency, loss or congestion signals. Separate network impairment from server processing delay; RTT alone cannot identify the cause. Compare with load-only and latency-only routing under controlled impairments. Measure throughput, P99 latency, switching frequency and locality loss.

### 10. Cross-edge cooperative caching

An edge can miss while a peer already has the object. Consult a bounded peer set before contacting origin. Compare independent caches with peer lookup and track origin bytes saved against lookup delay and peer traffic. Add a hop limit to prevent loops, bounded lookup time, and version checks. Cooperative fetching retrieves an existing copy on demand; replication creates additional copies ahead of failure or demand.

### 11. Programmable WebAssembly edge pipeline

Execute small application rules at the edge rather than requiring an origin trip. A possible implementation embeds a Wasm runtime with explicit host functions and CPU/memory limits. Compare no middleware, equivalent native Go middleware and Wasm for the same operation. Measure execution overhead, throughput and memory. Use one deterministic header/routing example first; JWT handling and bot detection each add distinct correctness requirements. Wasm is a programmable-execution feature, not inherently a cache policy.

### 12. Gossip invalidation with anti-entropy

Current purge reaches only available registered nodes. An offline edge may return with an old cache and no record of missed purges. Retain versioned invalidation records, disseminate them among peers, and reconcile missed records on reconnect. Measure convergence, stale reads during and after a partition, messages and retained history. Sequence numbers need a defined issuer/order or version scheme; tombstone cleanup needs a safety rule. Gossip provides eventual convergence, not immediate globally consistent invalidation. SWIM is a membership/failure-detection reference, not by itself a complete cache invalidation protocol.

### 13. HTTP/3 over QUIC and 0-RTT

Evaluate how transport affects delivery under loss and connection setup. HTTP/3 uses independent QUIC streams, which avoids TCP loss blocking unrelated HTTP streams. Compare HTTP/1.1, HTTP/2 and HTTP/3 under identical TLS, content, cache state, connection reuse and network impairment. Measure TTFB, handshake cost, download time and throughput. Treat 0-RTT as a separate resumed-connection experiment with replay-safe requests, not as a benefit on every first connection. This needs a TLS/UDP deployment path beyond the current plain HTTP listeners.

### 14. In-flight request coalescing and streaming fan-out

Concurrent cold requests for one object currently repeat origin work. Coordinate them so one fetch fills the cache and followers reuse it. The initial increment implements buffered cache-fill coordination for cacheable GET responses. Streaming fan-out is a further experiment: begin delivering bytes before the full object is fetched, while bounding slow-follower buffers and handling cancellation and partial failures. Compare independent fetches, buffered coordination, and streaming coordination. Measure actual origin attempts, user TTFB, total latency, follower count and peak memory. Coalescing by itself does not make the cache persistent or fresh after a partition.

## Research framing and references

An implementation gap in this repository is not proof of a gap in the literature. Each proposed contribution needs a precise hypothesis, baseline, workload, constraint, and reproducible result. Several sheet citations are placeholders such as "research on predictive caching"; resolve these to exact papers before making academic novelty claims.

- [Revisiting Consistent Hashing with Bounded Loads, AAAI 2021](https://ojs.aaai.org/index.php/AAAI/article/view/16517) supports the bounded-load discussion; adapt its assumptions carefully to live HTTP requests.
- [Go singleflight documentation](https://pkg.go.dev/golang.org/x/sync/singleflight) shows that duplicate suppression is established. The first implementation here is a keyed cache-fill gate, not the x/sync package and not streaming singleflight.
- [SWIM paper](https://www.cs.cornell.edu/projects/Quicksilver/public_pdfs/SWIM.pdf) is about membership and failure detection; pair it with an explicit invalidation protocol.
- [RFC 9114](https://www.rfc-editor.org/rfc/rfc9114.html) defines HTTP/3 and its independent-stream behavior.
- [RFC 8470](https://www.rfc-editor.org/rfc/rfc8470.html) covers HTTP early-data replay considerations.

## Provisional phases

These research stages supplement the README phases; they do not replace the forthcoming academic deliverables.

| Stage | Deliverable | Exit evidence |
| --- | --- | --- |
| A: baseline and cache-fill coordination | Reproducible cold-burst test, origin counter, feature toggle, basic cache safety | Same-key cacheable burst has one origin attempt with coordination; baseline has one per client; independent keys and cancellation work |
| B: credible storage and experiment foundation | Byte-bounded LRU, cache-key/variant contract, expired-entry revalidation, seeded uniform/Zipf/scan workloads | Fixed-capacity baseline, version-correct responses, repeatable latency and hit measurements |
| C: adaptive routing | Round-robin and hash baselines, in-flight load telemetry, bounded adaptive selection | Under skew, compare P95/P99, per-edge request variance, locality and origin attempts; quantify routing overhead |
| D: recoverable invalidation | Durable versions/tombstones, peer dissemination, reconnect reconciliation | Partition/heal test converges; report stale reads and message cost; no older fill resurrects invalidated data |
| E: one extension | Choose hot-object replication/cooperation OR prediction OR virtual-node adaptation | Demonstrate improvement and overhead against its static baseline |
| F: optional separate tracks | Wasm or HTTP/3 if deliverables/time support them | Controlled middleware or transport comparison; avoid conflating changes with cache/routing experiments |

Recommended core: cache-fill coordination, adaptive routing and recoverable invalidation. Keep heartbeat adaptation and virtual nodes as routing follow-ups; keep Wasm and HTTP/3 optional because they introduce substantial independent scope.

## First increment: implementation and validation status

- `cmd/edge/coalescing.go`: cancellable per-key fill gates with reference cleanup. Other keys proceed independently.
- `cmd/edge/main.go`: miss recheck after gate acquisition, `cdn_origin_requests_total`, `cdn_coalesced_requests_total`, and exact-key purge ordered against coordinated fills.
- `pkg/cache/cache.go`: `Peek` performs the internal recheck without inflating request lookup statistics.
- Requests with Authorization, Cookie, Range or explicit Cache-Control bypass shared caching. Responses carrying Vary or Set-Cookie are conservatively excluded from storage until variant-aware keys are implemented.
- Gate cleanup happens on failure as well as success. Noncacheable/error responses are not shared; queued callers retry independently, potentially serially. This increment is scoped to public cacheable static assets.
- Followers retain `X-Cache: HIT` for dashboard compatibility; the coalesced counter distinguishes an initial miss that benefited from a concurrent fill. Cache lookup statistics still count the initial miss once.
- `COALESCING_ENABLED=false` disables coordination for the comparison baseline. Default is enabled. In Compose, set this environment entry on each edge and recreate those services for the baseline run.
- Buffering still uses `io.ReadAll`; there is no streaming fan-out or object-size limit yet. The gate currently lasts through leader response writing, so a slow leader client can delay followers and purge. Short gate lifetime and bounded streaming belong in the next increment.
- Exact-key purge waits for coordinated fills. Purge recovery, query-variant/prefix invalidation and baseline-mode in-flight purge races remain future work. No mechanism can undo a response already served before invalidation.

Regression tests include a barrier-controlled 32-client cold burst with baseline/coordination modes, independent-key progress, canceled followers, gate cleanup and conservative response cacheability. Across 10 repeated runs, the cold burst produced 32 origin attempts in baseline mode versus 1 with coordination. This is a controlled handler regression, not a full deployed CDN performance benchmark.

Docker Desktop and Compose were found outside the sandbox and the Linux engine was started. Docker's hello-world smoke test and `docker compose config --quiet` passed. The changes were formatted with Go 1.21 in a container; `go test ./...`, `go test -race ./...` (with GCC/musl installed in the disposable container), and 10 repeated cold-burst runs all passed. `git diff --check` passed. To repeat using a local Go toolchain:

```powershell
gofmt -w cmd/edge/main.go cmd/edge/coalescing.go cmd/edge/coalescing_test.go pkg/cache/cache.go
go test ./...
go test -race ./...
go test ./cmd/edge -run TestConcurrentColdBurst -count=10 -v
```

The native Windows race test requires a supported compiler/CGO setup. The completed race test used Linux in Docker. These checks do not claim deployed failover, distributed invalidation, or streaming fan-out verification.

For later experiments record workload seed, content bytes, concurrency, cache capacity, TTL, origin delay, impairment, warm/cold state, repeated runs, errors and software versions. P95/P99 are the latencies at or below which 95%/99% of requests complete. TTFB is time to first response byte. Origin offload is `1 - origin_attempts / eligible_client_requests`; origin bytes and errors must also be reported. Separate content traffic from health, metrics and admin requests in Prometheus queries, since the existing dashboard's broad request totals include control traffic.
