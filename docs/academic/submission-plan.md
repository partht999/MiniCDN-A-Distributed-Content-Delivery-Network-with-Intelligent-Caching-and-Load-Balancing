# MiniCDN delivery plan and evaluation evidence

Updated 10 October 2026. Dates below were supplied by Jaynish in chat; the attached marksheets contain blank date fields. The marksheets are evaluation context, not instructions to fabricate grades, signatures, meetings, publication acceptance, or completed results.

| Review | Deadline | Evaluation | Evidence to prepare |
| --- | --- | --- | --- |
| Phase I | 17 August 2026 | Guide | Problem statement, related work, planning, presentation |
| Phase II | 2 September 2026 | Guide | SRS (10 marks), UML (5), algorithm design (5), presentation (5) |
| Phase III | 30 September 2026 | Guide | Module coding (10), Git setup (5), branching/commit rules (5), presentation (5) |
| Phase IV | 12 October 2026 | Guide | Integration (10), functional/nonfunctional tests (5), report (5), presentation (5) |
| ESE | 2 November 2026 | Industry expert/alumni | Definition (20), presentation/demo (20), work done (30), Q&A (20), poster/research paper (10) |

The first three dates have passed. That does not establish whether those evaluations/submissions happened. Phase IV is the immediate priority. ESE passing mark in the supplied sheet is 40/100.

## Submission scope

Deliver a reproducible static-content CDN prototype with origin, Redis control plane, three Go edges, three routing policies, bounded memory LRU, TTL and conditional validation, duplicate-fill suppression, targeted/prefix invalidation, reconnect invalidation recovery, and Grafana/Prometheus. Compare policies under identical seeded workloads. Treat measurable improvements as hypotheses until benchmark data exists.

The initial proposal also mentions a disk tier. It remains an implementation gap and must not be described as complete. HTTP/3, Wasm, gossip, predictive prefetch, peer caching, dynamic virtual nodes, regional placement, and switching LRU/LFU are separate extensions, not mandatory implications of the phrase intelligent caching. Confirm any guide-required extension before changing the declared scope.

## 10-12 October: Phase IV recovery schedule

These are proposed work slots, not invented historical meetings or official extra deadlines.

1. 10 October: repair Docker, finish core policies/cache correctness, collect five papers, finish SRS/UML/algorithm descriptions and deployment configuration.
2. 11 October: run functional integration and repeated workload comparison, exercise node failure and missed purge recovery, capture Grafana evidence, finish report and presentation.
3. 12 October: freeze tested revision, rehearse a short repeatable demo, verify submitted artifacts and guide's required format. Use local demo if public hosting is not ready.

## 13 October-2 November: ESE

Expand the literature survey from five deeply reviewed papers to at least 12, as required by the supplied Overleaf template. Add recent work and explicit comparison assumptions. Complete the 25-40 page report, architecture/UML, measured results, limitations, budget, references, actual plagiarism report, and poster/research-paper material. The template's sample electrical references are unrelated placeholders and must be replaced. Certificates, signatures, acceptance evidence and plagiarism results require real human/institutional records.

Suggested sequence: 13-18 October additional literature and any approved disk tier; 19-24 October broader validation and sensitivity study; 25-29 October report/poster/public dashboard; 30 October-1 November viva practice and backup demo. These are proposed team milestones.

## Team records

Group 21: Jaynish Thakar (2024300260), Anshul Warade (2023300262), Parth Thakkar (2025301033). Faculty guide: Dr. Sudhir N. Dhage. Names/UCIDs come from the supplied group PDF.

Suggested responsibility split for team approval: routing/experiments; cache/control/testing; report/dashboard/presentation. Record the actual owner, commits and review notes; do not assign fictional contributions retrospectively. Weekly form should use real meeting dates and actual supervisor feedback, with signatures left for the signatories.

## Completion ledger

- [x] Extract/read supplied rubrics and group proposal; record corrected deadlines.
- [x] Implement round robin, consistent hashing and request-load-aware spillover.
- [x] Add bounded response-body LRU, object streaming limit, expired-object validation, prefix purge.
- [x] Persist purge generation in Redis and flush missed invalidations on heartbeat (implementation).
- [x] Verify generation recovery and concurrency with tests and live integration (16 checks passed).
- [x] Complete Docker startup recovery, container build, compatibility/race tests.
- [x] Collect full five-paper sources and complete cited research report.
- [x] Run comparison and node-failure experiments; save raw traces and environment metadata (36 trials, 27,648 requests, zero request errors).
- [x] Finish Phase IV report, UML, presentation and Grafana screenshots using actual results.
- [ ] Deploy to the chosen Render Free service, connect minicdn.jaynishthakar.tech, verify HTTPS/authentication. Domain choice supersedes the earlier metrics subdomain proposal.
- [ ] Final ESE report: 12 papers minimum, 25-40 pages, poster/research paper, plagiarism proof and signatures.
