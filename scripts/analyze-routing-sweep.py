import csv
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path.cwd()
RESULTS = ROOT / "docs" / "academic" / "results"
FIGURES = RESULTS / "figures"
FIGURES.mkdir(parents=True, exist_ok=True)

T95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
    7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179,
    13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101,
    19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064,
    25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
    31: 2.040, 32: 2.037, 33: 2.034, 34: 2.032, 35: 2.030, 36: 2.028,
    37: 2.026, 38: 2.024, 39: 2.023, 40: 2.021,
}
WORKLOAD_COLORS = {
    "uniform": "#2878B5",
    "zipf": "#E07B39",
    "changing_hot": "#43966E",
    "cold_burst": "#8A69A8",
}
POLICY_MARKERS = {
    "consistent_hash": "o",
    "round_robin": "s",
    "adaptive": "^",
    "least_loaded_router_local": "D",
    "bounded_load_router_local": "P",
}


def confidence_interval(values):
    if not values:
        return None, None, None, 0
    count = len(values)
    average = sum(values) / count
    if count < 2:
        return average, None, None, count
    variance = sum((value - average) ** 2 for value in values) / (count - 1)
    half_width = T95.get(count - 1, 1.96) * math.sqrt(variance) / math.sqrt(count)
    return average, average - half_width, average + half_width, count


def bootstrap_confidence_interval(values, samples=10000):
    if not values:
        return None, None, None, 0
    count = len(values)
    average = sum(values) / count
    if count < 2:
        return average, None, None, count

    rng = random.Random(3102026 + count)
    means = sorted(
        sum(values[rng.randrange(count)] for _ in range(count)) / count
        for _ in range(samples)
    )
    return average, means[int(0.025 * samples)], means[int(0.975 * samples)], count


def metric_interval(metric, values):
    if metric in ("p50_ms", "p95_ms", "p99_ms", "errors"):
        return bootstrap_confidence_interval(values)
    return confidence_interval(values)


def policy_label(row):
    if row["policy"] == "adaptive":
        return f"adaptive (slack {row['slack']})"
    return row["policy"].replace("_", " ")


def fmt_ci(average, low, high, digits=3):
    if average is None:
        return "NA"
    if low is None:
        return f"{average:.{digits}f} (n=1)"
    return f"{average:.{digits}f} [{low:.{digits}f}, {high:.{digits}f}]"


def read_trial_files(paths):
    rows = []
    for file_path in paths:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if data.get("metadata", {}).get("method") is None:
            raise ValueError(f"Missing method metadata in {file_path}")
        rows.extend(data["rows"])
    if not rows:
        raise ValueError("No trial rows were loaded")
    return rows


def summarize_trials(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["workload"], row["policy"], row.get("slack"))].append(row)
    summaries = []
    metrics = [
        ("hit_ratio", 100.0),
        ("origin_attempts", 1.0),
        ("distinct_keys", 1.0),
        ("compulsory_miss_floor", 1.0),
        ("excess_origin_attempts", 1.0),
        ("request_cv", 1.0),
        ("p50_ms", 1.0),
        ("p95_ms", 1.0),
        ("p99_ms", 1.0),
        ("errors", 1.0),
    ]
    for (workload, policy, slack), trials in sorted(groups.items()):
        result = {
            "workload": workload,
            "policy": policy,
            "slack": slack,
            "n_trials": len(trials),
        }
        for metric, multiplier in metrics:
            values = [float(row[metric]) * multiplier for row in trials if row.get(metric) is not None]
            average, low, high, count = metric_interval(metric, values)
            result[f"{metric}_mean"] = average
            result[f"{metric}_ci95_low"] = low
            result[f"{metric}_ci95_high"] = high
            result[f"{metric}_n"] = count
        result["error_requests_total"] = sum(int(row.get("errors", 0)) for row in trials)
        result["trial_ids"] = ";".join(row["trialId"] for row in trials)
        summaries.append(result)
    return summaries


def summarize_spills(paths):
    trial_samples = defaultdict(list)
    for file_path in paths:
        with file_path.open(newline="", encoding="utf-8") as source:
            for request in csv.DictReader(source):
                if request.get("policy") != "adaptive":
                    continue
                if request.get("cacheStatus") not in ("HIT", "MISS"):
                    continue
                if request.get("spilled") not in ("true", "false") or request.get("error"):
                    continue
                key = (
                    request["trialId"], request["workload"], request["policy"],
                    request.get("slack") or "", "spilled" if request["spilled"] == "true" else "non_spilled",
                    request["cacheStatus"],
                )
                trial_samples[key].append(float(request["latencyMs"]))

    trial_percentiles = defaultdict(list)
    per_trial_rows = []
    for (trial_id, workload, policy, slack, spill, cache_status), values in trial_samples.items():
        ordered = sorted(values)
        p50 = ordered[max(0, math.ceil(0.50 * len(ordered)) - 1)]
        p95 = ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]
        key = (workload, policy, slack, spill, cache_status)
        trial_percentiles[key].append((p50, p95))
        per_trial_rows.append({
            "trial_id": trial_id,
            "workload": workload,
            "policy": policy,
            "slack": slack,
            "spill": spill,
            "cache_status": cache_status,
            "request_count": len(values),
            "p50_ms": p50,
            "p95_ms": p95,
        })

    summaries = []
    for (workload, policy, slack, spill, cache_status), pairs in sorted(trial_percentiles.items()):
        p50 = bootstrap_confidence_interval([pair[0] for pair in pairs])
        p95 = bootstrap_confidence_interval([pair[1] for pair in pairs])
        summaries.append({
            "workload": workload,
            "policy": policy,
            "slack": int(slack) if slack else None,
            "spill": spill,
            "cache_status": cache_status,
            "n_trials": len(pairs),
            "p50_ms_mean": p50[0],
            "p50_ms_ci95_low": p50[1],
            "p50_ms_ci95_high": p50[2],
            "p95_ms_mean": p95[0],
            "p95_ms_ci95_low": p95[1],
            "p95_ms_ci95_high": p95[2],
        })
    return per_trial_rows, summaries


def save_csv(file_path, rows):
    if not rows:
        return
    with file_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def save_svg(fig, file_path):
    fig.savefig(file_path, format="svg")
    svg = file_path.read_text(encoding="utf-8")
    file_path.write_text(
        "\n".join(line.rstrip() for line in svg.splitlines()) + "\n",
        encoding="utf-8",
    )


def save_figures(summaries, spill_summaries, prefix):
    by_key = {(row["workload"], row["policy"], row["slack"]): row for row in summaries}

    fig, ax = plt.subplots(figsize=(9, 6))
    for row in summaries:
        x, xl, xh = (row["request_cv_mean"], row["request_cv_ci95_low"], row["request_cv_ci95_high"])
        y, yl, yh = (
            row["excess_origin_attempts_mean"],
            row["excess_origin_attempts_ci95_low"],
            row["excess_origin_attempts_ci95_high"],
        )
        if x is None or y is None:
            continue
        xerr = None if xl is None else [[x - xl], [xh - x]]
        yerr = None if yl is None else [[y - yl], [yh - y]]
        ax.errorbar(
            x, y, xerr=xerr, yerr=yerr, fmt=POLICY_MARKERS.get(row["policy"], "o"),
            color=WORKLOAD_COLORS[row["workload"]], alpha=0.72, capsize=2,
            markersize=6,
        )
    workload_handles = [
        plt.Line2D([], [], color=color, marker="o", linestyle="", label=name.replace("_", " "))
        for name, color in WORKLOAD_COLORS.items()
    ]
    policy_handles = [
        plt.Line2D([], [], color="#555555", marker=marker, linestyle="", label=name.replace("_", " "))
        for name, marker in POLICY_MARKERS.items()
    ]
    first = ax.legend(handles=workload_handles, title="Workload", loc="upper left")
    ax.add_artist(first)
    ax.legend(handles=policy_handles, title="Policy", loc="upper right", fontsize=8)
    ax.set_xlabel("Request-count coefficient of variation (mean; t-interval 95%)")
    ax.set_ylabel("Excess origin attempts per trial (mean; t-interval 95%)")
    ax.set_title("Routing balance versus excess origin work")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    save_svg(fig, FIGURES / f"{prefix}-pareto.svg")
    fig.savefig(FIGURES / f"{prefix}-pareto.pdf", format="pdf")
    plt.close(fig)

    adaptive_slacks = sorted({
        row["slack"] for row in summaries if row["policy"] == "adaptive" and row["slack"] is not None
    })
    for metric, label, name in [
        ("hit_ratio", "HIT ratio (%)", "hit-ratio"),
        ("p95_ms", "P95 latency (ms)", "p95"),
    ]:
        fig, ax = plt.subplots(figsize=(9, 6))
        for workload, color in WORKLOAD_COLORS.items():
            selected = [
                by_key.get((workload, "adaptive", slack))
                for slack in adaptive_slacks
            ]
            selected = [row for row in selected if row is not None]
            if selected:
                x = [row["slack"] for row in selected]
                y = [row[f"{metric}_mean"] for row in selected]
                low = [row[f"{metric}_ci95_low"] for row in selected]
                high = [row[f"{metric}_ci95_high"] for row in selected]
                yerr = [
                    [value - bound if bound is not None else 0 for value, bound in zip(y, low)],
                    [bound - value if bound is not None else 0 for value, bound in zip(y, high)],
                ]
                ax.errorbar(x, y, yerr=yerr, marker="o", capsize=3, color=color, label=workload.replace("_", " "))
            for policy in ("consistent_hash", "round_robin", "least_loaded_router_local", "bounded_load_router_local"):
                base = by_key.get((workload, policy, None))
                if base is not None:
                    ax.axhline(
                        base[f"{metric}_mean"], color=color, linestyle=":" if policy == "consistent_hash" else "--",
                        alpha=0.35,
                    )
        ax.set_xscale("symlog", linthresh=1)
        ax.set_xticks(adaptive_slacks, labels=[str(value) for value in adaptive_slacks])
        ax.set_xlabel("Adaptive spill slack (dotted/dashed lines are non-adaptive baselines)")
        ax.set_ylabel(label)
        ax.set_title(f"{label} versus adaptive slack")
        ax.grid(alpha=0.25)
        ax.legend(title="Workload")
        fig.tight_layout()
        save_svg(fig, FIGURES / f"{prefix}-{name}.svg")
        fig.savefig(FIGURES / f"{prefix}-{name}.pdf", format="pdf")
        plt.close(fig)

    selected_spill = [
        row for row in spill_summaries
        if row["policy"] == "adaptive" and row["slack"] == 2
    ]
    categories = []
    values = []
    errors = []
    for row in selected_spill:
        categories.append(
            f"{row['workload'].replace('_', ' ')}\n{row['cache_status']} {row['spill'].replace('_', ' ')}"
        )
        value = row["p95_ms_mean"]
        low = row["p95_ms_ci95_low"]
        high = row["p95_ms_ci95_high"]
        values.append(value)
        errors.append((value - low, high - value) if low is not None else (0, 0))
    fig, ax = plt.subplots(figsize=(12, 6))
    palette = ["#43966E" if "spilled" in label and "non spilled" not in label else "#2878B5" for label in categories]
    ax.bar(range(len(values)), values, color=palette, alpha=0.82)
    for index, (value, (low, high)) in enumerate(zip(values, errors)):
        ax.errorbar(index, value, yerr=[[low], [high]], fmt="none", ecolor="#222222", capsize=3)
    ax.set_xticks(range(len(categories)), labels=categories, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Per-trial request P95 (ms), mean ± bootstrap 95% CI")
    ax.set_title("Adaptive slack 2: spilled versus non-spilled latency by cache status")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    save_svg(fig, FIGURES / f"{prefix}-spilled-latency.svg")
    fig.savefig(FIGURES / f"{prefix}-spilled-latency.pdf", format="pdf")
    plt.close(fig)


def make_markdown(summary_rows, spill_rows, source_names, prefix):
    lines = [
        f"# Routing sweep analysis ({prefix})",
        "",
        f"Source trial files: {', '.join(f'`{name}`' for name in source_names)}.",
        "",
        "Intervals are over independent trial-level values. HIT ratio, origin attempts,",
        "distinct keys, excess attempts, and request CV use two-sided 95% Student t-intervals:",
        "`mean ± t(0.975, n-1) × sample_sd / sqrt(n)`. P50/P95/P99 latency and error counts use",
        "deterministic 10,000-resample percentile bootstrap intervals for the mean. Percentiles",
        "are computed per trial before intervals are formed; HIT ratio is shown in percentage points.",
        "Request-level spill latency is first reduced to per-trial P50/P95, then summarized",
        "across repetitions. Pooled individual requests are not treated as independent samples.",
        "",
        "## Trial metrics by workload and policy",
        "",
        "| Workload | Policy | n | HIT (%) | Origin attempts | Distinct / floor | Excess attempts | Request CV | P95 (ms) | Errors |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['workload']} | {policy_label(row)} | {row['n_trials']} "
            f"| {fmt_ci(row['hit_ratio_mean'], row['hit_ratio_ci95_low'], row['hit_ratio_ci95_high'], 2)} "
            f"| {fmt_ci(row['origin_attempts_mean'], row['origin_attempts_ci95_low'], row['origin_attempts_ci95_high'], 1)} "
            f"| {fmt_ci(row['distinct_keys_mean'], row['distinct_keys_ci95_low'], row['distinct_keys_ci95_high'], 1)} "
            f"| {fmt_ci(row['excess_origin_attempts_mean'], row['excess_origin_attempts_ci95_low'], row['excess_origin_attempts_ci95_high'], 1)} "
            f"| {fmt_ci(row['request_cv_mean'], row['request_cv_ci95_low'], row['request_cv_ci95_high'], 3)} "
            f"| {fmt_ci(row['p95_ms_mean'], row['p95_ms_ci95_low'], row['p95_ms_ci95_high'], 1)} "
            f"| {row['error_requests_total']} |"
        )
    lines.extend([
        "",
        "## Adaptive slack effect on pooled workloads",
        "",
        "Workload-specific means and intervals remain in the CSV. The following table pools",
        "trial values across four workload families; this is a descriptive overall view, not",
        "a workload-standardized population estimate.",
        "",
        "| Slack | n trials | HIT (%) | Excess attempts | Request CV | P95 (ms) | Errors |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ])
    adaptive = defaultdict(list)
    for row in summary_rows:
        if row["policy"] == "adaptive":
            adaptive[row["slack"]].append(row)
    for slack, rows in sorted(adaptive.items()):
        source = [
            trial for trial in all_trial_rows
            if trial["policy"] == "adaptive" and trial["slack"] == slack
        ]
        entries = []
        for field in ("hit_ratio", "excess_origin_attempts", "request_cv", "p95_ms"):
            values = [
                float(trial[field]) * (100 if field == "hit_ratio" else 1)
                for trial in source
            ]
            entries.append(metric_interval(field, values))
        lines.append(
            f"| {slack} | {len(source)} | {fmt_ci(*entries[0][:3], 2)} "
            f"| {fmt_ci(*entries[1][:3], 1)} | {fmt_ci(*entries[2][:3], 3)} "
            f"| {fmt_ci(*entries[3][:3], 1)} | {sum(int(row['errors']) for row in source)} |"
        )
    lines.extend([
        "",
        "## Adaptive slack 2 spilled versus non-spilled P95",
        "",
        "| Workload | Cache status | Spill group | Trials | P95 (ms) |",
        "|---|---|---|---:|---:|",
    ])
    for row in spill_rows:
        if row["policy"] == "adaptive" and row["slack"] == 2:
            lines.append(
                f"| {row['workload']} | {row['cache_status']} | {row['spill']} | {row['n_trials']} "
                f"| {fmt_ci(row['p95_ms_mean'], row['p95_ms_ci95_low'], row['p95_ms_ci95_high'], 1)} |"
            )
    lines.extend([
        "",
        "## Figures and underlying data",
        "",
        f"- Pareto-style excess attempts versus request CV: `figures/{prefix}-pareto.svg` and `.pdf`.",
        f"- HIT ratio versus slack: `figures/{prefix}-hit-ratio.svg` and `.pdf`.",
        f"- P95 versus slack: `figures/{prefix}-p95.svg` and `.pdf`.",
        f"- Spilled versus non-spilled latency: `figures/{prefix}-spilled-latency.svg` and `.pdf`.",
        f"- Per-condition summary and interval endpoints: `{prefix}-summary.csv`.",
        f"- Per-trial spill percentiles and summary: `{prefix}-spill-trials.csv` and `{prefix}-spill-summary.csv`.",
        "",
        "A nonzero request-error count is retained as measured; do not silently exclude those trials.",
        "For any error trial, the reported latency percentile includes completed HTTP responses and",
        "client-side failures as recorded in the trial summary; interpret its tail alongside errors.",
        "",
    ])
    return "\n".join(lines)


if len(sys.argv) < 3:
    raise SystemExit(
        "Usage: python scripts/analyze-routing-sweep.py <sweep-trials.json> <baseline-trials.json> [request-csv ...]"
    )

trial_paths = [Path(argument) for argument in sys.argv[1:3]]
request_paths = [Path(argument) for argument in sys.argv[3:]]
all_trial_rows = read_trial_files(trial_paths)
summaries = summarize_trials(all_trial_rows)
spill_trials, spill_summaries = summarize_spills(request_paths) if request_paths else ([], [])
prefix = f"routing-analysis-{__import__('datetime').date.today().isoformat()}"
save_csv(RESULTS / f"{prefix}-summary.csv", summaries)
save_csv(RESULTS / f"{prefix}-spill-trials.csv", spill_trials)
save_csv(RESULTS / f"{prefix}-spill-summary.csv", spill_summaries)
save_figures(summaries, spill_summaries, prefix)
(RESULTS / f"{prefix}.md").write_text(
    make_markdown(summaries, spill_summaries, [file.name for file in trial_paths], prefix),
    encoding="utf-8",
)
(RESULTS / f"{prefix}.json").write_text(json.dumps({
    "sources": [file.name for file in trial_paths + request_paths],
    "confidence_intervals": {
        "hit_ratio, origin_attempts, distinct_keys, compulsory_miss_floor, excess_origin_attempts, request_cv": "Two-sided 95% Student t interval over trial-level replicates.",
        "p50_ms, p95_ms, p99_ms, errors, spill p50_ms, spill p95_ms": "Deterministic 10,000-resample percentile bootstrap interval for the trial-level mean.",
        "bootstrap_seed": 3102026,
    },
    "trial_summaries": summaries,
    "spill_trial_percentiles": spill_trials,
    "spill_summaries": spill_summaries,
}, indent=2) + "\n", encoding="utf-8")
print(json.dumps({
    "status": "PASS",
    "trial_rows": len(all_trial_rows),
    "summary_groups": len(summaries),
    "spill_trial_groups": len(spill_trials),
    "spill_summary_groups": len(spill_summaries),
    "outputs": [
        f"{prefix}.md", f"{prefix}.json", f"{prefix}-summary.csv",
        f"{prefix}-spill-trials.csv", f"{prefix}-spill-summary.csv",
        *(f"figures/{prefix}-{chart}.{extension}" for chart in (
            "pareto", "hit-ratio", "p95", "spilled-latency"
        ) for extension in ("svg", "pdf")),
    ],
}, indent=2))
