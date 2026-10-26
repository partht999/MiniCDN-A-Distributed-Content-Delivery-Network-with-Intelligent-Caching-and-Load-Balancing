# Routing sweep analysis (routing-analysis-2026-10-26)

Source trial files: `routing-sweep-2026-10-25T19-23-50-602Z.json`, `routing-sweep-2026-10-26T04-11-47-711Z.json`.

Intervals are over independent trial-level values. HIT ratio, origin attempts,
distinct keys, excess attempts, and request CV use two-sided 95% Student t-intervals:
`mean ± t(0.975, n-1) × sample_sd / sqrt(n)`. P50/P95/P99 latency and error counts use
deterministic 10,000-resample percentile bootstrap intervals for the mean. Percentiles
are computed per trial before intervals are formed; HIT ratio is shown in percentage points.
Request-level spill latency is first reduced to per-trial P50/P95, then summarized
across repetitions. Pooled individual requests are not treated as independent samples.

## Trial metrics by workload and policy

| Workload | Policy | n | HIT (%) | Origin attempts | Distinct / floor | Excess attempts | Request CV | P95 (ms) | Errors |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| changing_hot | adaptive (slack 0) | 10 | 73.03 [72.11, 73.96] | 809.0 [781.2, 836.8] | 248.3 [246.5, 250.1] | 560.7 [534.3, 587.1] | 0.078 [0.064, 0.092] | 81.4 [63.4, 102.0] | 0 |
| changing_hot | adaptive (slack 1) | 10 | 77.57 [76.85, 78.29] | 672.9 [651.2, 694.6] | 248.3 [246.5, 250.1] | 424.6 [404.0, 445.2] | 0.129 [0.115, 0.143] | 75.1 [57.7, 95.5] | 0 |
| changing_hot | adaptive (slack 2) | 10 | 81.73 [81.10, 82.37] | 548.0 [528.9, 567.1] | 248.3 [246.5, 250.1] | 299.7 [281.8, 317.6] | 0.175 [0.161, 0.189] | 64.4 [54.6, 76.0] | 0 |
| changing_hot | adaptive (slack 4) | 10 | 86.40 [85.90, 86.91] | 407.9 [392.7, 423.1] | 248.3 [246.5, 250.1] | 159.6 [145.3, 173.9] | 0.237 [0.229, 0.246] | 63.5 [53.3, 75.6] | 0 |
| changing_hot | adaptive (slack 8) | 10 | 89.29 [88.96, 89.62] | 321.3 [311.4, 331.2] | 248.3 [246.5, 250.1] | 73.0 [64.2, 81.8] | 0.277 [0.266, 0.288] | 56.9 [49.6, 66.0] | 0 |
| changing_hot | adaptive (slack 1000) | 10 | 89.85 [89.51, 90.20] | 304.4 [294.1, 314.7] | 248.3 [246.5, 250.1] | 56.1 [47.1, 65.1] | 0.285 [0.273, 0.296] | 63.3 [51.4, 76.9] | 0 |
| changing_hot | bounded load router local | 10 | 86.63 [86.29, 86.97] | 401.1 [390.9, 411.3] | 248.3 [246.5, 250.1] | 152.8 [142.6, 163.0] | 0.256 [0.244, 0.268] | 82.1 [67.2, 99.2] | 0 |
| changing_hot | consistent hash | 10 | 89.85 [89.50, 90.19] | 304.6 [294.2, 315.0] | 248.3 [246.5, 250.1] | 56.3 [47.3, 65.3] | 0.285 [0.273, 0.296] | 60.1 [50.1, 71.7] | 0 |
| changing_hot | least loaded router local | 10 | 73.16 [72.52, 73.80] | 805.3 [786.1, 824.5] | 248.3 [246.5, 250.1] | 557.0 [539.3, 574.7] | 0.084 [0.069, 0.098] | 102.8 [82.3, 125.3] | 0 |
| changing_hot | round robin | 10 | 70.94 [69.93, 71.95] | 871.8 [841.4, 902.2] | 248.3 [246.5, 250.1] | 623.5 [594.5, 652.5] | 0.000 [0.000, 0.000] | 84.3 [63.6, 107.6] | 0 |
| cold_burst | adaptive (slack 0) | 10 | 99.90 [99.90, 99.90] | 3.0 [3.0, 3.0] | 1.0 [1.0, 1.0] | 2.0 [2.0, 2.0] | 0.161 [0.136, 0.186] | 34.8 [27.3, 42.7] | 0 |
| cold_burst | adaptive (slack 1) | 10 | 99.90 [99.90, 99.90] | 3.0 [3.0, 3.0] | 1.0 [1.0, 1.0] | 2.0 [2.0, 2.0] | 0.328 [0.296, 0.360] | 29.1 [22.2, 37.3] | 0 |
| cold_burst | adaptive (slack 2) | 10 | 99.90 [99.90, 99.90] | 3.0 [3.0, 3.0] | 1.0 [1.0, 1.0] | 2.0 [2.0, 2.0] | 0.508 [0.489, 0.527] | 28.7 [23.4, 34.5] | 0 |
| cold_burst | adaptive (slack 4) | 10 | 99.90 [99.90, 99.90] | 3.0 [3.0, 3.0] | 1.0 [1.0, 1.0] | 2.0 [2.0, 2.0] | 0.791 [0.759, 0.823] | 31.2 [23.4, 40.6] | 0 |
| cold_burst | adaptive (slack 8) | 10 | 99.90 [99.90, 99.90] | 3.0 [3.0, 3.0] | 1.0 [1.0, 1.0] | 2.0 [2.0, 2.0] | 1.196 [1.165, 1.226] | 23.3 [20.1, 27.0] | 0 |
| cold_burst | adaptive (slack 1000) | 10 | 99.97 [99.97, 99.97] | 1.0 [1.0, 1.0] | 1.0 [1.0, 1.0] | 0.0 [0.0, 0.0] | 1.414 [1.414, 1.414] | 24.6 [18.9, 31.8] | 0 |
| cold_burst | bounded load router local | 10 | 99.90 [99.90, 99.90] | 3.0 [3.0, 3.0] | 1.0 [1.0, 1.0] | 2.0 [2.0, 2.0] | 0.589 [0.575, 0.602] | 37.2 [31.1, 44.3] | 0 |
| cold_burst | consistent hash | 10 | 99.97 [99.97, 99.97] | 1.0 [1.0, 1.0] | 1.0 [1.0, 1.0] | 0.0 [0.0, 0.0] | 1.414 [1.414, 1.414] | 23.1 [19.9, 27.6] | 0 |
| cold_burst | least loaded router local | 10 | 99.90 [99.90, 99.90] | 3.0 [3.0, 3.0] | 1.0 [1.0, 1.0] | 2.0 [2.0, 2.0] | 0.154 [0.137, 0.171] | 36.5 [30.3, 43.6] | 0 |
| cold_burst | round robin | 10 | 99.90 [99.90, 99.90] | 3.0 [3.0, 3.0] | 1.0 [1.0, 1.0] | 2.0 [2.0, 2.0] | 0.000 [0.000, 0.000] | 29.4 [22.8, 37.5] | 0 |
| uniform | adaptive (slack 0) | 10 | 30.99 [30.48, 31.50] | 2070.2 [2054.9, 2085.5] | 256.0 [256.0, 256.0] | 1814.2 [1798.9, 1829.5] | 0.019 [0.012, 0.026] | 81.5 [59.4, 116.7] | 0 |
| uniform | adaptive (slack 1) | 10 | 44.24 [43.57, 44.91] | 1672.8 [1652.6, 1693.0] | 256.0 [256.0, 256.0] | 1416.8 [1396.6, 1437.0] | 0.021 [0.012, 0.029] | 74.8 [61.3, 90.7] | 0 |
| uniform | adaptive (slack 2) | 10 | 54.25 [53.64, 54.86] | 1372.4 [1354.1, 1390.7] | 256.0 [256.0, 256.0] | 1116.4 [1098.1, 1134.7] | 0.040 [0.025, 0.055] | 73.3 [61.1, 86.5] | 0 |
| uniform | adaptive (slack 4) | 10 | 65.08 [64.46, 65.69] | 1047.7 [1029.2, 1066.2] | 256.0 [256.0, 256.0] | 791.7 [773.2, 810.2] | 0.069 [0.050, 0.087] | 77.8 [63.7, 93.5] | 0 |
| uniform | adaptive (slack 8) | 10 | 72.47 [71.90, 73.03] | 826.0 [809.0, 843.0] | 256.0 [256.0, 256.0] | 570.0 [553.0, 587.0] | 0.114 [0.093, 0.135] | 79.8 [66.0, 94.5] | 0 |
| uniform | adaptive (slack 1000) | 10 | 72.66 [70.39, 74.93] | 823.0 [748.5, 897.5] | 256.0 [256.0, 256.0] | 567.0 [492.5, 641.5] | 0.121 [0.099, 0.142] | 176.2 [62.4, 384.9] | 19 |
| uniform | bounded load router local | 10 | 69.51 [68.90, 70.12] | 914.7 [896.5, 932.9] | 256.0 [256.0, 256.0] | 658.7 [640.5, 676.9] | 0.098 [0.077, 0.119] | 100.3 [83.7, 119.7] | 0 |
| uniform | consistent hash | 10 | 73.49 [73.15, 73.83] | 795.2 [785.0, 805.4] | 256.0 [256.0, 256.0] | 539.2 [529.0, 549.4] | 0.123 [0.101, 0.144] | 65.1 [57.9, 73.1] | 0 |
| uniform | least loaded router local | 10 | 30.50 [30.04, 30.96] | 2085.0 [2071.2, 2098.8] | 256.0 [256.0, 256.0] | 1829.0 [1815.2, 1842.8] | 0.015 [0.010, 0.019] | 111.0 [89.0, 137.0] | 0 |
| uniform | round robin | 10 | 25.05 [24.35, 25.75] | 2248.6 [2227.6, 2269.6] | 256.0 [256.0, 256.0] | 1992.6 [1971.6, 2013.6] | 0.000 [0.000, 0.000] | 81.0 [63.9, 100.6] | 0 |
| zipf | adaptive (slack 0) | 10 | 74.74 [73.99, 75.50] | 757.7 [735.1, 780.3] | 234.2 [232.1, 236.3] | 523.5 [501.0, 546.0] | 0.084 [0.070, 0.098] | 85.7 [62.1, 114.2] | 0 |
| zipf | adaptive (slack 1) | 10 | 79.62 [78.91, 80.33] | 611.4 [590.1, 632.7] | 234.2 [232.1, 236.3] | 377.2 [356.3, 398.1] | 0.144 [0.133, 0.155] | 79.0 [58.9, 104.7] | 0 |
| zipf | adaptive (slack 2) | 10 | 83.70 [83.28, 84.11] | 489.1 [476.6, 501.6] | 234.2 [232.1, 236.3] | 254.9 [242.0, 267.8] | 0.184 [0.167, 0.201] | 76.6 [53.7, 107.6] | 0 |
| zipf | adaptive (slack 4) | 10 | 88.04 [87.78, 88.29] | 358.9 [351.3, 366.5] | 234.2 [232.1, 236.3] | 124.7 [117.3, 132.1] | 0.251 [0.239, 0.263] | 63.1 [48.7, 87.4] | 0 |
| zipf | adaptive (slack 8) | 10 | 90.48 [90.23, 90.73] | 285.5 [278.0, 293.0] | 234.2 [232.1, 236.3] | 51.3 [45.3, 57.3] | 0.305 [0.293, 0.316] | 57.6 [46.5, 77.5] | 0 |
| zipf | adaptive (slack 1000) | 10 | 90.87 [90.62, 91.11] | 274.0 [266.6, 281.4] | 234.2 [232.1, 236.3] | 39.8 [33.8, 45.8] | 0.313 [0.301, 0.324] | 55.4 [47.9, 65.9] | 0 |
| zipf | bounded load router local | 10 | 87.88 [87.50, 88.25] | 363.7 [352.5, 374.9] | 234.2 [232.1, 236.3] | 129.5 [118.6, 140.4] | 0.268 [0.257, 0.279] | 85.0 [70.2, 102.0] | 0 |
| zipf | consistent hash | 10 | 90.88 [90.62, 91.14] | 273.6 [265.9, 281.3] | 234.2 [232.1, 236.3] | 39.4 [33.0, 45.8] | 0.313 [0.301, 0.324] | 73.3 [49.4, 110.5] | 0 |
| zipf | least loaded router local | 10 | 75.00 [74.00, 76.00] | 750.0 [720.1, 779.9] | 234.2 [232.1, 236.3] | 515.8 [486.0, 545.6] | 0.090 [0.075, 0.104] | 97.8 [80.1, 118.1] | 0 |
| zipf | round robin | 10 | 73.02 [72.41, 73.63] | 809.5 [791.2, 827.8] | 234.2 [232.1, 236.3] | 575.3 [557.3, 593.3] | 0.000 [0.000, 0.000] | 106.2 [65.2, 164.5] | 0 |

## Adaptive slack effect on pooled workloads

Workload-specific means and intervals remain in the CSV. The following table pools
trial values across four workload families; this is a descriptive overall view, not
a workload-standardized population estimate.

| Slack | n trials | HIT (%) | Excess attempts | Request CV | P95 (ms) | Errors |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 40 | 69.67 [61.65, 77.68] | 725.1 [509.1, 941.1] | 0.085 [0.068, 0.103] | 70.9 [58.7, 84.8] | 0 |
| 1 | 40 | 75.33 [68.86, 81.80] | 555.1 [385.3, 725.0] | 0.155 [0.119, 0.192] | 64.5 [54.2, 75.7] | 0 |
| 2 | 40 | 79.90 [74.58, 85.21] | 418.2 [282.5, 554.0] | 0.227 [0.170, 0.283] | 60.8 [51.2, 71.6] | 0 |
| 4 | 40 | 84.85 [80.78, 88.92] | 269.5 [169.9, 369.1] | 0.337 [0.248, 0.425] | 58.9 [50.1, 68.7] | 0 |
| 8 | 40 | 88.03 [84.83, 91.24] | 174.1 [99.4, 248.7] | 0.473 [0.336, 0.610] | 54.4 [45.9, 63.5] | 0 |
| 1000 | 40 | 88.34 [85.10, 91.57] | 165.7 [88.7, 242.8] | 0.533 [0.366, 0.700] | 79.9 [47.8, 136.0] | 19 |

## Adaptive slack 2 spilled versus non-spilled P95

| Workload | Cache status | Spill group | Trials | P95 (ms) |
|---|---|---|---:|---:|
| changing_hot | HIT | non_spilled | 10 | 25.7 [21.6, 30.5] |
| changing_hot | MISS | non_spilled | 10 | 99.7 [74.0, 134.7] |
| changing_hot | HIT | spilled | 10 | 27.6 [22.3, 33.6] |
| changing_hot | MISS | spilled | 10 | 91.0 [73.5, 111.9] |
| cold_burst | HIT | non_spilled | 10 | 28.1 [22.9, 33.8] |
| cold_burst | MISS | non_spilled | 10 | 35.0 [32.5, 38.3] |
| cold_burst | HIT | spilled | 10 | 29.3 [23.8, 35.4] |
| cold_burst | MISS | spilled | 10 | 39.0 [36.8, 41.3] |
| uniform | HIT | non_spilled | 10 | 25.9 [21.6, 30.5] |
| uniform | MISS | non_spilled | 10 | 93.1 [72.9, 114.8] |
| uniform | HIT | spilled | 10 | 33.9 [24.0, 45.7] |
| uniform | MISS | spilled | 10 | 92.0 [70.8, 115.9] |
| zipf | HIT | non_spilled | 10 | 30.8 [21.9, 42.7] |
| zipf | MISS | non_spilled | 10 | 128.7 [78.2, 195.1] |
| zipf | HIT | spilled | 10 | 30.2 [21.2, 41.4] |
| zipf | MISS | spilled | 10 | 126.5 [76.4, 192.6] |

## Figures and underlying data

- Pareto-style excess attempts versus request CV: `figures/routing-analysis-2026-10-26-pareto.svg` and `.pdf`.
- HIT ratio versus slack: `figures/routing-analysis-2026-10-26-hit-ratio.svg` and `.pdf`.
- P95 versus slack: `figures/routing-analysis-2026-10-26-p95.svg` and `.pdf`.
- Spilled versus non-spilled latency: `figures/routing-analysis-2026-10-26-spilled-latency.svg` and `.pdf`.
- Per-condition summary and interval endpoints: `routing-analysis-2026-10-26-summary.csv`.
- Per-trial spill percentiles and summary: `routing-analysis-2026-10-26-spill-trials.csv` and `routing-analysis-2026-10-26-spill-summary.csv`.

A nonzero request-error count is retained as measured; do not silently exclude those trials.
For any error trial, the reported latency percentile includes completed HTTP responses and
client-side failures as recorded in the trial summary; interpret its tail alongside errors.
