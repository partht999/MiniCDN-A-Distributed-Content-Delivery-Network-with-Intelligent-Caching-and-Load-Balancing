import csv
import json
import math
import os
import re
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
POLICY_COLORS = {
    "consistent_hash": "#2878B5",
    "round_robin": "#E07B39",
    "adaptive": "#43966E",
    "least_loaded_router_local": "#8A69A8",
    "bounded_load_router_local": "#555555",
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


def paired_comparisons(rows):
    reference = {}
    for row in rows:
        if row["policy"] == "consistent_hash":
            run = int(row["trialId"].split("-", 2)[1])
            reference[(row["workload"], run)] = row

    metrics = [
        ("hit_ratio", 100.0, "HIT difference (percentage points)"),
        ("excess_origin_attempts", 1.0, "Excess origin attempts difference"),
        ("request_cv", 1.0, "Request CV difference"),
        ("p95_ms", 1.0, "P95 difference (ms)"),
    ]
    grouped = defaultdict(list)
    for row in rows:
        if row["policy"] == "consistent_hash":
            continue
        run = int(row["trialId"].split("-", 2)[1])
        baseline = reference.get((row["workload"], run))
        if baseline is None:
            continue
        for metric, scale, _ in metrics:
            if row.get(metric) is None or baseline.get(metric) is None:
                continue
            grouped[(
                row["workload"], row["policy"], row.get("slack"), metric, scale
            )].append((float(row[metric]) - float(baseline[metric])) * scale)

    results = []
    for (workload, policy, slack, metric, scale), differences in sorted(grouped.items()):
        average, low, high, count = confidence_interval(differences)
        if count > 1:
            half_width = T95.get(count - 1, 1.96) * math.sqrt(
                sum((value - average) ** 2 for value in differences) / (count - 1)
            ) / math.sqrt(count)
            low, high = average - half_width, average + half_width
        results.append({
            "workload": workload,
            "policy": policy,
            "slack": slack,
            "metric": metric,
            "metric_label": next(label for name, _, label in metrics if name == metric),
            "n_pairs": count,
            "mean_difference_vs_consistent_hash": average,
            "ci95_low": low,
            "ci95_high": high,
            "ci_excludes_zero": low is not None and high is not None and (low > 0 or high < 0),
        })
    return results


def spill_rates_and_regressions(rows, request_paths):
    request_groups = defaultdict(lambda: {"HIT": 0, "MISS": 0})
    for file_path in request_paths:
        with file_path.open(newline="", encoding="utf-8") as source:
            for request in csv.DictReader(source):
                if request.get("policy") != "adaptive":
                    continue
                spill = request.get("spilled")
                status = request.get("cacheStatus")
                if spill not in ("true", "false") or status not in ("HIT", "MISS"):
                    continue
                request_groups[(
                    request["trialId"], request["workload"],
                    int(request.get("slack") or 0),
                    "spilled" if spill == "true" else "non_spilled",
                )][status] += 1

    trial_totals = defaultdict(lambda: {"spilled": 0, "total": 0})
    miss_trial_rates = defaultdict(list)
    for (trial_id, workload, slack, spill), counts in request_groups.items():
        total = counts["HIT"] + counts["MISS"]
        if total == 0:
            continue
        trial_totals[(trial_id, workload, slack)]["total"] += total
        trial_totals[(trial_id, workload, slack)]["spilled"] += (
            total if spill == "spilled" else 0
        )
        miss_trial_rates[(workload, slack, spill)].append({
            "trial_id": trial_id,
            "total_requests": total,
            "misses": counts["MISS"],
            "miss_rate": counts["MISS"] / total,
        })

    spill_trials = []
    for (trial_id, workload, slack), counts in sorted(trial_totals.items()):
        if counts["total"] == 0:
            continue
        spill_trials.append({
            "trial_id": trial_id,
            "workload": workload,
            "slack": slack,
            "classified_requests": counts["total"],
            "spilled_requests": counts["spilled"],
            "spill_fraction": counts["spilled"] / counts["total"],
        })

    miss_rate_summaries = []
    for (workload, slack, spill), values in sorted(miss_trial_rates.items()):
        rates = [row["miss_rate"] * 100 for row in values]
        mean, low, high, count = confidence_interval(rates)
        miss_rate_summaries.append({
            "workload": workload,
            "slack": slack,
            "spill_group": spill,
            "n_trials": count,
            "mean_miss_rate_percent": mean,
            "ci95_low_percent": low,
            "ci95_high_percent": high,
            "classified_requests_total": sum(row["total_requests"] for row in values),
        })

    spill_by_trial = {row["trial_id"]: row for row in spill_trials}
    trial_by_id = {row["trialId"]: row for row in rows if row["policy"] == "adaptive"}
    regression_rows = []
    regression_summaries = []
    for metric, label in [
        ("hit_ratio", "HIT ratio"),
        ("excess_origin_attempts", "Excess origin attempts"),
    ]:
        points = []
        for trial_id, spill_row in spill_by_trial.items():
            trial = trial_by_id.get(trial_id)
            if trial is None or trial.get(metric) is None:
                continue
            x = float(spill_row["spill_fraction"])
            y = float(trial[metric]) * (100 if metric == "hit_ratio" else 1)
            points.append((trial_id, spill_row, x, y))
        mean_x = sum(point[2] for point in points) / len(points)
        mean_y = sum(point[3] for point in points) / len(points)
        sxx = sum((point[2] - mean_x) ** 2 for point in points)
        slope = (
            sum((point[2] - mean_x) * (point[3] - mean_y) for point in points) / sxx
            if sxx else 0.0
        )
        intercept = mean_y - slope * mean_x
        sse = 0.0
        sst = 0.0
        predictions = []
        for trial_id, spill_row, x, y in points:
            predicted = intercept + slope * x
            residual = y - predicted
            sse += residual ** 2
            sst += (y - mean_y) ** 2
            predictions.append((trial_id, spill_row, x, y, predicted, residual))
        regression_summaries.append({
            "metric": metric,
            "metric_label": label,
            "n_trials": len(points),
            "intercept": intercept,
            "slope_per_spill_fraction": slope,
            "r_squared": 1 - sse / sst if sst else 1.0,
            "residual_rmse": math.sqrt(sse / len(points)),
            "residual_mean_absolute": sum(abs(item[5]) for item in predictions) / len(points),
            "residual_max_absolute": max(abs(item[5]) for item in predictions),
        })
        regression_rows.extend({
            "trial_id": trial_id,
            "workload": spill_row["workload"],
            "slack": spill_row["slack"],
            "spill_fraction": x,
            "metric": metric,
            "observed": y,
            "predicted": predicted,
            "residual": residual,
        } for trial_id, spill_row, x, y, predicted, residual in predictions)
    return spill_trials, miss_rate_summaries, regression_rows, regression_summaries


def save_paired_figure(paired_rows, prefix):
    metrics = [
        ("hit_ratio", "HIT (pp)"),
        ("excess_origin_attempts", "Excess attempts"),
        ("request_cv", "Request CV"),
        ("p95_ms", "P95 (ms)"),
    ]
    workloads = list(WORKLOAD_COLORS)
    conditions = [
        ("round_robin", None, "RR"),
        *[("adaptive", slack, f"A{slack}") for slack in (0, 1, 2, 4, 8, 1000)],
    ]
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), squeeze=False)
    offsets = {workload: (index - (len(workloads) - 1) / 2) * 0.13
               for index, workload in enumerate(workloads)}
    for (metric, label), ax in zip(metrics, axes.flat):
        selected = [row for row in paired_rows if row["metric"] == metric]
        for workload in workloads:
            for position, (policy, slack, _) in enumerate(conditions):
                row = next((
                    item for item in selected
                    if item["workload"] == workload
                    and item["policy"] == policy
                    and item["slack"] == slack
                ), None)
                if row is None:
                    continue
                value = row["mean_difference_vs_consistent_hash"]
                low, high = row["ci95_low"], row["ci95_high"]
                ax.errorbar(
                    position + offsets[workload], value,
                    yerr=[[value - low], [high - value]],
                    fmt="o", color=WORKLOAD_COLORS[workload],
                    capsize=2, markersize=4,
                )
        ax.axhline(0, color="#333333", linewidth=0.8)
        ax.set_title(label)
        ax.set_xticks(range(len(conditions)), labels=[name for _, _, name in conditions],
                      rotation=45, ha="right")
        ax.grid(axis="y", alpha=0.25)
    axes[1][0].set_xlabel("Policy / adaptive slack")
    axes[1][1].set_xlabel("Policy / adaptive slack")
    handles = [
        plt.Line2D([], [], color=WORKLOAD_COLORS[name], marker="o",
                   linestyle="", label=name.replace("_", " "))
        for name in workloads
    ]
    fig.legend(
        handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.965),
        ncol=4, frameon=False, fontsize=8,
    )
    fig.suptitle(
        "Paired per-run differences versus consistent hashing (95% t-intervals)",
        y=0.995,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    save_svg(fig, FIGURES / f"{prefix}-paired-differences.svg")
    fig.savefig(FIGURES / f"{prefix}-paired-differences.pdf", format="pdf")
    plt.close(fig)


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

    fig, axes = plt.subplots(2, 2, figsize=(11, 8), squeeze=False)
    observed_policies = sorted({row["policy"] for row in summaries})
    for (workload, _), ax in zip(WORKLOAD_COLORS.items(), axes.flat):
        workload_rows = [row for row in summaries if row["workload"] == workload]
        for row in workload_rows:
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
                x, y, xerr=xerr, yerr=yerr,
                fmt=POLICY_MARKERS.get(row["policy"], "o"),
                color=POLICY_COLORS.get(row["policy"], "#333333"),
                alpha=0.78, capsize=2, markersize=5,
            )
            if row["policy"] == "adaptive":
                ax.annotate(
                    str(row["slack"]), (x, y), xytext=(3, 3),
                    textcoords="offset points", fontsize=7,
                )
        ax.set_title(workload.replace("_", " "))
        ax.set_xlabel("Request-count CV")
        ax.set_ylabel("Excess origin attempts / trial")
        ax.grid(alpha=0.25)
    policy_handles = [
        plt.Line2D(
            [], [], color=POLICY_COLORS[policy], marker=POLICY_MARKERS[policy],
            linestyle="", label=(
                "adaptive (slack labels)" if policy == "adaptive"
                else policy.replace("_", " ")
            ),
        )
        for policy in observed_policies
    ]
    fig.legend(handles=policy_handles, loc="upper center", ncol=len(policy_handles))
    fig.suptitle("Routing balance versus excess origin work by workload")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
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
        if metric == "p95_ms":
            y_cap = 200
            clipped = [
                row for row in selected
                if row["p95_ms_ci95_high"] is not None
                and row["p95_ms_ci95_high"] > y_cap
            ]
            ax.set_ylim(0, y_cap)
            if clipped:
                details = "; ".join(
                    f"{row['workload']} slack {row['slack']}: upper CI "
                    f"{row['p95_ms_ci95_high']:.1f} ms, "
                    f"{row['error_requests_total']} errors"
                    for row in clipped
                )
                ax.text(
                    0.02, 0.98, f"Axis capped at {y_cap} ms. {details}",
                    transform=ax.transAxes, va="top", fontsize=7,
                    bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "none"},
                )
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
    spill_states = []
    for row in selected_spill:
        workload = row["workload"].replace("_", " ")
        cache_status = row["cache_status"]
        spill_state = "spilled" if row["spill"] == "spilled" else "non-spilled"
        categories.append(f"{workload} / {cache_status} / {spill_state}")
        spill_states.append(spill_state)
        value = row["p95_ms_mean"]
        low = row["p95_ms_ci95_low"]
        high = row["p95_ms_ci95_high"]
        values.append(value)
        errors.append((value - low, high - value) if low is not None else (0, 0))
    positions = list(range(len(values)))
    fig, ax = plt.subplots(figsize=(12, 6))
    palette = ["#43966E" if state == "spilled" else "#2878B5" for state in spill_states]
    ax.barh(positions, values, color=palette, alpha=0.82)
    for index, (value, (low, high)) in enumerate(zip(values, errors)):
        ax.errorbar(value, index, xerr=[[low], [high]], fmt="none", ecolor="#222222", capsize=3)
    ax.set_yticks(positions, labels=categories, fontsize=9)
    ax.set_xlabel("Per-trial request P95 (ms), mean ± bootstrap 95% CI")
    ax.set_title("Adaptive slack 2: spilled versus non-spilled latency by cache status")
    ax.grid(axis="x", alpha=0.25)
    ax.invert_yaxis()
    ax.margins(y=0.03)
    fig.tight_layout()
    save_svg(fig, FIGURES / f"{prefix}-spilled-latency.svg")
    fig.savefig(FIGURES / f"{prefix}-spilled-latency.pdf", format="pdf")
    plt.close(fig)


def make_markdown(summary_rows, spill_rows, paired_rows, spill_rate_rows,
                  regression_rows, regression_summaries, source_names, prefix):
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
        "## Paired differences versus consistent hashing",
        "",
        "Differences are computed within matching workload/run seeds from the primary",
        "same-session sweep, with adaptive/round-robin minus consistent hash. Intervals",
        "are two-sided 95% paired Student t-intervals over the ten run-level differences.",
        "The condition order was not randomized, so paired intervals do not remove possible",
        "time/order effects. The full workload/metric table is in the paired CSV.",
        "",
        "| Zipf condition | HIT difference (pp) | Excess attempts | Request CV | P95 difference (ms) | Latency CI excludes zero? |",
        "|---|---:|---:|---:|---:|---|",
    ])
    zipf_pairs = {
        (row["policy"], row["slack"], row["metric"]): row
        for row in paired_rows if row["workload"] == "zipf"
    }
    for policy, slack, label in [
        ("round_robin", None, "round robin"),
        *[("adaptive", slack_value, f"adaptive slack {slack_value}")
          for slack_value in (0, 1, 2, 4, 8, 1000)],
    ]:
        def paired_value(metric):
            row = zipf_pairs.get((policy, slack, metric))
            if row is None:
                return "NA"
            return fmt_ci(
                row["mean_difference_vs_consistent_hash"],
                row["ci95_low"], row["ci95_high"], 2,
            )
        p95 = zipf_pairs.get((policy, slack, "p95_ms"))
        latency_sig = "yes" if p95 and p95["ci_excludes_zero"] else "no"
        lines.append(
            f"| {label} | {paired_value('hit_ratio')} | "
            f"{paired_value('excess_origin_attempts')} | "
            f"{paired_value('request_cv')} | {paired_value('p95_ms')} | {latency_sig} |"
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
        "## Spill fraction and cache-miss rates",
        "",
        "Only requests with a recorded spill flag and HIT/MISS classification are included.",
        "Miss-rate means and 95% Student t-intervals are computed across per-trial rates;",
        "the CSV includes classified request totals. The regression is descriptive pooled",
        "ordinary least squares across adaptive trials, with no causal interpretation.",
        "",
        "| Workload | Slack | Non-spilled MISS (%) | Spilled MISS (%) |",
        "|---|---:|---:|---:|",
    ])
    rates_by_key = {
        (row["workload"], row["slack"], row["spill_group"]): row
        for row in spill_rate_rows
    }
    for workload in sorted(WORKLOAD_COLORS):
        for slack in (0, 1, 2, 4, 8, 1000):
            entries = []
            for spill in ("non_spilled", "spilled"):
                row = rates_by_key.get((workload, slack, spill))
                entries.append(
                    "NA" if row is None else fmt_ci(
                        row["mean_miss_rate_percent"],
                        row["ci95_low_percent"], row["ci95_high_percent"], 2,
                    )
                )
            lines.append(f"| {workload} | {slack} | {entries[0]} | {entries[1]} |")
    lines.extend([
        "",
        "## Spill-fraction regression",
        "",
        "| Outcome | n | Intercept | Slope per 1.0 spill fraction | R² | Residual RMSE | Mean absolute residual | Maximum absolute residual |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in regression_summaries:
        lines.append(
            f"| {row['metric_label']} | {row['n_trials']} | {row['intercept']:.3f} "
            f"| {row['slope_per_spill_fraction']:.3f} | {row['r_squared']:.4f} "
            f"| {row['residual_rmse']:.3f} | {row['residual_mean_absolute']:.3f} "
            f"| {row['residual_max_absolute']:.3f} |"
        )
    lines.extend([
        "",
        "Largest absolute residuals (trial-level values and all residuals are in the regression CSV):",
        "",
        "| Outcome | Trial | Observed | Predicted | Residual |",
        "|---|---|---:|---:|---:|",
    ])
    for metric in ("hit_ratio", "excess_origin_attempts"):
        largest = sorted(
            (row for row in regression_rows if row["metric"] == metric),
            key=lambda row: abs(row["residual"]), reverse=True,
        )[:3]
        for row in largest:
            lines.append(
                f"| {metric} | {row['trial_id']} | {row['observed']:.3f} "
                f"| {row['predicted']:.3f} | {row['residual']:.3f} |"
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
        f"- Paired differences versus consistent hash: `{prefix}-paired.csv` and `figures/{prefix}-paired-differences.pdf`.",
        f"- Per-trial spill percentiles and summary: `{prefix}-spill-trials.csv` and `{prefix}-spill-summary.csv`.",
        f"- Spill fraction by trial, spill MISS rates, and OLS residuals: `{prefix}-spill-fraction-trials.csv`, `{prefix}-spill-miss-rates.csv`, `{prefix}-spill-regression-trials.csv`, `{prefix}-spill-regression-summary.csv`.",
        "",
        "A nonzero request-error count is retained as measured; do not silently exclude those trials.",
        "For any error trial, the reported latency percentile includes completed HTTP responses and",
        "client-side failures as recorded in the trial summary; interpret its tail alongside errors.",
        "",
    ])
    return "\n".join(lines)


input_paths = [Path(argument) for argument in sys.argv[1:]]
trial_paths = [file_path for file_path in input_paths if file_path.suffix.lower() == ".json"]
request_paths = [file_path for file_path in input_paths if file_path.suffix.lower() == ".csv"]
if not trial_paths or len(trial_paths) + len(request_paths) != len(input_paths):
    raise SystemExit(
        "Usage: python scripts/analyze-routing-sweep.py <trial-results.json> "
        "[additional-trial-results.json ...] [request-export.csv ...]"
    )

all_trial_rows = read_trial_files(trial_paths)
summaries = summarize_trials(all_trial_rows)
spill_trials, spill_summaries = summarize_spills(request_paths) if request_paths else ([], [])
spill_fraction_trials, spill_miss_rates, spill_regression_trials, spill_regression_summary = (
    spill_rates_and_regressions(all_trial_rows, request_paths)
    if request_paths else ([], [], [], [])
)
requested_prefix = os.environ.get("ANALYSIS_PREFIX")
if requested_prefix and not re.fullmatch(r"[A-Za-z0-9._-]+", requested_prefix):
    raise SystemExit("ANALYSIS_PREFIX may contain only letters, digits, dot, underscore, and hyphen.")
prefix = requested_prefix or f"routing-analysis-{__import__('datetime').date.today().isoformat()}"
save_csv(RESULTS / f"{prefix}-summary.csv", summaries)
save_csv(RESULTS / f"{prefix}-spill-trials.csv", spill_trials)
save_csv(RESULTS / f"{prefix}-spill-summary.csv", spill_summaries)
save_csv(RESULTS / f"{prefix}-spill-fraction-trials.csv", spill_fraction_trials)
save_csv(RESULTS / f"{prefix}-spill-miss-rates.csv", spill_miss_rates)
save_csv(RESULTS / f"{prefix}-spill-regression-trials.csv", spill_regression_trials)
save_csv(RESULTS / f"{prefix}-spill-regression-summary.csv", spill_regression_summary)
paired_rows = paired_comparisons(all_trial_rows)
save_csv(RESULTS / f"{prefix}-paired.csv", paired_rows)
save_figures(summaries, spill_summaries, prefix)
save_paired_figure(paired_rows, prefix)
(RESULTS / f"{prefix}.md").write_text(
    make_markdown(
        summaries, spill_summaries, paired_rows, spill_miss_rates,
        spill_regression_trials, spill_regression_summary,
        [file.name for file in trial_paths], prefix,
    ),
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
    "paired_differences_vs_consistent_hash": paired_rows,
    "spill_fraction_trials": spill_fraction_trials,
    "spill_miss_rates": spill_miss_rates,
    "spill_regression_trials": spill_regression_trials,
    "spill_regression_summary": spill_regression_summary,
}, indent=2) + "\n", encoding="utf-8")
print(json.dumps({
    "status": "PASS",
    "trial_rows": len(all_trial_rows),
    "summary_groups": len(summaries),
    "spill_trial_groups": len(spill_trials),
    "spill_summary_groups": len(spill_summaries),
    "paired_comparisons": len(paired_rows),
    "spill_fraction_trials": len(spill_fraction_trials),
    "spill_miss_rate_groups": len(spill_miss_rates),
    "spill_regression_rows": len(spill_regression_trials),
    "outputs": [
        f"{prefix}.md", f"{prefix}.json", f"{prefix}-summary.csv", f"{prefix}-paired.csv",
        f"{prefix}-spill-trials.csv", f"{prefix}-spill-summary.csv",
        f"{prefix}-spill-fraction-trials.csv", f"{prefix}-spill-miss-rates.csv",
        f"{prefix}-spill-regression-trials.csv", f"{prefix}-spill-regression-summary.csv",
        *(f"figures/{prefix}-{chart}.{extension}" for chart in (
            "pareto", "hit-ratio", "p95", "spilled-latency", "paired-differences"
        ) for extension in ("svg", "pdf")),
    ],
}, indent=2))
