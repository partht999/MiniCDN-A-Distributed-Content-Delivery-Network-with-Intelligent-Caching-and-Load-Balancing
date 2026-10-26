import fs from 'node:fs/promises';
import { createReadStream } from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
import { performance } from 'node:perf_hooks';

const seed = 2100260;
const objects = 256;
const objectBytes = 1024;
const requests = Number(process.env.REQUESTS || 3000);
const concurrency = Number(process.env.CONCURRENCY || 16);
const repetitions = Number(process.env.REPETITIONS || 10);
const warmupRequests = Number(process.env.WARMUP_REQUESTS || 256);
const slacks = (process.env.SLACKS || '0,1,2,4,8,1000').split(',').map(Number);
const selectedPolicies = process.env.POLICIES?.split(',').map(value => value.trim()).filter(Boolean);
const root = process.cwd();
const startedAt = new Date();
const date = startedAt.toISOString().slice(0, 10);
const runStamp = startedAt.toISOString().replaceAll(':', '-').replaceAll('.', '-');
const resultsDir = path.join(root, 'docs/academic/results');
const resumeManifestArg = process.env.RESUME_MANIFEST;
const outputPrefix = resumeManifestArg
  ? path.basename(resumeManifestArg).replace(/\.partial\.json$/, '')
  : `routing-sweep-${runStamp}`;
const dryRun = process.argv.includes('--dry-run');
const policies = [
  { policy: 'consistent_hash', port: 8080, slack: null },
  { policy: 'round_robin', port: 8084, slack: null },
  { policy: 'adaptive', port: 8086, slack: 0 },
  { policy: 'adaptive', port: 8087, slack: 1 },
  { policy: 'adaptive', port: 8085, slack: 2 },
  { policy: 'adaptive', port: 8088, slack: 4 },
  { policy: 'adaptive', port: 8089, slack: 8 },
  { policy: 'adaptive', port: 8090, slack: 1000 },
  { policy: 'least_loaded_router_local', routingMode: 'least_loaded', port: 8091, slack: null },
  { policy: 'bounded_load_router_local', routingMode: 'bounded_load', port: 8092, slack: null },
].filter(item =>
  (item.slack === null || slacks.includes(item.slack)) &&
  (!selectedPolicies || selectedPolicies.includes(item.policy)),
);
const workloads = ['uniform', 'zipf', 'changing_hot', 'cold_burst'];

if (![requests, concurrency, repetitions].every(value => Number.isInteger(value) && value > 0) ||
    !Number.isInteger(warmupRequests) || warmupRequests < 0 ||
    slacks.length === 0 || slacks.some(value => !Number.isInteger(value) || value < 0)) {
  throw new Error('Invalid sweep configuration; counts and slack must be nonnegative integers.');
}
if (!dryRun && (requests < 3000 || repetitions < 10 || warmupRequests === 0)) {
  throw new Error('Submission sweep requires at least 3000 measured requests, 10 repetitions, and a nonempty warm-up.');
}
if (dryRun) {
  console.log(JSON.stringify({
    mode: 'dry-run',
    seedDerivation: 'seed + run index',
    workloads,
    policies,
    repetitions,
    requestsPerTrial: requests,
    warmupRequests,
    concurrency,
    plannedTrials: repetitions * workloads.length * policies.length,
  }, null, 2));
  process.exit(0);
}

await fs.mkdir(path.join(root, 'sample-content/benchmark'), { recursive: true });
await fs.mkdir(resultsDir, { recursive: true });
for (let i = 0; i < objects; i++) {
  await fs.writeFile(path.join(root, `sample-content/benchmark/${i}.txt`), `${i}:`.padEnd(objectBytes, 'x'));
}

function random(initial) {
  let state = initial >>> 0;
  return () => {
    state = (Math.imul(1664525, state) + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

function trace(workload, run) {
  const rng = random(seed + run);
  const weights = Array.from({ length: objects }, (_, index) => 1 / (index + 1) ** 1.1);
  const total = weights.reduce((sum, weight) => sum + weight, 0);
  return Array.from({ length: warmupRequests + requests }, (_, index) => {
    if (workload === 'uniform') return Math.floor(rng() * objects);
    if (workload === 'cold_burst') return 0;
    let value = rng() * total;
    let key = objects - 1;
    for (let i = 0; i < objects; i++) {
      value -= weights[i];
      if (value <= 0) {
        key = i;
        break;
      }
    }
    return workload === 'changing_hot' && index >= warmupRequests + requests / 2
      ? (key + 128) % objects
      : key;
  });
}

async function counters() {
  let origin = 0;
  let coalesced = 0;
  for (const port of [8081, 8082, 8083]) {
    const response = await fetch(`http://127.0.0.1:${port}/metrics`);
    if (!response.ok) throw new Error(`Edge metrics unavailable on port ${port}: HTTP ${response.status}`);
    const text = await response.text();
    for (const line of text.split('\n')) {
      if (line.startsWith('cdn_origin_requests_total{')) origin += Number(line.split(' ').at(-1));
      if (line.startsWith('cdn_coalesced_requests_total{')) coalesced += Number(line.split(' ').at(-1));
    }
  }
  return { origin, coalesced };
}

async function purgeBenchmarkCache() {
  const response = await fetch('http://127.0.0.1:7000/api/v1/purge', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prefixes: ['/benchmark/'] }),
  });
  const body = await response.json();
  if (response.status !== 200 || Object.keys(body.details || {}).length !== 3 ||
      Object.values(body.details).some(status => status !== 'success')) {
    throw new Error(`Prefix purge was not acknowledged by all three edges: HTTP ${response.status}, ${JSON.stringify(body)}`);
  }
}

async function runWarmup(port, keys, trialId) {
  let next = 0;
  let retries = 0;
  const retryableStatus = new Set([502, 503, 504]);
  await Promise.all(Array.from({ length: concurrency }, async () => {
    while (next < keys.length) {
      const key = keys[next++];
      let failure = '';
      let succeeded = false;
      for (let attempt = 0; attempt < 4; attempt++) {
        try {
          const response = await fetch(`http://127.0.0.1:${port}/benchmark/${key}.txt`);
          const body = await response.text();
          if (response.status === 200 && body.length === objectBytes && body.startsWith(`${key}:`)) {
            succeeded = true;
            break;
          }
          failure = `HTTP ${response.status}, bodyLength=${body.length}, bodyPrefix=${JSON.stringify(body.slice(0, 32))}`;
          if (!retryableStatus.has(response.status)) break;
        } catch (error) {
          failure = String(error);
        }
        if (attempt < 3) {
          retries++;
          await new Promise(resolve => setTimeout(resolve, 250 * (attempt + 1)));
        }
      }
      if (!succeeded) {
        throw new Error(`Warm-up failed for trial ${trialId}, key ${key}, router port ${port}: ${failure}`);
      }
    }
  }));
  return retries;
}

const csvValue = value => `"${String(value ?? '').replaceAll('"', '""')}"`;
const requestFields = [
  'trialId', 'run', 'workload', 'policy', 'slack', 'index', 'key', 'servingEdge',
  'hashOwnerEdge', 'spilled', 'cacheStatus', 'latencyMs', 'httpStatus', 'error',
];
const csvLine = row => requestFields.map(field => csvValue(row[field])).join(',') + '\n';
const metadata = {
  seed,
  seedDerivation: 'seed + run index',
  objects,
  objectBytes,
  cacheBodyBytesPerEdge: 65536,
  concurrency,
  repetitions,
  requestsPerTrial: requests,
  warmupRequests,
  originDelayMs: 20,
  cacheTTLSeconds: 3600,
  workloads,
  slacks,
  policies: [...new Set(policies.map(item => item.policy))],
  boundedLoadCapacityFactor: Number(process.env.BOUNDED_LOAD_CAPACITY_FACTOR || 2),
  hashReplicas: 50,
  method: 'closed-loop; stack warm-up excluded, followed by acknowledged cache purge; single host Docker; no network impairment',
  createdAt: new Date().toISOString(),
  requestFields: ['trialId', 'key', 'servingEdge', 'hashOwnerEdge', 'spilled', 'cacheStatus', 'latencyMs'],
};
const partialManifestPath = path.join(resultsDir, `${outputPrefix}.partial.json`);
const partialRequestsPath = path.join(resultsDir, `${outputPrefix}-requests.partial.csv`);
const expectedTrials = repetitions * workloads.length * policies.length;
let rows = [];
const completedTrialIds = new Set();
const spillSamples = new Map();
let currentTrialId = null;
let warmupRetries = 0;
let requestCount = 0;

function parseCsvLine(line) {
  const fields = [];
  let value = '';
  let quoted = false;
  for (let index = 0; index < line.length; index++) {
    const character = line[index];
    if (quoted && character === '"' && line[index + 1] === '"') {
      value += '"';
      index++;
    } else if (character === '"') {
      quoted = !quoted;
    } else if (character === ',' && !quoted) {
      fields.push(value);
      value = '';
    } else {
      value += character;
    }
  }
  fields.push(value);
  return fields;
}

function addSpillSample(request) {
  if (!['HIT', 'MISS'].includes(request.cacheStatus) ||
      !['true', 'false'].includes(request.spilled) || request.error) return;
  const spill = request.spilled === 'true' ? 'spilled' : 'non_spilled';
  const key = [request.workload, request.policy, request.slack, spill, request.cacheStatus].join('|');
  if (!spillSamples.has(key)) spillSamples.set(key, []);
  spillSamples.get(key).push(Number(request.latencyMs));
}

if (resumeManifestArg) {
  const manifestPath = path.resolve(root, resumeManifestArg);
  const prior = JSON.parse(await fs.readFile(manifestPath, 'utf8'));
  if (prior.status !== 'incomplete' || prior.expectedTrials !== expectedTrials ||
      prior.metadata.requestsPerTrial !== requests ||
      prior.metadata.warmupRequests !== warmupRequests ||
      prior.metadata.concurrency !== concurrency ||
      JSON.stringify(prior.metadata.slacks) !== JSON.stringify(slacks)) {
    throw new Error('Resume manifest is incomplete or does not match the current sweep configuration.');
  }
  rows = prior.rows;
  for (const row of rows) completedTrialIds.add(row.trialId);
  warmupRetries = prior.warmupRetries || 0;
  const reader = readline.createInterface({
    input: createReadStream(partialRequestsPath, { encoding: 'utf8' }),
    crlfDelay: Infinity,
  });
  let isHeader = true;
  for await (const line of reader) {
    if (isHeader) {
      isHeader = false;
      continue;
    }
    if (!line) continue;
    const values = parseCsvLine(line);
    addSpillSample(Object.fromEntries(requestFields.map((field, index) => [field, values[index]])));
    requestCount++;
  }
  if (requestCount !== rows.length * requests) {
    throw new Error(`Resume checkpoint mismatch: request rows ${requestCount} != completed-trial requests ${rows.length * requests}`);
  }
} else {
  await fs.writeFile(partialRequestsPath, requestFields.join(',') + '\n');
  await fs.writeFile(partialManifestPath, JSON.stringify({
    metadata, status: 'running', expectedTrials, completedTrials: 0, rows,
  }, null, 2) + '\n');
}

try {
  for (let run = 0; run < repetitions; run++) {
    const order = policies.slice(run % policies.length).concat(policies.slice(0, run % policies.length));
    for (const workload of workloads) {
      const allKeys = trace(workload, run);
      const warmKeys = allKeys.slice(0, warmupRequests);
      const measuredKeys = allKeys.slice(warmupRequests);
      for (const { policy, port, slack } of order) {
        const trialId = `run-${run}-${workload}-${policy}${slack === null ? '' : `-slack-${slack}`}`;
        if (completedTrialIds.has(trialId)) continue;
        currentTrialId = trialId;
        const healthResponse = await fetch(`http://127.0.0.1:${port}/health`);
        if (!healthResponse.ok) {
          throw new Error(`Health check failed for ${trialId} on port ${port}: HTTP ${healthResponse.status}`);
        }
        const health = await healthResponse.json();
        const policyConfig = policies.find(item => item.policy === policy && item.slack === slack);
        if (health.routing_mode !== (policyConfig?.routingMode || policy) ||
            (slack !== null && Number(health.adaptive_slack) !== slack)) {
          throw new Error(`Router configuration mismatch for ${trialId}: ${JSON.stringify(health)}`);
        }
        if (policy === 'bounded_load_router_local' &&
            Number(health.bounded_load_capacity_factor) !== metadata.boundedLoadCapacityFactor) {
          throw new Error(`Bounded-load capacity factor mismatch for ${trialId}: ${JSON.stringify(health)}`);
        }

        await purgeBenchmarkCache();
        warmupRetries += await runWarmup(port, warmKeys, trialId);
        await purgeBenchmarkCache();
        const before = await counters();
        const latencies = [];
        const edges = {};
        const statuses = {};
        const trialRaw = [];
        let errors = 0;
        let next = 0;
        const started = performance.now();

        await Promise.all(Array.from({ length: concurrency }, async () => {
          while (next < measuredKeys.length) {
            const index = next++;
            const key = measuredKeys[index];
            const begin = performance.now();
            try {
              const response = await fetch(`http://127.0.0.1:${port}/benchmark/${key}.txt`);
              const body = await response.text();
              const latencyMs = performance.now() - begin;
              latencies.push(latencyMs);
              const servingEdge = response.headers.get('x-edge-node');
              const hashOwnerEdge = response.headers.get('x-hash-owner');
              const cacheStatus = response.headers.get('x-cache') || 'none';
              const spilled = servingEdge && hashOwnerEdge ? servingEdge !== hashOwnerEdge : null;
              const requestError = response.status !== 200 || body.length !== objectBytes ||
                !body.startsWith(`${key}:`) || !servingEdge || !hashOwnerEdge;
              if (requestError) errors++;
              if (servingEdge) edges[servingEdge] = (edges[servingEdge] || 0) + 1;
              statuses[cacheStatus] = (statuses[cacheStatus] || 0) + 1;
              const request = {
                trialId, run, workload, policy, slack, index, key, servingEdge,
                hashOwnerEdge, spilled, cacheStatus, latencyMs, httpStatus: response.status,
                error: requestError
                  ? `status=${response.status}, bodyLength=${body.length}, servingEdge=${servingEdge}, hashOwnerEdge=${hashOwnerEdge}`
                  : '',
              };
              trialRaw.push(request);
              if (['HIT', 'MISS'].includes(cacheStatus) && spilled !== null && !requestError) {
                const spill = spilled ? 'spilled' : 'non_spilled';
                const group = [workload, policy, slack, spill, cacheStatus].join('|');
                if (!spillSamples.has(group)) spillSamples.set(group, []);
                spillSamples.get(group).push(latencyMs);
              }
            } catch (error) {
              errors++;
              const latencyMs = performance.now() - begin;
              latencies.push(latencyMs);
              trialRaw.push({
                trialId, run, workload, policy, slack, index, key, servingEdge: '',
                hashOwnerEdge: '', spilled: '', cacheStatus: 'ERROR', latencyMs,
                httpStatus: '', error: String(error),
              });
            }
          }
        }));

        const seconds = (performance.now() - started) / 1000;
        const after = await counters();
        latencies.sort((a, b) => a - b);
        const percentile = p => latencies[Math.max(0, Math.ceil(p * latencies.length) - 1)] ?? null;
        const edgeCounts = ['edge-1', 'edge-2', 'edge-3'].map(edge => edges[edge] || 0);
        const average = edgeCounts.reduce((sum, count) => sum + count, 0) / 3;
        const variance = edgeCounts.reduce((sum, count) => sum + (count - average) ** 2, 0) / 3;
        const distinctKeys = new Set(measuredKeys).size;
        const originAttempts = after.origin - before.origin;
        const row = {
          trialId, run, workload, policy, slack, requests, warmupRequests, errors,
          seconds, rps: (requests - errors) / seconds,
          p50_ms: percentile(0.5), p95_ms: percentile(0.95), p99_ms: percentile(0.99),
          hits: statuses.HIT || 0, hit_ratio: (statuses.HIT || 0) / requests,
          misses: statuses.MISS || 0, revalidated: statuses.REVALIDATED || 0,
          origin_attempts: originAttempts, distinct_keys: distinctKeys,
          compulsory_miss_floor: distinctKeys, excess_origin_attempts: originAttempts - distinctKeys,
          coalesced: after.coalesced - before.coalesced,
          request_cv: average === 0 ? null : Math.sqrt(variance) / average,
          edges: edgeCounts,
        };
        if (trialRaw.length !== requests) {
          throw new Error(`Incomplete raw request count for ${trialId}: ${trialRaw.length}/${requests}`);
        }
        rows.push(row);
        completedTrialIds.add(trialId);
        requestCount += trialRaw.length;
        await fs.appendFile(partialRequestsPath, trialRaw.map(csvLine).join(''));
        await fs.writeFile(partialManifestPath, JSON.stringify({
          metadata, status: 'running', expectedTrials, completedTrials: rows.length,
          lastCompletedTrialId: trialId, requestCount, warmupRetries, rows,
        }, null, 2) + '\n');
        console.log(JSON.stringify(row));
      }
    }
  }

  if (rows.length !== expectedTrials || requestCount !== expectedTrials * requests) {
    throw new Error(`Sweep completeness check failed: trials=${rows.length}/${expectedTrials}, requests=${requestCount}`);
  }
  const spillLatency = [...spillSamples.entries()].map(([key, values]) => {
    const [workload, policy, slack, spill, cacheStatus] = key.split('|');
    const sorted = [...values].sort((a, b) => a - b);
    return {
      workload, policy, slack: slack === 'null' ? null : Number(slack), spill, cacheStatus,
      n: values.length,
      p50_ms: sorted[Math.max(0, Math.ceil(0.5 * sorted.length) - 1)],
      p95_ms: sorted[Math.max(0, Math.ceil(0.95 * sorted.length) - 1)],
    };
  });
  const trialFields = Object.keys(rows[0]);
  const trialCsv = [trialFields.join(','), ...rows.map(row => trialFields.map(field => csvValue(
    typeof row[field] === 'object' ? JSON.stringify(row[field]) : row[field],
  )).join(','))].join('\n') + '\n';
  const spillFields = Object.keys(spillLatency[0] || {});
  const spillCsv = [spillFields.join(','), ...spillLatency.map(row => spillFields.map(field => csvValue(row[field])).join(','))].join('\n') + '\n';
  await Promise.all([
    fs.writeFile(path.join(resultsDir, `${outputPrefix}.json`), JSON.stringify({ metadata: { ...metadata, warmupRetries }, rows }, null, 2) + '\n'),
    fs.writeFile(path.join(resultsDir, `${outputPrefix}.csv`), trialCsv),
    fs.rename(partialRequestsPath, path.join(resultsDir, `${outputPrefix}-requests.csv`)),
    fs.writeFile(path.join(resultsDir, `${outputPrefix}-spill-latency.csv`), spillCsv),
    fs.writeFile(partialManifestPath, JSON.stringify({
      metadata: { ...metadata, warmupRetries }, status: 'complete',
      expectedTrials, completedTrials: rows.length, requestCount, rows,
    }, null, 2) + '\n'),
  ]);
  console.log(JSON.stringify({
    outputPrefix, status: 'complete', trials: rows.length, requests: requestCount,
    errors: rows.reduce((sum, row) => sum + row.errors, 0), warmupRetries,
  }, null, 2));
} catch (error) {
  await fs.writeFile(partialManifestPath, JSON.stringify({
    metadata: { ...metadata, warmupRetries },
    status: 'incomplete',
    expectedTrials,
    completedTrials: rows.length,
    requestCount,
    failedTrialId: currentTrialId,
    error: String(error),
    rows,
  }, null, 2) + '\n');
  console.error(`Sweep incomplete; checkpoint saved to ${partialManifestPath}: ${error.stack || error}`);
  process.exitCode = 1;
}
