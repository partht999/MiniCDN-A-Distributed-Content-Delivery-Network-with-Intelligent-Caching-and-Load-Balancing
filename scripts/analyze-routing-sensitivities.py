import csv
import json
import math
import random
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
    "hit_ratio", "origin_attempts", "distinct_keys",
    "excess_origin_attempts", "request_cv", "p50_ms", "p95_ms", "p99_ms", "errors",
)


def interval(values, bootstrap=False):
    if not values:
        return None, None, None
    mean = sum(values) / len(values)
    if len(values) < 2:
        return mean, None, None
    if bootstrap:
        rng = random.Random(3102026 + len(values))
        samples = sorted(
            sum(values[rng.randrange(len(values))] for _ in values) / len(values)
            for _ in range(10000)
        )
        return mean, samples[250], samples[9749]
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    half = T_95_DF9 * math.sqrt(variance / len(values))
    return mean, mean - half, mean + half


def condition_from_metadata(metadata):
    label = metadata.get("experimentLabel", "")
    if "-cache-" in label:
        value = int(label.split("-cache-")[1].split("-")[0])
        return "cache size", value, "KiB"
    if "-origin-" in label:
        value = int(label.split("-origin-")[1].split("-")[0])
        return "origin delay", value, "ms"
    if "-zipf-" in label:
        value = float(label.split("-zipf-")[1].replace("-", "."))
        return "Zipf exponent", value, ""
    raise ValueError(f"Could not identify sensitivity condition from label {label!r}")


def save_csv(path, rows):
    if rows:
        with path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: analyze-routing-sensitivities.py SWEEP.json [SWEEP.json ...]")
    grouped = defaultdict(list)
    sources = []
    for argument in sys.argv[1:]:
        path = Path(argument)
        data = json.loads(path.read_text(encoding="utf-8"))
        factor, value, unit = condition_from_metadata(data["metadata"])
        sources.append(path.name)
        for row in data["rows"]:
            if row["workload"] != "zipf":
                raise ValueError(f"Unexpected workload in optional sensitivity file {path}")
            grouped[(factor, value, unit, row["policy"], row.get("slack"))].append(row)

    summaries = []
    for key, trials in sorted(grouped.items(), key=lambda item: str(item[0])):
        factor, value, unit, policy, slack = key
        if len(trials) != 10:
            raise ValueError(f"Expected 10 repetitions for {key}, got {len(trials)}")
        row = {
            "factor": factor, "value": value, "unit": unit,
            "policy": policy, "slack": slack, "n_trials": len(trials),
        }
        for metric in METRICS:
            values = [float(trial[metric]) for trial in trials]
            mean, low, high = interval(values, bootstrap=metric in ("p95_ms", "p99_ms", "errors"))
            row[f"{metric}_mean"] = mean
            row[f"{metric}_ci95_low"] = low
            row[f"{metric}_ci95_high"] = high
            row[f"{metric}_interval_method"] = (
                "10,000-resample percentile bootstrap" if metric in ("p95_ms", "p99_ms", "errors")
                else "two-sided Student t, df=9"
            )
        summaries.append(row)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S-%fZ")
    prefix = f"routing-sensitivity-analysis-{stamp}"
    save_csv(RESULTS / f"{prefix}.csv", summaries)
    payload = {
        "sources": sources,
        "confidence_intervals": {
            "hit_ratio, origin_attempts, distinct_keys, excess_origin_attempts, request_cv, p50_ms": "Two-sided Student t, df=9.",
            "p95_ms, p99_ms, errors": "10,000-resample percentile bootstrap interval for the mean.",
            "bootstrap_seed": 3102026,
        },
        "summaries": summaries,
    }
    (RESULTS / f"{prefix}.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with (RESULTS / f"{prefix}.md").open("w", encoding="utf-8") as output:
        output.write("# Routing sensitivity results\n\n")
        output.write("All conditions use ten Zipf-trace repetitions, 3,000 measured requests, concurrency 16, 256 warm-up requests, and the same interleaved consistent-hash, round-robin, and adaptive-slack-2 policies. HIT and count/CV/P50 intervals use Student t (df=9); P95/P99/errors use deterministic 10,000-resample bootstrap intervals.\n\n")
        output.write("Input files: " + ", ".join(f"`{name}`" for name in sources) + ".\n\n")
        output.write("| Factor | Value | Policy | HIT (%) | Excess origins | CV | P95 (ms) | Errors |\n|---|---:|---|---|---|---|---|---|\n")
        for row in summaries:
            label = row["policy"] + (f" slack {row['slack']}" if row["slack"] is not None else "")
            output.write(
                f"| {row['factor']} | {row['value']} {row['unit']} | {label} | "
                f"{row['hit_ratio_mean'] * 100:.2f} "
                f"[{row['hit_ratio_ci95_low'] * 100:.2f}, {row['hit_ratio_ci95_high'] * 100:.2f}] | "
                f"{row['excess_origin_attempts_mean']:.2f} "
                f"[{row['excess_origin_attempts_ci95_low']:.2f}, {row['excess_origin_attempts_ci95_high']:.2f}] | "
                f"{row['request_cv_mean']:.4f} "
                f"[{row['request_cv_ci95_low']:.4f}, {row['request_cv_ci95_high']:.4f}] | "
                f"{row['p95_ms_mean']:.2f} "
                f"[{row['p95_ms_ci95_low']:.2f}, {row['p95_ms_ci95_high']:.2f}] | "
                f"{row['errors_mean']:.2f} |\n"
            )
    factors = ("cache size", "origin delay", "Zipf exponent")
    for metric, label in (("hit_ratio", "HIT ratio (%)"), ("p95_ms", "P95 latency (ms)")):
        fig, axes = plt.subplots(1, 3, figsize=(13, 4))
        for ax, factor in zip(axes, factors):
            selected_factor = [row for row in summaries if row["factor"] == factor]
            for policy, marker in (
                ("consistent_hash", "o"), ("round_robin", "s"), ("adaptive", "^")
            ):
                selected = sorted(
                    [row for row in selected_factor if row["policy"] == policy],
                    key=lambda row: float(row["value"]),
                )
                if not selected:
                    continue
                x = [float(row["value"]) for row in selected]
                scale = 100 if metric == "hit_ratio" else 1
                means = [row[f"{metric}_mean"] * scale for row in selected]
                lows = [row[f"{metric}_ci95_low"] * scale for row in selected]
                highs = [row[f"{metric}_ci95_high"] * scale for row in selected]
                ax.errorbar(
                    x, means,
                    yerr=[[mean - low for mean, low in zip(means, lows)],
                          [high - mean for mean, high in zip(means, highs)]],
                    marker=marker, capsize=3, label=policy.replace("_", " "),
                )
            ax.set_title(factor)
            ax.set_xlabel(f"{factor} ({selected_factor[0]['unit']})" if selected_factor else factor)
            ax.set_ylabel(label)
            ax.grid(alpha=0.25)
            ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(FIGURES / f"{prefix}-{metric}.pdf")
        plt.close(fig)
    print(json.dumps({
        "status": "PASS",
        "prefix": prefix,
        "conditions": len(summaries),
        "source_files": len(sources),
    }, indent=2))


if __name__ == "__main__":
    main()
