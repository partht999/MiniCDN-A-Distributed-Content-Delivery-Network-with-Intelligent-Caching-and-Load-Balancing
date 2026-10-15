import fs from 'node:fs/promises';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { performance } from 'node:perf_hooks';
const root=process.cwd(), directory=path.join(root,'sample-content/integration-test');
await fs.mkdir(directory,{recursive:true});
await fs.mkdir(path.join(root,'docs/academic/results'),{recursive:true});
const file=path.join(directory,'asset.txt'), resource='/integration-test/asset.txt';
const results=[];
const check=(name,condition,details={})=>{results.push({name,passed:condition,...details});if(!condition)throw new Error(name);};
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function content(port,url=resource,headers={}) {const response=await fetch(`http://127.0.0.1:${port}${url}`,{headers,signal:AbortSignal.timeout(15000)}); return {http:response.status,body:await response.text(),cache:response.headers.get('x-cache'),edge:response.headers.get('x-edge-node'),etag:response.headers.get('etag')};}
async function purge(){const response=await fetch('http://127.0.0.1:7000/api/v1/purge',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prefixes:['/integration-test/']})});return {http:response.status,body:await response.json()};}
let stopped=false;
try {
  await fs.writeFile(file,'version-one');
  const invalidated=await purge(); check('Three-edge purge acknowledgement',invalidated.http===200 && Object.keys(invalidated.body.details||{}).length===3 && Object.values(invalidated.body.details).every(x=>x==='success'));
  const first=await content(8080), second=await content(8080);
  check('Router-origin body fidelity and MISS to HIT',first.http===200&&first.body==='version-one'&&first.cache==='MISS'&&second.cache==='HIT'&&second.body===first.body);
  const headResponse=await fetch(`http://127.0.0.1:8080${resource}`,{method:'HEAD'});
  check('HEAD uses cached headers without body',headResponse.status===200 && await headResponse.text()==='');
  const conditional=await content(8080,resource,{'If-None-Match':second.etag}); check('Cached ETag conditional GET',conditional.http===304&&conditional.body==='');
  const bypass=await content(8080,resource,{'Authorization':'test-only'}); check('Personalized requests bypass shared cache',bypass.cache==='BYPASS'&&bypass.body==='version-one');
  const missing=await content(8080,'/integration-test/missing.txt'); check('Missing content remains HTTP 404',missing.http===404);
  // Locate a resource variant whose hash owner is definitely edge-1.
  let ownedResource;
  for(let index=0;index<256;index++){const candidate=resource+'?owner='+index;const probe=await content(8080,candidate);if(probe.edge==='edge-1'){ownedResource=candidate;break;}}
  check('Locate edge-1 hash owner before failure',Boolean(ownedResource));
  // Keep one old object on edge-1, then make it miss invalidation while stopped.
  await content(8081);
  execFileSync('docker',['stop','edge-1'],{stdio:'pipe'}); stopped=true;
  const started=performance.now();
  const failover=await content(8080,ownedResource); const recoveryMs=performance.now()-started;
  check('Hard-stopped edge leaves content available',failover.http===200&&failover.body==='version-one'&&failover.edge!=='edge-1',{requestLatencyMs:recoveryMs});
  check('Post-stop request completes within five-second target',recoveryMs<5000,{requestLatencyMs:recoveryMs,note:'This times one request after docker stop completes; it is not a full detection-delay distribution.'});
  await fs.writeFile(file,'version-two');
  const partial=await purge();
  check('Unavailable edge purge reports partial failure',partial.http===502&&partial.body.details?.['edge-1']==='failed');
  execFileSync('docker',['start','edge-1'],{stdio:'pipe'}); stopped=false;
  let after;
  for(let attempt=0;attempt<30;attempt++) {try {after=await content(8081);if(after.body==='version-two')break;}catch{} await delay(500);}
  check('Returning edge retrieves current content',after?.body==='version-two',{note:'Container restart clears memory too; disconnected-node check separately tests generation-only recovery.'});
  await content(8081);
  const inspected=JSON.parse(execFileSync('docker',['inspect','edge-1'],{encoding:'utf8'}))[0];
  const network=Object.keys(inspected.NetworkSettings.Networks)[0];
  if(!network)throw new Error('Missing edge experiment network');
  execFileSync('docker',['network','disconnect',network,'edge-1'],{stdio:'pipe'});
  try {
    await fs.writeFile(file,'version-three');
    const partitionedPurge=await purge(); check('Disconnected edge purge reports failure',partitionedPurge.http===502);
  } finally {execFileSync('docker',['network','connect',network,'edge-1'],{stdio:'pipe'});}
  // Network disconnection preserves memory and prevents delayed purge delivery.
  // Wait for the five-second heartbeat to
  // reconcile the retained invalidation generation before checking content.
  await delay(6500);
  const reconciled=await content(8081);
  check('Missed invalidation recovered without process restart',reconciled.body==='version-three',{cache:reconciled.cache});
  const afterInspect=JSON.parse(execFileSync('docker',['inspect','edge-1'],{encoding:'utf8'}))[0];
  check('Partition recovery preserves edge process',afterInspect.State.StartedAt===inspected.State.StartedAt);
  const grafana=await fetch('http://127.0.0.1:3000/api/health').then(r=>r.json());check('Grafana database healthy',grafana.database==='ok');
  const prom=await fetch('http://127.0.0.1:9090/api/v1/targets').then(r=>r.json());check('Prometheus targets recovered',prom.status==='success' && prom.data.activeTargets.some(t=>t.labels.instance==='edge-2:8080'&&t.health==='up'));
} finally {
  if(stopped)execFileSync('docker',['start','edge-1'],{stdio:'pipe'});
  await fs.writeFile(path.join(root,'docs/academic/results/integration-check.json'),JSON.stringify({executedAt:new Date().toISOString(),results},null,2));
  console.log(JSON.stringify(results,null,2));
}
