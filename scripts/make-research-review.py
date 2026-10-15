import json, hashlib
from pathlib import Path
from pypdf import PdfReader
root = Path(__file__).resolve().parents[1]
papers = json.loads((root/'docs/academic/research-papers.json').read_text())
lines = ['# Five-paper research review and implementation feasibility', '',
'Group 21, MiniCDN. Prepared 10 October 2026. This is a focused first literature review, not a systematic state-of-the-art survey. The final report template requires at least 12 papers; seven additional studies remain.', '',
'## Selection and collected data', '',
'These five primary sources cover stable placement, capacity-constrained hashing, cache locality and stampede prevention. They provide algorithmic foundations. Their 1997-2021 publication dates do not establish novelty against current commercial products. PDFs were collected for private team review. URLs, DOI, page count and SHA-256 make the sources traceable. Paper-reported datasets/results are distinguished from MiniCDN measurements.', '']
manifest=[]
for p in papers:
    file=root/'docs/academic/papers'/f"{p['id']}.pdf"
    count=len(PdfReader(file).pages)
    manifest.append({'id':p['id'],'title':p['title'],'source':p['pdf'],'doi':p['doi'],'pages':count,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'collectedOn':'2026-10-10'})
    lines += [f"## {p['id']}: {p['title']}", '',f"{p['authors']}. {p['venue']}. DOI: {p['doi']}. Collected PDF: {count} pages.", '',f"Finding: {p['finding']}", '',f"Applicability limit: {p['limit']}", '',f"What we can do: {p['application']}", '',f"Primary source: [{p['title']}]({p['url']}).", '']
lines += ['## Decision matrix', '',
'| Candidate | Baseline | MiniCDN evidence | Decision |',
'| --- | --- | --- | --- |',
'| Cache locality vs traffic imbalance | Round robin vs consistent hash | Same request trace, cache capacity, client timing, per-edge request CV, origin attempts | Implement and evaluate now |',
'| Request-load-aware spillover | Plain hash | In-flight reservations and configurable slack; compare latency vs cold fills | Experimental heuristic implemented; benchmark required |',
'| Duplicate cold fills | Coordination off vs on | Barrier-controlled 32-client regression and origin counter | Implemented; established technique, not new invention |',
'| Missed invalidation on returning edge | Broadcast only | Retained Redis generation plus heartbeat full flush on mismatch | Implemented conservative recovery; partition test required |',
'| Probabilistic early refresh | TTL + coordinated fill | Extra origin requests, expiry-burst latency and wasted refreshes | Defer until core evaluation is reproducible |', '',
'## Research question and falsifiable hypotheses', '',
'Question: Under finite cache capacity and skewed/changing demand, can a request-load-aware hash spillover rule reduce tail latency or request imbalance without unacceptable additional origin requests?', '',
'H1: Round robin balances request counts better than plain hashing, but may duplicate hot objects across edge caches. H2: Consistent hashing improves locality under some workloads but can concentrate a hot key. H3: Adaptive spillover may trade extra origin fills for lower queueing or imbalance. These are hypotheses; any negative or mixed result is useful and must be reported. A greater-than-85% hit target applies only to an explicitly defined reuse-heavy workload.', '',
'The proposed rule preserves the hash owner unless its in-flight count exceeds the least-loaded candidate by more than a slack of two. It does not enforce an origin budget. An origin-budget-aware variant is a future research direction and must not appear as an implemented USP.', '',
'## Controlled experiment and data schema', '',
'Three policies, three repeated runs, four workloads: uniform, Zipf exponent 1.1, changing hot set, and repeated-key cold burst. Each trial starts with a prefix purge acknowledged by all three edges. Use seed 2100260 plus repetition index, 256 objects of 1024 bytes, 64 KiB body capacity per edge, concurrency 16, 768 requests, 20 ms emulated origin delay and one-hour origin freshness. Rotate policy order each run. No warm-up requests are included. This is a closed-loop single-machine Docker experiment.', '',
'Record individual latency, HTTP status, key, selected edge and cache status. Derive P50/P95/P99 from raw client measurements, successful throughput, response-body validation errors, request CV across all three edges, cache HIT fraction and origin/coalescing counter deltas. Save JSON, CSV and raw JSONL. Counters are sampled directly at each edge before/after each trial; Grafana provides live observability. Report each repeat and mean/range across repeats, not only the best run.', '',
'Caveats: equal body capacity excludes metadata/temporary buffers; equal request counts do not equal CPU load. Closed-loop traffic can hide overload behavior. Origin delay is synthetic, node regions are local labels, and CRC32 virtual-node placement is measured rather than assumed uniform. Cache coalescing changes apparent HIT status of an initial miss, so HIT fraction and actual origin attempts must both be reported. Test failure recovery separately from the no-failure comparison.', '',
'## Proposed project positioning', '',
'MiniCDN is a transparent CDN experiment platform with interchangeable routing policies, observable cache fills, finite storage, invalidation recovery and reproducible comparisons. This is a defensible educational/project value proposition. Five reviewed papers cannot prove that Cloudflare or every modern solution lacks a feature. A scientific novelty claim would require broader literature, commercial documentation review and a clearly superior evaluated mechanism.', '',
'## Reading and final report expansion', '',
'Add at least seven relevant papers before ESE: modern cache eviction/admission, distributed membership/failure detection, invalidation consistency, cooperative caching, and realistic trace-based evaluation. Record exact sources and assumptions. Do not use unrelated template bibliography placeholders. A research-paper manuscript can describe measured results after they exist; publication acceptance and plagiarism evidence cannot be generated as facts.']
(root/'docs/academic/research-review.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
(root/'docs/academic/papers/sources-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Five-paper review and verified source manifest written.')
