import fs from 'node:fs/promises';
import path from 'node:path';
import { Presentation, PresentationFile } from '@oai/artifact-tool';
import { resolvePresentationFont, applyPresentationChartFont, finalizePresentation } from 'file:///C:/Users/jayni/.codex/plugins/cache/openai-primary-runtime/presentations/26.1007.11041/skills/presentations/container_tools/artifact_tool_utils.mjs';
const root=process.cwd(), build=path.join(root,'tmp/presentation-build');
const skill='C:/Users/jayni/.codex/plugins/cache/openai-primary-runtime/presentations/26.1007.11041/skills/presentations';
const python='C:/Users/jayni/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const data=JSON.parse(await fs.readFile(path.join(root,'docs/academic/results/routing-comparison.json'),'utf8'));
if(data.rows.length!==36 || data.rows.some(r=>r.errors)) throw new Error('Comparison is incomplete or has errors');
const p=Presentation.create({slideSize:{width:1280,height:720}}), font=resolvePresentationFont();
const ink='#14384A', teal='#176B79', grey='#52747E';
function text(s,value,x,y,w,h,size=28,bold=false,color=ink){
 const shape=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 shape.text=value;shape.text.style={typeface:font,fontSize:size,bold,color};shape.text.insets=0;return shape;
}
function slide(title,notes='') { const s=p.slides.add();s.background.fill='#FFFFFF';text(s,title,64,45,1152,85,40,true);text(s,'MiniCDN | Group 21 | Phase IV | 12 October 2026',64,676,1000,25,17,false,grey);text(s,String(p.slides.items.length),1160,676,55,25,17,false,grey);s.speakerNotes.text=notes;return s; }
function lines(s,items,y=170){items.forEach((v,i)=>text(s,v,72,y+i*94,1110,83,28));}
function table(s,values,widths,y=170,h=390,size=23){const t=s.tables.add({rows:values.length,columns:values[0].length,left:64,top:y,width:1152,height:h,values,columnWidths:widths});for(let r=0;r<values.length;r++)for(let c=0;c<values[0].length;c++){const cell=t.getCell(r,c);cell.text.style={typeface:font,fontSize:size,color:ink,bold:r===0};cell.fill=r===0?'#E1EFF2':'#FFFFFF';}return t;}
let s=slide('MiniCDN','Names and UCIDs: supplied Group 21 proposal. Dates: user-confirmed evaluation schedule. Prepared on 10 October 2026.');
text(s,'Cache locality, request balance\nand failure recovery',64,190,1130,155,52,true);
text(s,'Jaynish Thakar • Anshul Warade • Parth Thakkar',64,430,1140,58,27);
text(s,'Guide: Dr. Sudhir N. Dhage',64,510,1100,45,27,false,teal);
s=slide('Problem and project contribution');
lines(s,['Repeated content should reuse cached copies; hot keys can concentrate requests.','Compare routing policies using identical requests, cache budgets and origin delay.','Expose latency, origin work and failures in a reproducible Go + Docker system.','Contribution: transparent experimental evidence and recovery mechanisms.']);
s.speakerNotes.text='No claim that Cloudflare lacks these algorithms or that this implementation is globally novel. The contribution is a reproducible student system and measured tradeoffs.';
s=slide('Five papers and implementation decisions');
table(s,[['Paper','What we investigate'],['Karger et al., 1997','Consistent hashing and content locality'],['Mirrokni et al., 2018','Load limits; our heuristic has no theorem guarantee'],['Chen et al., 2021','Avoid cascaded overflow; measure spillover costs'],['Archer et al., 2019','Cache benefit alongside request balance'],['Vattani et al., 2015','Stampedes; singleflight implemented, XFetch deferred']],[440,712],160,430,22);
s.speakerNotes.text='Primary sources: https://people.csail.mit.edu/karger/Papers/web.pdf ; https://arxiv.org/abs/1608.01350 ; https://ojs.aaai.org/index.php/AAAI/article/view/16517 ; https://research.google/pubs/cache-aware-load-balancing-of-data-center-applications/ ; https://www.vldb.org/pvldb/vol8/p886-vattani.pdf . See research-review.md for full citations and method distinctions.';
s=slide('Routing policies');
table(s,[['Policy','Selection','Expected tradeoff'],['Round robin','Rotate across healthy edges','Even request count; duplicate copies'],['Consistent hashing','Keep key on ring owner','Locality; hot-key concentration'],['Adaptive','Spill when owner load exceeds minimum + 2','Lower imbalance; extra misses possible']],[250,430,472],160,360,24);
text(s,'Load = current in-flight requests, not bytes, CPU or object count',64,560,1150,70,27,false,teal);
s=slide('System architecture');
function node(label,x,y,w=260,h=78){const v=s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill:'#E1EFF2',line:{fill:teal,width:1}});v.text=label;v.text.style={typeface:font,fontSize:25,color:ink};return v;}
const client=node('Client',70,170),router=node('Router',440,170),control=node('Control + Redis',840,170,345);
const e1=node('Edge 1: LRU + fills',100,350,295),e2=node('Edge 2: LRU + fills',490,350,295),e3=node('Edge 3: LRU + fills',880,350,295),origin=node('Origin',490,525,295);
function connect(a,b,fromSide='bottom',toSide='top'){s.shapes.connect(a,b,{kind:'elbow',fromSide,toSide,line:{fill:grey,width:2},tail:{type:'arrow',width:'med',length:'med'}});}
connect(client,router,'right','left');connect(router,control,'right','left');[e1,e2,e3].forEach(e=>{connect(router,e);connect(e,origin);});
text(s,'Prometheus scrapes routers and edges; Grafana displays the metrics',64,620,1152,40,24,false,teal);
s.speakerNotes.text='Editable component view of the implemented local Docker system. Control discovers/registers nodes and coordinates purge generations. Redis is persistent. Origin and edge cache bodies are the data path. Three routers are used by the experiment; one policy is exercised per trial.';
s=slide('Cache and control changes');
lines(s,['Bounded memory LRU and oversized-object streaming keep cached bodies within budget.','Per-key fill gates suppress duplicate origin work on one edge.','TTL + ETag validation renew expired content; private responses bypass shared caching.','Redis purge generations recover missed invalidations on successful heartbeats.']);
s.speakerNotes.text='Purges may wait for requests holding the cache read lock. Heartbeat recovery is eventual; no distributed gossip is implemented. No persistent disk cache is implemented.';
s=slide('Experiment method');
lines(s,['36 trials: 3 policies × 4 workloads × 3 repetitions; 27,648 requests.','256 one-KiB objects; each edge caches 64 KiB; concurrency 16.','Uniform, Zipf, changing hot set and one-key cold burst; seeded request traces.','Cold cache each trial; 20 ms synthetic origin delay; single-machine Docker.']);
s.speakerNotes.text=JSON.stringify(data.metadata)+'\nClosed-loop test, no regional network impairment, no confidence interval from only three repetitions. Policy order rotates per repetition. All 36 trials had zero request/body-validation errors.';
const workloads=['uniform','zipf','changing_hot','cold_burst'], labels=['Uniform','Zipf','Changing hot','Cold burst'];
const policies=['consistent_hash','round_robin','adaptive'],names=['Consistent hash','Round robin','Adaptive'],fills=['#176B79','#B86B38','#6B70AA'];
function mean(w,policy,k){const a=data.rows.filter(r=>r.workload===w&&r.policy===policy);return a.reduce((sum,r)=>sum+r[k],0)/a.length;}
function chart(s,key){const c=s.charts.add('bar',{position:{left:64,top:150,width:1152,height:430},categories:labels,series:policies.map((policy,i)=>({name:names[i],values:workloads.map(w=>Number(mean(w,policy,key).toFixed(1))),fill:fills[i]})),hasLegend:true,legend:{textStyle:{fontSize:22}},xAxis:{textStyle:{fontSize:22}},yAxis:{textStyle:{fontSize:22},majorGridlines:{style:'solid',fill:'#D5E2E5',width:1}}});applyPresentationChartFont(c,{fontFamily:font});s.speakerNotes.text='Source: docs/academic/results/routing-comparison.json. Values are arithmetic means of three trial-level measurements per workload/policy, rounded to one decimal for the chart. Full measurements remain in JSON/CSV and below.\n'+JSON.stringify(workloads.map(w=>({workload:w,values:policies.map(policy=>({policy,mean:mean(w,policy,key),runs:data.rows.filter(r=>r.workload===w&&r.policy===policy).map(r=>r[key])}))})));}
s=slide('Origin fetches per 768 requests');chart(s,'origin_attempts');text(s,'Consistent hashing used fewer origin fetches in these workloads',64,600,1152,56,27,false,teal);
s=slide('P95 request latency (milliseconds)');chart(s,'p95_ms');text(s,'Host variability and workload affect latency; adaptive did not win consistently',64,600,1152,56,25,false,teal);
s=slide('Integration and failure evidence');
lines(s,['16 live checks passed, including HIT/MISS, HEAD, ETag and bypass behavior.','A request after its edge was stopped completed in 567 ms through fallback.','A disconnected edge missed a purge, then recovered without restarting its process.','Go tests and Linux Go 1.21 race tests passed; cold-burst regression repeated 10 times.']);
s.speakerNotes.text='Source: docs/academic/results/integration-check.json, executed 10 October 2026. The 567 ms measurement starts after docker stop finishes. It is one request, not a failover detection-delay distribution or availability guarantee. Coalescing regression: 32 concurrent requests, 32 baseline origin fetches vs 1 coordinated fetch.';
s=slide('Demonstration');
lines(s,['Grafana: http://localhost:3000/d/minicdn-dashboard/mini-cdn-overview','Request content twice and inspect cache responses and origin counters.','Show policy comparison CSV; stop an edge and demonstrate fallback.','Show partial purge failure and heartbeat recovery; restore the edge.']);
s=slide('Remaining deliverables');
lines(s,['Phase IV, 12 October: report, integration evidence, presentation and rehearsed demo.','ESE, 2 November: 12-paper survey, 25–40 page report, poster and viva preparation.','Disk cache, broader workload sensitivity and multi-host testing remain open.','metrics.jaynishthakar.tech: deployment files prepared; VPS and DNS still needed.']);
s.speakerNotes.text='Evaluation dates from user chat; rubrics have blank date fields. Institution requires real plagiarism evidence and signatures. No VPS purchased, DNS changed or public dashboard deployed. Hosting should follow a stable local demo and authentication checks.';
await fs.mkdir(build,{recursive:true});await fs.mkdir(path.join(root,'output/presentations'),{recursive:true});
const candidate=path.join(build,'candidate.pptx');
if(!process.argv.includes('--finalize-only')) {
 for(let i=0;i<p.slides.items.length;i++){const b=await p.export({slide:p.slides.items[i],format:'png',scale:1});await fs.writeFile(path.join(build,`slide-${i+1}.png`),new Uint8Array(await b.arrayBuffer()));}
 await(await PresentationFile.exportPptx(p)).save(candidate);
}
await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath:path.join(root,'output/presentations/MiniCDN-Phase-IV-Reviewed.pptx'),pythonExecutable:python,integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit','--require-native-table-slide','3','--require-native-table-slide','4'],fontPolicy:{basis:'design',families:[font]},requiredNativeTableOwnerSlides:[3,4],requiredNativeChartOwnerSlides:[8,9],materializeLiteralChartWorkbooks:true,verifyArtifactToolImport:true,receiptPath:path.join(build,'validation-reviewed.json')});
console.log('Created 12-slide Phase IV deck');
