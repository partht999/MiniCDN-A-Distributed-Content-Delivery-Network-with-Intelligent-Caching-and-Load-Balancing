# Technical progress record

This is a factual technical work log, not a completed supervisor meeting form.

10 October 2026: read evaluation rubrics and group proposal, recorded corrected deadlines supplied in chat, collected five primary-source papers, implemented routing baselines/spillover, bounded memory LRU, expired-entry origin validation, response-size admission limit, prefix invalidation and retained purge generation. Added automated regression tests. Prepared SRS/design, experimental harness and subdomain deployment configuration. Docker startup repair required a runtime-directory backup and official in-place update from 4.86.0 to 4.94.0; engine became available again.

10 October 2026, validation: all 16 live integration checks passed, including disconnected-edge purge recovery without process restart. Completed 36 comparison trials (27,648 requests, zero request/body-validation errors). Native Go 1.27 tests and Linux Go 1.21 race tests passed. A request after its owning edge was stopped completed in 567 ms; this is one request, not a failover guarantee. Grafana showed all three active edges. Consistent hashing reduced origin work; adaptive latency results were mixed.

Supervisor review date: to be entered after the actual meeting. Student signatures: blank. Supervisor remarks/signature: blank. Team member contribution confirmation: pending actual team review.
