import fs from 'node:fs/promises';
import path from 'node:path';
import { performance } from 'node:perf_hooks';

const seed = 2100260, objects = 256, requests = 768, concurrency = 16;
const repetitions = Number(process.env.REPETITIONS || 3);
const root = process.cwd();
const policies = [['consistent_hash',8080],['round_robin',8084],['adaptive',8085]];
await fs.mkdir(path.join(root,'sample-content/benchmark'), {recursive:true});
await fs.mkdir(path.join(root,'docs/academic/results'), {recursive:true});
for (let i=0;i<objects;i++) await fs.writeFile(path.join(root,`sample-content/benchmark/${i}.txt`), `${i}:`.padEnd(1024,'x'));

function random(initial) { let state=initial>>>0; return () => { state=(Math.imul(1664525,state)+1013904223)>>>0; return state/4294967296; }; }
function trace(workload, run) {
  const rng=random(seed+run), weights=Array.from({length:objects},(_,i)=>1/(i+1)**1.1);
  const total=weights.reduce((a,b)=>a+b,0);
  return Array.from({length:requests}, (_,index)=> {
    if(workload==='uniform') return Math.floor(rng()*objects);
    if(workload==='cold_burst') return 0;
    let value=rng()*total, key=objects-1;
    for(let i=0;i<objects;i++){ value-=weights[i]; if(value<=0){key=i;break;} }
    return workload==='changing_hot' && index>=requests/2 ? (key+128)%objects : key;
  });
}
async function counters() {
  let origin=0, coalesced=0;
  for(const port of [8081,8082,8083]) {
    const response=await fetch(`http://127.0.0.1:${port}/metrics`);
    if(!response.ok) throw new Error('edge metrics unavailable');
    const text=await response.text();
    for(const line of text.split('\n')) {
      if(line.startsWith('cdn_origin_requests_total{')) origin+=Number(line.split(' ').at(-1));
      if(line.startsWith('cdn_coalesced_requests_total{')) coalesced+=Number(line.split(' ').at(-1));
    }
  }
  return {origin,coalesced};
}
const rows=[], raw=[];
for(let run=0;run<repetitions;run++) for(const workload of ['uniform','zipf','changing_hot','cold_burst']) {
  const keys=trace(workload,run);
  // Rotate order between repetitions to reduce fixed ordering bias.
  const order=policies.slice(run%3).concat(policies.slice(0,run%3));
  for(const [policy,port] of order) {
    const health=await fetch(`http://127.0.0.1:${port}/health`).then(r=>r.json());
    if(health.routing_mode!==policy) throw new Error(`Wrong policy on ${port}`);
    const purge=await fetch('http://127.0.0.1:7000/api/v1/purge', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prefixes:['/benchmark/']})}).then(async r=>({code:r.status,body:await r.json()}));
    if(purge.code!==200 || Object.keys(purge.body.details||{}).length!==3 || Object.values(purge.body.details).some(v=>v!=='success')) throw new Error(`Purge not acknowledged by three edges: ${JSON.stringify(purge)}`);
    const before=await counters(), latencies=[], edges={}, statuses={}; let errors=0, next=0;
    const started=performance.now();
    await Promise.all(Array.from({length:concurrency},async()=>{
      while(next<keys.length) {
        const index=next++, key=keys[index], begin=performance.now();
        try {
          const response=await fetch(`http://127.0.0.1:${port}/benchmark/${key}.txt`);
          const body=await response.text(), ms=performance.now()-begin;
          latencies.push(ms);
          const edge=response.headers.get('x-edge-node')||'none', status=response.headers.get('x-cache')||'none';
          edges[edge]=(edges[edge]||0)+1; statuses[status]=(statuses[status]||0)+1;
          if(response.status!==200 || body.length!==1024 || !body.startsWith(`${key}:`)) errors++;
          raw.push({run,workload,policy,index,key,ms,edge,status,httpStatus:response.status});
        } catch(error) { errors++; raw.push({run,workload,policy,index,key,error:String(error)}); }
      }
    }));
    const seconds=(performance.now()-started)/1000, after=await counters();
    latencies.sort((a,b)=>a-b);
    const percentile=p=>latencies[Math.max(0,Math.ceil(p*latencies.length)-1)]||null;
    const counts=[...Object.values(edges)], average=counts.reduce((a,b)=>a+b,0)/3;
    const variance=[...counts,...Array(3-counts.length).fill(0)].reduce((a,b)=>a+(b-average)**2,0)/3;
    const row={run,workload,policy,requests,errors,seconds,rps:(requests-errors)/seconds,p50_ms:percentile(.5),p95_ms:percentile(.95),p99_ms:percentile(.99),hits:statuses.HIT||0,misses:statuses.MISS||0,revalidated:statuses.REVALIDATED||0,origin_attempts:after.origin-before.origin,coalesced:after.coalesced-before.coalesced,request_cv:Math.sqrt(variance)/average,edges};
    rows.push(row); console.log(JSON.stringify(row));
    await fs.writeFile(path.join(root,'docs/academic/results/routing-comparison.json'),JSON.stringify({metadata:{seed,objects,objectBytes:1024,cacheBodyBytesPerEdge:65536,concurrency,repetitions,originDelayMs:20,cacheTTLSeconds:3600,warmupRequests:0,method:'closed-loop, cold cache per trial; single machine Docker; no network impairment',createdAt:new Date().toISOString()},rows},null,2));
  }
}
await fs.writeFile(path.join(root,'docs/academic/results/routing-requests.jsonl'),raw.map(r=>JSON.stringify(r)).join('\n')+'\n');
const columns=['run','workload','policy','requests','errors','seconds','rps','p50_ms','p95_ms','p99_ms','hits','misses','origin_attempts','coalesced','request_cv'];
await fs.writeFile(path.join(root,'docs/academic/results/routing-comparison.csv'),[columns.join(','),...rows.map(r=>columns.map(k=>r[k]).join(','))].join('\n')+'\n');
