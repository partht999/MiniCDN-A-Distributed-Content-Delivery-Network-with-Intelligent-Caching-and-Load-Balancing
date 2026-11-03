import fs from 'node:fs/promises';
import path from 'node:path';

const root = process.cwd();
const resultsDir = path.join(root, 'docs/academic/results');
const comparisonPath = path.join(resultsDir, 'routing-comparison.json');
const requestsPath = path.join(resultsDir, 'routing-requests.jsonl');
const comparison = JSON.parse(await fs.readFile(comparisonPath, 'utf8'));
const requestLines = (await fs.readFile(requestsPath, 'utf8')).trim().split(/\r?\n/);
const requests = requestLines.map((line, index) => {
  try {
    return JSON.parse(line);
  } catch (error) {
    throw new Error(`Invalid JSON in ${path.basename(requestsPath)} at line ${index + 1}`, { cause: error });
  }
});

if (!comparison.metadata?.createdAt?.startsWith('2026-10-10')) {
  throw new Error(`Expected retained 10 October 2026 dataset in ${path.basename(comparisonPath)}`);
}
const id = ({ run, workload, policy }) => `${run}|${workload}|${policy}`;
const rawByTrial = new Map();
for (const request of requests) {
  const key = id(request);
  if (!rawByTrial.has(key)) rawByTrial.set(key, []);
  rawByTrial.get(key).push(request);
}

const trials = comparison.rows.map(row => {
  const raw = rawByTrial.get(id(row));
  if (!raw || raw.length !== row.requests) {
    throw new Error(`Raw request count does not match comparison row ${id(row)}`);
  }
  if (raw.some(request => request.error || request.httpStatus !== 200)) {
    throw new Error(`Retained raw trace contains a failed request in ${id(row)}`);
  }
  const distinctKeys = new Set(raw.map(request => String(request.key))).size;
  return {
    trial_id: `run-${row.run}-${row.workload}-${row.policy}`,
    run: row.run,
    workload: row.workload,
    policy: row.policy,
    requests: row.requests,
    errors: row.errors,
    hits: row.hits,
    hit_ratio_pct: row.hits / row.requests * 100,
    origin_attempts: row.origin_attempts,
    distinct_keys: distinctKeys,
    compulsory_miss_floor: distinctKeys,
    excess_origin_attempts: row.origin_attempts - distinctKeys,
    request_cv: row.request_cv,
    p50_ms: row.p50_ms,
    p95_ms: row.p95_ms,
    p99_ms: row.p99_ms,
  };
});

if (trials.length !== comparison.rows.length || rawByTrial.size !== comparison.rows.length) {
  throw new Error('Comparison rows and raw request trials do not have a one-to-one match');
}

const round = (value, digits = 2) => Number(value.toFixed(digits));
const mean = values => values.reduce((sum, value) => sum + value, 0) / values.length;
const workloads = ['uniform', 'zipf', 'changing_hot', 'cold_burst'];
const policies = ['consistent_hash', 'round_robin', 'adaptive'];
const distinctMeans = Object.fromEntries(workloads.map(workload => {
  const values = [...new Map(trials
    .filter(trial => trial.workload === workload)
    .map(trial => [trial.run, trial.distinct_keys])).values()];
  if (values.length !== comparison.metadata.repetitions) {
    throw new Error(`Unexpected number of repetitions for ${workload}`);
  }
  return [workload, mean(values)];
}));

const expectedDistinct = { zipf: 151, changing_hot: 176.33, uniform: 242.67, cold_burst: 1 };
for (const [workload, expected] of Object.entries(expectedDistinct)) {
  if (round(distinctMeans[workload]) !== expected) {
    throw new Error(`Distinct-key mean mismatch for ${workload}: ${round(distinctMeans[workload])} != ${expected}`);
  }
}

const summaries = workloads.flatMap(workload => policies.map(policy => {
  const selected = trials.filter(trial => trial.workload === workload && trial.policy === policy);
  const nRequests = selected.reduce((sum, trial) => sum + trial.requests, 0);
  const hits = selected.reduce((sum, trial) => sum + trial.hits, 0);
  return {
    workload,
    policy,
    hit_ratio_pct: hits / nRequests * 100,
    origin_attempts_mean: mean(selected.map(trial => trial.origin_attempts)),
    distinct_keys_mean: mean(selected.map(trial => trial.distinct_keys)),
    excess_origin_attempts_mean: mean(selected.map(trial => trial.excess_origin_attempts)),
    p50_ms_mean: mean(selected.map(trial => trial.p50_ms)),
    p95_ms_mean: mean(selected.map(trial => trial.p95_ms)),
  };
}));

const summary = (workload, policy, field) => summaries.find(row => row.workload === workload && row.policy === policy)[field];
const expectedChecks = [
  ['Zipf CH HIT', summary('zipf', 'consistent_hash', 'hit_ratio_pct'), 80.34],
  ['Zipf RR HIT', summary('zipf', 'round_robin', 'hit_ratio_pct'), 65.49],
  ['Zipf adaptive HIT', summary('zipf', 'adaptive', 'hit_ratio_pct'), 76.69],
  ['Zipf CH origin attempts', summary('zipf', 'consistent_hash', 'origin_attempts_mean'), 151],
  ['Zipf RR origin attempts', summary('zipf', 'round_robin', 'origin_attempts_mean'), 265],
  ['Zipf adaptive origin attempts', summary('zipf', 'adaptive', 'origin_attempts_mean'), 179],
  ['Uniform CH HIT', summary('uniform', 'consistent_hash', 'hit_ratio_pct'), 60.89],
  ['Uniform RR HIT', summary('uniform', 'round_robin', 'hit_ratio_pct'), 21.09],
  ['Uniform adaptive HIT', summary('uniform', 'adaptive', 'hit_ratio_pct'), 48.44],
];
for (const [label, actual, expected] of expectedChecks) {
  if (round(actual) !== expected) throw new Error(`${label} mismatch: ${round(actual)} != ${expected}`);
}

const date = new Date().toISOString().slice(0, 10);
const csvPath = path.join(resultsDir, `routing-trials-derived-${date}.csv`);
const jsonPath = path.join(resultsDir, `routing-reproduction-${date}.json`);
const markdownPath = path.join(resultsDir, `routing-reproduction-${date}.md`);
const fields = Object.keys(trials[0]);
const escapeCSV = value => `"${String(value).replaceAll('"', '""')}"`;
const csv = [fields.join(','), ...trials.map(row => fields.map(field => escapeCSV(row[field])).join(','))].join('\n') + '\n';
const markdownTable = (headers, rows) => [
  `| ${headers.join(' | ')} |`,
  `| ${headers.map(() => '---').join(' | ')} |`,
  ...rows.map(row => `| ${row.join(' | ')} |`),
].join('\n');

const markdown = `# Retained routing result reproduction (${date})

Source files (read-only): \`routing-comparison.json\` and \`routing-requests.jsonl\`
(retained 10 October 2026 data). Percentages and means below were regenerated
by \`scripts/reproduce-routing-results.mjs\`; per-trial derived values are in
\`${path.basename(csvPath)}\`.

## HIT ratio and origin-attempt means by workload

HIT ratio is total HIT responses divided by total requests within the three
trials. Attempt and latency columns are arithmetic means across trials.

${markdownTable(
  ['Workload', 'Policy', 'HIT (%)', 'Origin attempts (mean)', 'P50 (ms, mean)', 'P95 (ms, mean)'],
  summaries.map(row => [
    row.workload,
    row.policy,
    row.hit_ratio_pct.toFixed(2),
    row.origin_attempts_mean.toFixed(2),
    row.p50_ms_mean.toFixed(2),
    row.p95_ms_mean.toFixed(2),
  ]),
)}

## Distinct-key compulsory-miss floor

The floor is the number of distinct requested keys in a workload/run trace.
It is counted once per run from the raw request log; identical traces across
policies are not counted as additional repetitions.

${markdownTable(['Workload', 'Distinct keys (mean)', 'Repetitions'], workloads.map(workload => [
  workload,
  distinctMeans[workload].toFixed(2),
  String(comparison.metadata.repetitions),
]))}

## Per-trial derived accounting

Excess origin attempts = origin attempts - distinct-key compulsory-miss floor.
The CSV contains the full per-trial rows and their source identifiers.

${markdownTable(
  ['Run', 'Workload', 'Policy', 'Distinct / floor', 'Origin attempts', 'Excess'],
  trials.map(row => [
    String(row.run),
    row.workload,
    row.policy,
    String(row.distinct_keys),
    String(row.origin_attempts),
    String(row.excess_origin_attempts),
  ]),
)}
`;

const result = {
  metadata: {
    generatedAt: new Date().toISOString(),
    sourceFiles: [path.basename(comparisonPath), path.basename(requestsPath)],
    sourceDatasetCreatedAt: comparison.metadata.createdAt,
    method: 'Distinct keys counted per workload/run from raw JSONL; summary HIT ratio is pooled across equal-size trials; attempts and latency are arithmetic trial means.',
  },
  distinctKeyMeans: distinctMeans,
  summaries,
  trials,
};
await Promise.all([
  fs.writeFile(csvPath, csv),
  fs.writeFile(jsonPath, JSON.stringify(result, null, 2) + '\n'),
  fs.writeFile(markdownPath, markdown),
]);
console.log(JSON.stringify({
  status: 'PASS',
  retainedTrials: trials.length,
  distinctKeyMeans: Object.fromEntries(Object.entries(distinctMeans).map(([key, value]) => [key, round(value)])),
  confirmed: expectedChecks.map(([label, actual]) => `${label} ${round(actual)}`),
  outputs: [csvPath, jsonPath, markdownPath].map(file => path.relative(root, file)),
}, null, 2));
