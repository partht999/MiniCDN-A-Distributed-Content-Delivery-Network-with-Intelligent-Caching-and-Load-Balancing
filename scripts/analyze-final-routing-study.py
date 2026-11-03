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


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def paired_interval(values):
    if not values:
        return None, None, None
    mean = sum(values) / len(values)
    if len(values) < 2:
        return mean, None, None
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    half_width = T_95_DF9 * math.sqrt(variance / len(values))
    return mean, mean - half_width, mean + half_width


def bootstrap_interval(values, seed=3102026, samples=10000):
    if not values:
        return None, None, None
    mean = sum(values) / len(values)
    if len(values) == 1:
        return mean, None, None
    rng = random.Random(seed + len(values))
    estimates = sorted(
        sum(values[rng.randrange(len(values))] for _ in values) / len(values)
        for _ in range(samples)
    )
    return mean, estimates[int(0.025 * samples)], estimates[int(0.975 * samples)]


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def iter_requests(path):
    with path.open(newline="", encoding="utf-8") as source:
        yield from csv.DictReader(source)


def compute_paired(rows):
    by_trial = {
        (row["workload"], row["run"], row["policy"]): row
        for row in rows
    }
    metrics = ("hit_ratio", "excess_origin_attempts", "request_cv", "p95_ms")
    output = []
    paired_differences = defaultdict(list)
    for workload in sorted({row["workload"] for row in rows}):
        policies = sorted({
            row["policy"] for row in rows
            if row["workload"] == workload and row["policy"] != "consistent_hash"
        })
        for policy in policies:
            differences = {metric: [] for metric in metrics}
            for run in sorted({
                int(row["run"]) for row in rows
                if row["workload"] == workload and row["policy"] == policy
            }):
                policy_row = by_trial.get((workload, str(run), policy))
                hash_row = by_trial.get((workload, str(run), "consistent_hash"))
                if policy_row is None:
                    policy_row = by_trial.get((workload, run, policy))
                if hash_row is None:
                    hash_row = by_trial.get((workload, run, "consistent_hash"))
                if policy_row is None or hash_row is None:
                    raise ValueError(f"Unpaired trial: {workload}, run {run}, {policy}")
                for metric in metrics:
                    differences[metric].append(
                        float(policy_row[metric]) - float(hash_row[metric])
                    )
            for metric, values in differences.items():
                if len(values) != 10:
                    raise ValueError(
                        f"Expected 10 paired runs for {workload}/{policy}/{metric}, got {len(values)}"
                    )
                mean, low, high = paired_interval(values)
                row = {
                    "workload": workload,
                    "policy": policy,
                    "metric": metric,
                    "difference_policy_minus_consistent_hash": mean,
                    "ci95_low": low,
                    "ci95_high": high,
                    "n_pairs": len(values),
                    "interval_method": "paired Student t, two-sided 95%, df=9",
                    "latency_ranking_claimed": (
                        "no" if metric == "p95_ms" and low is not None and low <= 0 <= high
                        else "yes" if metric == "p95_ms"
                        else "not_applicable"
                    ),
                }
                output.append(row)
                paired_differences[(workload, policy, metric)] = values
    return output, paired_differences


def capacity_rows(rows):
    uniform = [row for row in rows if row["workload"] == "uniform"]
    by_policy = defaultdict(list)
    for row in uniform:
        if row["policy"] in ("consistent_hash", "round_robin"):
            by_policy[row["policy"]].append(row)
    if set(by_policy) != {"consistent_hash", "round_robin"}:
        raise ValueError("Uniform consistent-hash and round-robin trials are required.")
    distinct = [int(row["distinct_keys"]) for row in by_policy["consistent_hash"]]
    requests = [int(row["requests"]) for row in by_policy["consistent_hash"]]
    if len(set(requests)) != 1:
        raise ValueError("Uniform trial request counts differ.")
    count = len(requests)
    distinct_mean = sum(distinct) / len(distinct)
    compulsory_ceiling = 1.0 - distinct_mean / requests[0]
    predictions = {
        "round_robin": 64 / 256,
        "consistent_hash": (3 * 64) / 256,
    }
    output = []
    for policy, predicted in predictions.items():
        values = [float(row["hit_ratio"]) for row in by_policy[policy]]
        mean, low, high = paired_interval(values)
        output.append({
            "policy": policy,
            "prediction_capacity_model": predicted,
            "prediction_capped_by_compulsory_ceiling": min(predicted, compulsory_ceiling),
            "measured_hit_mean": mean,
            "measured_hit_ci95_low": low,
            "measured_hit_ci95_high": high,
            "distinct_keys_mean": distinct_mean,
            "requests_per_trial": requests[0],
            "compulsory_miss_hit_ceiling": compulsory_ceiling,
            "n_trials": count,
            "interval_method": "two-sided Student t, df=9",
        })
    return output


def spill_analysis(trial_rows, request_rows):
    valid_spills = defaultdict(lambda: {"spilled": 0, "total": 0})
    miss_counts = defaultdict(lambda: {
        "spilled_requests": 0, "spilled_misses": 0,
        "non_spilled_requests": 0, "non_spilled_misses": 0,
    })
    for path in request_rows:
        for request in iter_requests(path):
            if request.get("policy") != "adaptive":
                continue
            if request.get("spilled") not in ("true", "false"):
                continue
            if request.get("error") or request.get("cacheStatus") not in ("HIT", "MISS"):
                continue
            workload = request["workload"]
            slack = request.get("slack") or ""
            trial_id = request["trialId"]
            trial_group = (trial_id, workload, slack)
            valid_spills[trial_group]["total"] += 1
            valid_spills[trial_group]["spilled"] += request["spilled"] == "true"
            miss_group = (workload, slack)
            spill_label = "spilled" if request["spilled"] == "true" else "non_spilled"
            miss_counts[miss_group][f"{spill_label}_requests"] += 1
            miss_counts[miss_group][f"{spill_label}_misses"] += request["cacheStatus"] == "MISS"

    trials = {
        (
            row["trialId"], row["workload"],
            str(row["slack"]) if row.get("slack") is not None else "",
        ): row
        for row in trial_rows if row["policy"] == "adaptive"
    }
    observations = []
    for key, counts in valid_spills.items():
        trial = trials.get(key)
        if trial is None or counts["total"] == 0:
            continue
        observations.append({
            "trial_id": key[0],
            "workload": key[1],
            "slack": int(key[2]),
            "spill_fraction": counts["spilled"] / counts["total"],
            "hit_ratio": float(trial["hit_ratio"]),
            "excess_origin_attempts": float(trial["excess_origin_attempts"]),
            "request_count_valid_for_spill": counts["total"],
        })

    fit_rows = []
    residual_rows = []
    for metric in ("hit_ratio", "excess_origin_attempts"):
        xs = [row["spill_fraction"] for row in observations]
        ys = [row[metric] for row in observations]
        x_mean = sum(xs) / len(xs)
        y_mean = sum(ys) / len(ys)
        denominator = sum((x - x_mean) ** 2 for x in xs)
        slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator
        intercept = y_mean - slope * x_mean
        residual_sum = 0.0
        total_sum = 0.0
        for row in observations:
            predicted = intercept + slope * row["spill_fraction"]
            residual = row[metric] - predicted
            residual_sum += residual ** 2
            total_sum += (row[metric] - y_mean) ** 2
            residual_rows.append({
                "trial_id": row["trial_id"],
                "workload": row["workload"],
                "slack": row["slack"],
                "outcome": metric,
                "spill_fraction": row["spill_fraction"],
                "observed": row[metric],
                "predicted": predicted,
                "residual": residual,
            })
        fit_rows.append({
            "outcome": metric,
            "observations": len(observations),
            "intercept": intercept,
            "spill_fraction_slope": slope,
            "r_squared": 1.0 - residual_sum / total_sum if total_sum else 1.0,
            "interpretation": "descriptive association only; no causal claim",
        })

    miss_rows = []
    for (workload, slack), counts in sorted(miss_counts.items()):
        for spill_label in ("spilled", "non_spilled"):
            total = counts[f"{spill_label}_requests"]
            misses = counts[f"{spill_label}_misses"]
            miss_rows.append({
                "workload": workload,
                "slack": int(slack),
                "spill_group": spill_label,
                "requests": total,
                "misses": misses,
                "miss_rate": misses / total if total else None,
                "errors_excluded": True,
            })
    return observations, fit_rows, residual_rows, miss_rows


def trial_spill_latencies(request_paths):
    grouped = defaultdict(list)
    for path in request_paths:
        for request in iter_requests(path):
            if request.get("policy") != "adaptive" or request.get("slack") != "2":
                continue
            if request.get("cacheStatus") not in ("HIT", "MISS"):
                continue
            if request.get("spilled") not in ("true", "false") or request.get("error"):
                continue
            key = (
                request["trialId"], request["workload"],
                "spilled" if request["spilled"] == "true" else "non_spilled",
                request["cacheStatus"],
            )
            grouped[key].append(float(request["latencyMs"]))
    trial_rows = []
    by_condition = defaultdict(list)
    for (trial_id, workload, spill, status), values in sorted(grouped.items()):
        ordered = sorted(values)
        p50 = ordered[max(0, math.ceil(0.50 * len(ordered)) - 1)]
        p95 = ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]
        row = {
            "trial_id": trial_id,
            "workload": workload,
            "spill": spill,
            "cache_status": status,
            "request_count": len(values),
            "p50_ms": p50,
            "p95_ms": p95,
        }
        trial_rows.append(row)
        by_condition[(workload, spill, status)].append(row)
    summary_rows = []
    for (workload, spill, status), trials in sorted(by_condition.items()):
        p50 = bootstrap_interval([row["p50_ms"] for row in trials])
        p95 = bootstrap_interval([row["p95_ms"] for row in trials])
        summary_rows.append({
            "workload": workload,
            "spill": spill,
            "cache_status": status,
            "n_trials": len(trials),
            "p50_ms_mean": p50[0],
            "p50_ms_ci95_low": p50[1],
            "p50_ms_ci95_high": p50[2],
            "p95_ms_mean": p95[0],
            "p95_ms_ci95_low": p95[1],
            "p95_ms_ci95_high": p95[2],
            "interval_method": "10,000-resample percentile bootstrap over trial percentiles",
        })
    return trial_rows, summary_rows


def make_main_figures(
    sweep_rows, baseline_rows, spill_rows, capacities,
    spill_observations, spill_fits, prefix
):
    plot_rows = list(baseline_rows) + [
        row for row in sweep_rows
        if row["policy"] == "adaptive" and int(row["slack"]) != 2
    ]
    grouped = defaultdict(list)
    for row in plot_rows:
        grouped[(row["workload"], row["policy"], row.get("slack"))].append(row)
    summary = []
    for (workload, policy, slack), trials in grouped.items():
        record = {
            "workload": workload, "policy": policy, "slack": slack,
            "n_trials": len(trials),
        }
        for metric in ("request_cv", "excess_origin_attempts", "hit_ratio", "p95_ms"):
            values = [float(row[metric]) for row in trials]
            mean, low, high = (
                bootstrap_interval(values) if metric == "p95_ms"
                else paired_interval(values)
            )
            record[metric] = mean
            record[f"{metric}_ci95_low"] = low
            record[f"{metric}_ci95_high"] = high
        summary.append(record)

    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for ax, workload in zip(axes.flat, ("uniform", "zipf", "changing_hot", "cold_burst")):
        for row in summary:
            if row["workload"] != workload:
                continue
            label = row["policy"].replace("_", " ")
            if row["slack"] is not None:
                label += f" s={row['slack']}"
            ax.errorbar(
                row["request_cv"], row["excess_origin_attempts"],
                xerr=[[
                    row["request_cv"] - row["request_cv_ci95_low"]
                ], [
                    row["request_cv_ci95_high"] - row["request_cv"]
                ]],
                yerr=[[
                    row["excess_origin_attempts"] - row["excess_origin_attempts_ci95_low"]
                ], [
                    row["excess_origin_attempts_ci95_high"] - row["excess_origin_attempts"]
                ]],
                fmt="o", markersize=3, capsize=2, label=label,
            )
        ax.set_title(workload.replace("_", " "))
        ax.set_xlabel("Request-count CV")
        ax.set_ylabel("Excess origin attempts / trial")
        ax.grid(alpha=0.25)
        ax.legend(fontsize=6, loc="best")
    fig.tight_layout()
    fig.savefig(FIGURES / f"{prefix}-pareto-faceted.pdf")
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    slacks = (0, 1, 2, 4, 8, 1000)
    for ax, workload in zip(axes.flat, ("uniform", "zipf", "changing_hot", "cold_burst")):
        adaptive_rows = sorted(
            [row for row in summary if row["workload"] == workload and row["policy"] == "adaptive"],
            key=lambda row: int(row["slack"]),
        )
        x = [int(row["slack"]) for row in adaptive_rows]
        y = [row["hit_ratio"] * 100 for row in adaptive_rows]
        low = [row["hit_ratio_ci95_low"] * 100 for row in adaptive_rows]
        high = [row["hit_ratio_ci95_high"] * 100 for row in adaptive_rows]
        ax.errorbar(
            x, y, yerr=[[a - b for a, b in zip(y, low)], [b - a for a, b in zip(y, high)]],
            marker="o", capsize=3, label="adaptive",
        )
        for policy, linestyle in (
            ("consistent_hash", "--"), ("round_robin", ":"),
            ("least_loaded_router_local", "-."), ("bounded_load_router_local", "-"),
        ):
            row = next((
                item for item in summary
                if item["workload"] == workload and item["policy"] == policy
            ), None)
            if row is not None:
                ax.axhline(row["hit_ratio"] * 100, linestyle=linestyle, linewidth=0.9,
                           label=policy.replace("_router_local", "").replace("_", " "))
        ax.set_xscale("symlog", linthresh=1)
        ax.set_xticks(slacks, [str(value) for value in slacks])
        ax.set_title(workload.replace("_", " "))
        ax.set_xlabel("Adaptive slack")
        ax.set_ylabel("HIT ratio (%)")
        ax.grid(alpha=0.25)
        ax.legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(FIGURES / f"{prefix}-hit-vs-slack.pdf")
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for ax, workload in zip(axes.flat, ("uniform", "zipf", "changing_hot", "cold_burst")):
        adaptive_rows = sorted(
            [row for row in summary if row["workload"] == workload and row["policy"] == "adaptive"],
            key=lambda row: int(row["slack"]),
        )
        x = [int(row["slack"]) for row in adaptive_rows]
        y = [row["p95_ms"] for row in adaptive_rows]
        low = [row["p95_ms_ci95_low"] for row in adaptive_rows]
        high = [row["p95_ms_ci95_high"] for row in adaptive_rows]
        ax.errorbar(
            x, y, yerr=[[max(0, a - b) for a, b in zip(y, low)],
                        [max(0, b - a) for a, b in zip(y, high)]],
            marker="o", capsize=3, label="adaptive",
        )
        if workload == "uniform":
            error_row = next((
                row for row in adaptive_rows
                if int(row["slack"]) == 1000
            ), None)
            if error_row is not None:
                errors = sum(
                    int(row["errors"]) for row in sweep_rows
                    if row["workload"] == workload and row["policy"] == "adaptive"
                    and int(row["slack"]) == 1000
                )
                if errors:
                    ax.annotate(
                        f"slack 1000: {errors} errors",
                        (1000, min(error_row["p95_ms"], 390)),
                        xytext=(-100, 18), textcoords="offset points",
                        arrowprops={"arrowstyle": "->"}, fontsize=7,
                    )
        ax.set_xscale("symlog", linthresh=1)
        ax.set_xticks(slacks, [str(value) for value in slacks])
        ax.set_ylim(bottom=0, top=400)
        ax.set_title(workload.replace("_", " "))
        ax.set_xlabel("Adaptive slack")
        ax.set_ylabel("P95 latency (ms; axis capped at 400)")
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGURES / f"{prefix}-p95-vs-slack.pdf")
    plt.close(fig)

    spill_conditions = [
        row for row in spill_rows
        if row["cache_status"] in ("HIT", "MISS")
    ]
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for ax, workload in zip(axes.flat, ("uniform", "zipf", "changing_hot", "cold_burst")):
        selected = [row for row in spill_conditions if row["workload"] == workload]
        labels = [
            f"{row['cache_status']} {'spill' if row['spill'] == 'spilled' else 'local'}"
            for row in selected
        ]
        y = list(range(len(selected)))
        means = [row["p95_ms_mean"] for row in selected]
        lows = [
            row["p95_ms_ci95_low"] if row["p95_ms_ci95_low"] is not None else row["p95_ms_mean"]
            for row in selected
        ]
        highs = [
            row["p95_ms_ci95_high"] if row["p95_ms_ci95_high"] is not None else row["p95_ms_mean"]
            for row in selected
        ]
        ax.errorbar(
            means, y,
            xerr=[[mean - low for mean, low in zip(means, lows)],
                   [high - mean for mean, high in zip(means, highs)]],
            fmt="o", capsize=3,
        )
        ax.set_yticks(y, labels)
        ax.set_title(workload.replace("_", " "))
        ax.set_xlabel("Per-trial request P95 (ms), mean with bootstrap 95% CI")
        ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGURES / f"{prefix}-spill-p95.pdf")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 4))
    positions = list(range(len(capacities)))
    predicted = [row["prediction_capped_by_compulsory_ceiling"] * 100 for row in capacities]
    measured = [row["measured_hit_mean"] * 100 for row in capacities]
    low = [row["measured_hit_ci95_low"] * 100 for row in capacities]
    high = [row["measured_hit_ci95_high"] * 100 for row in capacities]
    ax.bar([position - 0.18 for position in positions], predicted, width=0.36, label="capacity model")
    ax.bar([position + 0.18 for position in positions], measured, width=0.36, label="measured")
    ax.errorbar(
        [position + 0.18 for position in positions], measured,
        yerr=[[mean - bottom for mean, bottom in zip(measured, low)],
              [top - mean for mean, top in zip(measured, high)]],
        fmt="none", ecolor="black", capsize=3,
    )
    ax.set_xticks(positions, [row["policy"].replace("_", " ") for row in capacities])
    ax.set_ylabel("Uniform HIT ratio (%)")
    ax.set_title("Uniform capacity-model prediction vs same-session measurements")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGURES / f"{prefix}-capacity-model.pdf")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    colors = {
        "uniform": "#2878B5", "zipf": "#E07B39",
        "changing_hot": "#43966E", "cold_burst": "#8A69A8",
    }
    for ax, metric, label in (
        (axes[0], "hit_ratio", "Adaptive HIT ratio"),
        (axes[1], "excess_origin_attempts", "Excess origin attempts / trial"),
    ):
        fit = next(row for row in spill_fits if row["outcome"] == metric)
        for workload, color in colors.items():
            selected = [row for row in spill_observations if row["workload"] == workload]
            xs = [row["spill_fraction"] for row in selected]
            ys = [row[metric] for row in selected]
            ax.scatter(xs, ys, label=workload.replace("_", " "), color=color, alpha=0.75)
        line_x = [0, 1]
        line_y = [
            fit["intercept"] + fit["spill_fraction_slope"] * value
            for value in line_x
        ]
        ax.plot(line_x, line_y, color="black", linestyle="--", linewidth=1,
                label=f"OLS R2={fit['r_squared']:.3f}")
        ax.set_xlabel("Per-trial spill fraction")
        ax.set_ylabel(label)
        ax.grid(alpha=0.25)
        ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(FIGURES / f"{prefix}-spill-fit.pdf")
    plt.close(fig)
    return summary


def save_paired_figure(rows, prefix):
    workloads = sorted({row["workload"] for row in rows})
    fig, axes = plt.subplots(len(workloads), 4, figsize=(17, 3.3 * len(workloads)))
    metrics = ("hit_ratio", "excess_origin_attempts", "request_cv", "p95_ms")
    labels = {
        "hit_ratio": "HIT-ratio difference",
        "excess_origin_attempts": "Excess-origin difference",
        "request_cv": "Request-CV difference",
        "p95_ms": "P95-latency difference (ms)",
    }
    for row_index, workload in enumerate(workloads):
        for column_index, metric in enumerate(metrics):
            ax = axes[row_index, column_index]
            selected = [
                row for row in rows
                if row["workload"] == workload and row["metric"] == metric
            ]
            y = list(range(len(selected)))
            means = [row["difference_policy_minus_consistent_hash"] for row in selected]
            lows = [row["ci95_low"] for row in selected]
            highs = [row["ci95_high"] for row in selected]
            ax.errorbar(
                means, y,
                xerr=[[mean - low for mean, low in zip(means, lows)],
                       [high - mean for mean, high in zip(means, highs)]],
                fmt="o", capsize=3,
            )
            ax.set_yticks(y, [row["policy"].replace("_", " ") for row in selected])
            ax.axvline(0, color="black", linewidth=0.8)
            ax.set_title(f"{workload.replace('_', ' ')}: {metric}")
            ax.set_xlabel(labels[metric])
            ax.grid(axis="x", alpha=0.25)
            if metric == "p95_ms":
                for row, position in zip(selected, y):
                    if row["latency_ranking_claimed"] == "no":
                        ax.annotate("CI overlaps 0", (0, position), xytext=(4, 3),
                                    textcoords="offset points", fontsize=7)
    fig.tight_layout()
    fig.savefig(FIGURES / f"{prefix}-paired-differences.pdf")
    plt.close(fig)


def main():
    if len(sys.argv) != 5:
        raise SystemExit(
            "usage: analyze-final-routing-study.py SAME_SESSION.json "
            "SLACK_SWEEP.json SLACK_SWEEP-requests.csv "
            "SAME_SESSION-requests.csv"
        )
    paths = [Path(argument) for argument in sys.argv[1:]]
    baseline_data = read_json(paths[0])
    slack_data = read_json(paths[1])
    baseline_rows = baseline_data["rows"]
    all_slack_rows = slack_data["rows"]
    slack_requests = [paths[2]]
    baseline_requests = [paths[3]]
    paired_rows, _ = compute_paired(baseline_rows)
    capacities = capacity_rows(baseline_rows)
    spill_observations, spill_fits, spill_residuals, miss_rows = spill_analysis(
        all_slack_rows, slack_requests
    )
    spill_trials, spill_summaries = trial_spill_latencies(baseline_requests)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S-%fZ")
    prefix = f"routing-final-analysis-{stamp}"
    output_dir = RESULTS
    write_csv(output_dir / f"{prefix}-paired.csv", paired_rows)
    write_csv(output_dir / f"{prefix}-capacity-model.csv", capacities)
    write_csv(output_dir / f"{prefix}-spill-observations.csv", spill_observations)
    write_csv(output_dir / f"{prefix}-spill-fit.csv", spill_fits)
    write_csv(output_dir / f"{prefix}-spill-residuals.csv", spill_residuals)
    write_csv(output_dir / f"{prefix}-miss-rates.csv", miss_rows)
    write_csv(output_dir / f"{prefix}-spill-latency-trials.csv", spill_trials)
    write_csv(output_dir / f"{prefix}-spill-latency-summary.csv", spill_summaries)
    main_summary = make_main_figures(
        all_slack_rows, baseline_rows, spill_summaries, capacities,
        spill_observations, spill_fits, prefix
    )
    write_csv(output_dir / f"{prefix}-main-summary.csv", main_summary)
    save_paired_figure(paired_rows, prefix)
    report = {
        "sources": [str(path) for path in paths],
        "paired_interval_method": "paired Student t, two-sided 95%, df=9",
        "spill_fit_method": "ordinary least squares, unweighted trial rows, descriptive only",
        "paired_rows": paired_rows,
        "capacity_model": capacities,
        "spill_fit": spill_fits,
        "spill_observations": len(spill_observations),
        "miss_rate_rows": miss_rows,
        "main_summary": main_summary,
    }
    (output_dir / f"{prefix}.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    with (output_dir / f"{prefix}.md").open("w", encoding="utf-8") as output:
        output.write("# Paired routing and capacity analysis\n\n")
        output.write("Sources: " + ", ".join(f"`{path}`" for path in paths) + ".\n\n")
        output.write("Paired intervals are two-sided Student t intervals over ten matched runs (df=9). P95 rankings are claimed only when the paired interval excludes zero. Spill regressions are descriptive ordinary least squares, not causal estimates.\n\n")
        output.write("## Paired differences versus consistent hash\n\n")
        output.write("| Workload | Policy | Metric | Difference | 95% CI | n | Latency ranking |\n|---|---|---|---:|---:|---:|---|\n")
        for row in paired_rows:
            output.write(
                f"| {row['workload']} | {row['policy']} | {row['metric']} | "
                f"{row['difference_policy_minus_consistent_hash']:.6g} | "
                f"[{row['ci95_low']:.6g}, {row['ci95_high']:.6g}] | "
                f"{row['n_pairs']} | {row['latency_ranking_claimed']} |\n"
            )
        output.write("\n## Uniform capacity-model check\n\n")
        output.write("| Policy | Predicted HIT | Compulsory-capped | Measured mean | 95% CI | Distinct keys | Ceiling |\n|---|---:|---:|---:|---:|---:|---:|\n")
        for row in capacities:
            output.write(
                f"| {row['policy']} | {row['prediction_capacity_model']:.4f} | "
                f"{row['prediction_capped_by_compulsory_ceiling']:.4f} | "
                f"{row['measured_hit_mean']:.4f} | "
                f"[{row['measured_hit_ci95_low']:.4f}, {row['measured_hit_ci95_high']:.4f}] | "
                f"{row['distinct_keys_mean']:.2f} | {row['compulsory_miss_hit_ceiling']:.4f} |\n"
            )
        output.write("\n## Spill-fraction regressions\n\n")
        output.write("| Outcome | n | Intercept | Spill slope | R-squared |\n|---|---:|---:|---:|---:|\n")
        for row in spill_fits:
            output.write(
                f"| {row['outcome']} | {row['observations']} | {row['intercept']:.6g} | "
                f"{row['spill_fraction_slope']:.6g} | {row['r_squared']:.6g} |\n"
            )
        output.write("\nResiduals and per-trial fitted values are in the companion CSV; the relationship is descriptive only.\n\n")
        output.write("## Spilled versus non-spilled MISS rates\n\n")
        output.write("| Workload | Slack | Group | Requests | MISS | MISS rate |\n|---|---:|---|---:|---:|---:|\n")
        for row in miss_rows:
            rate = "NA" if row["miss_rate"] is None else f"{row['miss_rate']:.4f}"
            output.write(
                f"| {row['workload']} | {row['slack']} | {row['spill_group']} | "
                f"{row['requests']} | {row['misses']} | {rate} |\n"
            )
    print(json.dumps({
        "status": "PASS",
        "prefix": prefix,
        "paired_rows": len(paired_rows),
        "capacity_rows": len(capacities),
        "spill_trials": len(spill_observations),
        "spill_miss_rate_rows": len(miss_rows),
    }, indent=2))


if __name__ == "__main__":
    main()
