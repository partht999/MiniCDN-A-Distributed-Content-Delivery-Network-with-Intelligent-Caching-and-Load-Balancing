import csv
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path.cwd()
RESULTS = ROOT / "docs" / "academic" / "results"
FIGURES = RESULTS / "figures"
FIGURES.mkdir(parents=True, exist_ok=True)
T_95_DF9 = 2.262
METRICS = (
    "hit_ratio", "excess_origin_attempts", "request_cv",
    "p50_ms", "p95_ms", "p99_ms", "errors",
)


def interval(values):
    if not values:
        return None, None, None
    mean = sum(values) / len(values)
    if len(values) < 2:
        return mean, None, None
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    half = T_95_DF9 * math.sqrt(variance / len(values))
    return mean, mean - half, mean + half


def policy_key(row):
    slack = row.get("slack")
    return (
        row["workload"],
        int(row["concurrency"]),
        row["policy"],
        None if slack is None else int(slack),
    )


def save_csv(path, rows):
    if rows:
        with path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def analyze(rows):
    groups = defaultdict(list)
    run_map = {}
    for row in rows:
        if int(row["edgeMaxConcurrentRequests"]) != 4:
            raise ValueError("Constrained sweep must use edgeMaxConcurrentRequests=4.")
        groups[policy_key(row)].append(row)
        run_map[(
            row["workload"], int(row["concurrency"]), int(row["run"]),
            row["policy"], None if row.get("slack") is None else int(row["slack"]),
        )] = row

    summaries = []
    for key, trials in sorted(groups.items(), key=lambda item: str(item[0])):
        workload, concurrency, policy, slack = key
        if len(trials) != 10:
            raise ValueError(f"Expected 10 trials for {key}; got {len(trials)}")
        row = {
            "workload": workload,
            "concurrency": concurrency,
            "policy": policy,
            "slack": slack,
            "n_trials": len(trials),
            "interval_method": "two-sided Student t, df=9",
        }
        for metric in METRICS:
            values = [float(trial[metric]) for trial in trials]
            mean, low, high = interval(values)
            row[f"{metric}_mean"] = mean
            row[f"{metric}_ci95_low"] = low
            row[f"{metric}_ci95_high"] = high
        summaries.append(row)

    paired = []
    for key, trials in sorted(groups.items(), key=lambda item: str(item[0])):
        workload, concurrency, policy, slack = key
        if policy == "consistent_hash":
            continue
        for metric in METRICS:
            differences = []
            for run in range(10):
                candidate = run_map.get((workload, concurrency, run, policy, slack))
                baseline = run_map.get((workload, concurrency, run, "consistent_hash", None))
                if candidate is None or baseline is None:
                    raise ValueError(
                        f"Missing paired CH trial for {workload}, c={concurrency}, "
                        f"{policy}/{slack}, run={run}"
                    )
                differences.append(float(candidate[metric]) - float(baseline[metric]))
            mean, low, high = interval(differences)
            paired.append({
                "workload": workload,
                "concurrency": concurrency,
                "policy": policy,
                "slack": slack,
                "metric": metric,
                "difference_policy_minus_consistent_hash": mean,
                "ci95_low": low,
                "ci95_high": high,
                "n_pairs": len(differences),
                "interval_method": "paired Student t, two-sided 95%, df=9",
                "latency_ranking_claimed": (
                    "no" if metric.startswith("p") and low <= 0 <= high
                    else "yes" if metric.startswith("p")
                    else "not_applicable"
                ),
            })
    return summaries, paired


def save_figure(paired, prefix):
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for row_index, workload in enumerate(("zipf", "uniform")):
        for col_index, metric in enumerate(("hit_ratio", "p95_ms")):
            ax = axes[row_index, col_index]
            subset = [
                row for row in paired
                if row["workload"] == workload and row["metric"] == metric
            ]
            for concurrency in (16, 64, 128):
                conditions = [row for row in subset if row["concurrency"] == concurrency]
                if not conditions:
                    continue
                x = list(range(len(conditions)))
                means = [row["difference_policy_minus_consistent_hash"] for row in conditions]
                lows = [row["ci95_low"] for row in conditions]
                highs = [row["ci95_high"] for row in conditions]
                ax.errorbar(
                    x, means,
                    yerr=[[mean - low for mean, low in zip(means, lows)],
                          [high - mean for mean, high in zip(means, highs)]],
                    marker="o", capsize=3, label=f"concurrency {concurrency}",
                )
                ax.set_xticks(
                    x,
                    [
                        f"{row['policy'].replace('_', ' ')}"
                        + (f"\nslack {row['slack']}" if row["slack"] is not None else "")
                        for row in conditions
                    ],
                    rotation=25, ha="right",
                )
            ax.axhline(0, color="black", linewidth=0.8)
            ax.set_title(f"{workload.replace('_', ' ')}: {metric}")
            ax.set_ylabel("paired difference vs consistent hash")
            ax.grid(alpha=0.25)
            ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGURES / f"{prefix}-paired.pdf")
    plt.close(fig)


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: analyze-constrained-routing.py SWEEP.json [SWEEP.json ...]")
    paths = [Path(value) for value in sys.argv[1:]]
    trials = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        metadata = data["metadata"]
        for row in data["rows"]:
            trials.append({
                **row,
                "concurrency": metadata["concurrency"],
                "edgeMaxConcurrentRequests": metadata["edgeMaxConcurrentRequests"],
            })
    summaries, paired = analyze(trials)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S-%fZ")
    prefix = f"routing-constrained-analysis-{stamp}"
    save_csv(RESULTS / f"{prefix}-summary.csv", summaries)
    save_csv(RESULTS / f"{prefix}-paired.csv", paired)
    save_figure(paired, prefix)
    payload = {
        "sources": [str(path) for path in paths],
        "edge_max_concurrent_requests": 4,
        "confidence_interval": "two-sided Student t, df=9; paired for policy differences",
        "summaries": summaries,
        "paired_differences": paired,
    }
    (RESULTS / f"{prefix}.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    with (RESULTS / f"{prefix}.md").open("w", encoding="utf-8") as output:
        output.write("# Constrained edge service experiment\n\n")
        output.write("Edge handler concurrency limit: 4 per edge. Results use independent trial-level two-sided Student t intervals (df=9); differences versus consistent hash use paired t intervals on run-matched traces. P50/P95/P99 differences are ranked only when the paired interval excludes zero.\n\n")
        output.write("## Per-condition metrics\n\n")
        output.write("| Workload | C | Policy | Slack | HIT (95% CI) | Excess origins (95% CI) | CV (95% CI) | P50 | P95 | P99 | Errors |\n|---|---:|---|---:|---|---|---|---|---|---|---|\n")
        for row in summaries:
            def ci(metric, scale=1.0):
                return (
                    f"{row[f'{metric}_mean'] * scale:.4g} "
                    f"[{row[f'{metric}_ci95_low'] * scale:.4g}, "
                    f"{row[f'{metric}_ci95_high'] * scale:.4g}]"
                )
            output.write(
                f"| {row['workload']} | {row['concurrency']} | {row['policy']} | "
                f"{row['slack'] if row['slack'] is not None else '—'} | "
                f"{ci('hit_ratio', 100)} | {ci('excess_origin_attempts')} | "
                f"{ci('request_cv')} | {ci('p50_ms')} | {ci('p95_ms')} | "
                f"{ci('p99_ms')} | {ci('errors')} |\n"
            )
        output.write("\n## Paired differences versus consistent hash\n\n")
        output.write("| Workload | C | Policy | Slack | Metric | Difference | 95% CI | Latency ranking |\n|---|---:|---|---:|---|---:|---|---|\n")
        for row in paired:
            output.write(
                f"| {row['workload']} | {row['concurrency']} | {row['policy']} | "
                f"{row['slack'] if row['slack'] is not None else '—'} | {row['metric']} | "
                f"{row['difference_policy_minus_consistent_hash']:.6g} | "
                f"[{row['ci95_low']:.6g}, {row['ci95_high']:.6g}] | "
                f"{row['latency_ranking_claimed']} |\n"
            )
    print(json.dumps({
        "status": "PASS",
        "prefix": prefix,
        "trials": len(trials),
        "summary_groups": len(summaries),
        "paired_rows": len(paired),
    }, indent=2))


if __name__ == "__main__":
    main()
