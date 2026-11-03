# Retained routing result reproduction (2026-10-25)

Source files (read-only): `routing-comparison.json` and `routing-requests.jsonl`
(retained 10 October 2026 data). Percentages and means below were regenerated
by `scripts/reproduce-routing-results.mjs`; per-trial derived values are in
`routing-trials-derived-2026-10-25.csv`.

## HIT ratio and origin-attempt means by workload

HIT ratio is total HIT responses divided by total requests within the three
trials. Attempt and latency columns are arithmetic means across trials.

| Workload | Policy | HIT (%) | Origin attempts (mean) | P50 (ms, mean) | P95 (ms, mean) |
| --- | --- | --- | --- | --- | --- |
| uniform | consistent_hash | 60.89 | 300.33 | 46.76 | 235.38 |
| uniform | round_robin | 21.09 | 606.00 | 137.44 | 314.62 |
| uniform | adaptive | 48.44 | 396.00 | 80.26 | 232.02 |
| zipf | consistent_hash | 80.34 | 151.00 | 46.72 | 130.29 |
| zipf | round_robin | 65.49 | 265.00 | 50.98 | 145.99 |
| zipf | adaptive | 76.69 | 179.00 | 55.04 | 161.79 |
| changing_hot | consistent_hash | 77.04 | 176.33 | 56.97 | 198.89 |
| changing_hot | round_robin | 59.29 | 312.67 | 61.94 | 243.17 |
| changing_hot | adaptive | 71.53 | 218.67 | 71.59 | 265.13 |
| cold_burst | consistent_hash | 99.87 | 1.00 | 44.29 | 118.16 |
| cold_burst | round_robin | 99.61 | 3.00 | 53.06 | 113.99 |
| cold_burst | adaptive | 99.61 | 3.00 | 53.71 | 195.50 |

## Distinct-key compulsory-miss floor

The floor is the number of distinct requested keys in a workload/run trace.
It is counted once per run from the raw request log; identical traces across
policies are not counted as additional repetitions.

| Workload | Distinct keys (mean) | Repetitions |
| --- | --- | --- |
| uniform | 242.67 | 3 |
| zipf | 151.00 | 3 |
| changing_hot | 176.33 | 3 |
| cold_burst | 1.00 | 3 |

## Per-trial derived accounting

Excess origin attempts = origin attempts - distinct-key compulsory-miss floor.
The CSV contains the full per-trial rows and their source identifiers.

| Run | Workload | Policy | Distinct / floor | Origin attempts | Excess |
| --- | --- | --- | --- | --- | --- |
| 0 | uniform | consistent_hash | 239 | 288 | 49 |
| 0 | uniform | round_robin | 239 | 595 | 356 |
| 0 | uniform | adaptive | 239 | 381 | 142 |
| 0 | zipf | consistent_hash | 151 | 151 | 0 |
| 0 | zipf | round_robin | 151 | 259 | 108 |
| 0 | zipf | adaptive | 151 | 175 | 24 |
| 0 | changing_hot | consistent_hash | 178 | 178 | 0 |
| 0 | changing_hot | round_robin | 178 | 309 | 131 |
| 0 | changing_hot | adaptive | 178 | 215 | 37 |
| 0 | cold_burst | consistent_hash | 1 | 1 | 0 |
| 0 | cold_burst | round_robin | 1 | 3 | 2 |
| 0 | cold_burst | adaptive | 1 | 3 | 2 |
| 1 | uniform | round_robin | 243 | 613 | 370 |
| 1 | uniform | adaptive | 243 | 394 | 151 |
| 1 | uniform | consistent_hash | 243 | 301 | 58 |
| 1 | zipf | round_robin | 160 | 285 | 125 |
| 1 | zipf | adaptive | 160 | 182 | 22 |
| 1 | zipf | consistent_hash | 160 | 160 | 0 |
| 1 | changing_hot | round_robin | 176 | 320 | 144 |
| 1 | changing_hot | adaptive | 176 | 221 | 45 |
| 1 | changing_hot | consistent_hash | 176 | 176 | 0 |
| 1 | cold_burst | round_robin | 1 | 3 | 2 |
| 1 | cold_burst | adaptive | 1 | 3 | 2 |
| 1 | cold_burst | consistent_hash | 1 | 1 | 0 |
| 2 | uniform | adaptive | 246 | 413 | 167 |
| 2 | uniform | consistent_hash | 246 | 312 | 66 |
| 2 | uniform | round_robin | 246 | 610 | 364 |
| 2 | zipf | adaptive | 142 | 180 | 38 |
| 2 | zipf | consistent_hash | 142 | 142 | 0 |
| 2 | zipf | round_robin | 142 | 251 | 109 |
| 2 | changing_hot | adaptive | 175 | 220 | 45 |
| 2 | changing_hot | consistent_hash | 175 | 175 | 0 |
| 2 | changing_hot | round_robin | 175 | 309 | 134 |
| 2 | cold_burst | adaptive | 1 | 3 | 2 |
| 2 | cold_burst | consistent_hash | 1 | 1 | 0 |
| 2 | cold_burst | round_robin | 1 | 3 | 2 |
