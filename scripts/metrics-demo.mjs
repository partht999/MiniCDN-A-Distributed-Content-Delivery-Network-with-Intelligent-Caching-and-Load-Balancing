// Bounded local traffic for the Grafana walkthrough. This is not a load benchmark.
const base = 'http://localhost:8080';
const paths = ['/', '/index.html', '/assets/app.js', '/assets/logo.png'];
const results = {requests: 0, errors: 0, cacheStatus: {}, edgeNodes: {}};
const runID = Date.now();

async function request(path) {
  results.requests++;
  try {
    const response = await fetch(base + path, {signal: AbortSignal.timeout(10000)});
    await response.arrayBuffer();
    if (!response.ok) results.errors++;
    const cache = response.headers.get('x-cache') || 'UNKNOWN';
    const edge = response.headers.get('x-edge-node') || 'UNKNOWN';
    results.cacheStatus[cache] = (results.cacheStatus[cache] || 0) + 1;
    results.edgeNodes[edge] = (results.edgeNodes[edge] || 0) + 1;
  } catch (error) {
    results.errors++;
    console.error(error.message);
  }
}

for (let round = 0; round < 10; round++) {
  // A fresh query creates one cold key per round without purging existing entries.
  await Promise.all(Array.from({length: 32}, () => request(`/assets/app.js?metrics_demo=${runID}-${round}`)));
  await Promise.all(paths.flatMap(path => Array.from({length: 8}, () => request(path))));
  await new Promise(resolve => setTimeout(resolve, 2000));
}
console.log(JSON.stringify(results, null, 2));
if (results.errors) process.exitCode = 1;
