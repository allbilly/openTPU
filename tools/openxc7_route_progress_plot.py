#!/usr/bin/env python3
"""Plot observed Router2 counters and constant-rate scenarios without touching it.

Run with an isolated plotting environment, for example:
    uv run --no-project --with matplotlib python tools/openxc7_route_progress_plot.py
"""

import argparse
import csv
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


ROOT = Path(__file__).resolve().parents[1]
HKT = ZoneInfo("Asia/Hong_Kong")


def interpolate(rows, when):
    for before, after in zip(rows, rows[1:]):
        if before["time"] <= when <= after["time"]:
            fraction = (when - before["time"]).total_seconds() / (
                after["time"] - before["time"]
            ).total_seconds()
            return before["remaining"] + fraction * (
                after["remaining"] - before["remaining"]
            )
    raise ValueError("Projection window exceeds the recorded history")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--observer", type=Path,
        default=ROOT / "build/fedora-openxc7/routing-five-minute-observer-20261013T104000Z",
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs/plots")
    args = parser.parse_args()
    rows, skipped = [], []
    identity = None
    for path in sorted(args.observer.glob("sample-*/manifest.json")):
        raw = path.read_bytes()
        try:
            receipt = json.loads(raw)
        except json.JSONDecodeError:
            skipped.append({"path": str(path), "reason": "incomplete JSON"})
            continue
        metrics = receipt.get("metrics")
        if receipt.get("status") != "LIVE_ROUTING_METRICS_SAMPLE_PASS" or not isinstance(metrics, dict):
            skipped.append({"path": str(path), "reason": "not a successful metrics sample"})
            continue
        before, after = receipt["before"], receipt["after"]
        current = (
            before["pid"], before["start_ticks"],
            metrics["unique_connection_identity_sha256"],
            metrics["unique_driven_sink_connections"], metrics["router_iteration"],
        )
        if (after["pid"], after["start_ticks"]) != current[:2] or receipt["route_restarted"]:
            raise ValueError(f"Native identity changed in {path}")
        if identity is not None and current != identity:
            raise ValueError("History spans different native runs, connection inventories or iterations")
        identity = current
        rows.append({
            "time": datetime.fromisoformat(receipt["observed_utc"]),
            "remaining": metrics["connections_remaining_without_routed_flag"],
            "active_workers": len(metrics["workers"]),
            "queue": metrics["sampled_largest_combined_queue"],
            "path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
        })
    rows.sort(key=lambda row: row["time"])
    if len(rows) < 3:
        raise ValueError("Need at least three compatible observations")
    first, last = rows[0], rows[-1]
    hours_recorded = (last["time"] - first["time"]).total_seconds() / 3600
    scenarios = []
    for hours, label, color in [
        (2, "Last 2 hours", "#19855d"),
        (1, "Last 1 hour", "#2463b6"),
        (0.5, "Last 30 minutes", "#c27518"),
    ]:
        window_start = last["time"] - timedelta(hours=hours)
        rate = (interpolate(rows, window_start) - last["remaining"]) / hours
        eta = last["remaining"] / rate if rate > 0 else None
        interval_decreases = []
        for before, after in zip(rows, rows[1:]):
            if after["time"] <= window_start:
                continue
            seconds = (after["time"] - before["time"]).total_seconds()
            overlap = (after["time"] - max(before["time"], window_start)).total_seconds()
            decrease = before["remaining"] - after["remaining"]
            interval_decreases.append((decrease * overlap / seconds, after))
        largest_interval, interval_row = max(interval_decreases, key=lambda item: item[0])
        interval_share = largest_interval / (rate * hours) if rate > 0 else None
        scenarios.append({
            "label": label, "window_hours": hours,
            "connections_per_hour": rate, "hours_to_zero_if_rate_constant": eta,
            "projected_zero_hkt": (last["time"] + timedelta(hours=eta)).astimezone(HKT).isoformat() if eta else None,
            "color": color,
            "largest_interval_decrease_within_window": largest_interval,
            "largest_interval_end_utc": interval_row["time"].isoformat(),
            "largest_interval_share_of_window_decrease": interval_share,
            "dominated_by_one_sample_interval": interval_share is not None and interval_share > 0.5,
        })
    all_rate = (first["remaining"] - last["remaining"]) / hours_recorded
    recent_drops = [
        (before["remaining"] - after["remaining"], after)
        for before, after in zip(rows, rows[1:])
        if after["time"] > last["time"] - timedelta(hours=2)
    ]
    largest_drop, drop_row = max(recent_drops, key=lambda item: item[0])
    drop_share = scenarios[1]["largest_interval_share_of_window_decrease"]
    burst_dominated = any(s["dominated_by_one_sample_interval"] for s in scenarios)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = args.output_dir / f"openxc7_routing_progress_{last['time'].strftime('%Y%m%dT%H%M%SZ')}"
    with stem.with_suffix(".csv").open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["observed_utc", "observed_hkt", "remaining_connections", "active_workers", "sampled_combined_queue", "source_manifest", "source_sha256"])
        for row in rows:
            writer.writerow([row["time"].isoformat(), row["time"].astimezone(HKT).isoformat(), row["remaining"], row["active_workers"], row["queue"], row["path"], row["sha256"]])
    summary = {
        "status": "OBSERVED_ROUTING_HISTORY_AND_CONDITIONAL_RATE_PROJECTIONS",
        "native_pid": identity[0], "native_start_ticks": identity[1],
        "connection_identity_sha256": identity[2], "total_connections": identity[3],
        "router_iteration": identity[4], "successful_samples": len(rows),
        "first_observed_utc": first["time"].isoformat(),
        "latest_observed_utc": last["time"].isoformat(),
        "latest_remaining": last["remaining"], "recorded_hours": hours_recorded,
        "all_history_connections_per_hour": all_rate,
        "all_history_hours_to_zero_if_rate_constant": last["remaining"] / all_rate,
        "scenarios": scenarios, "skipped_samples": skipped,
        "largest_recent_sample_decrease": largest_drop,
        "largest_decrease_observed_utc": drop_row["time"].isoformat(),
        "largest_last_hour_interval_share": drop_share,
        "recent_projections_dominated_by_one_sample_interval": burst_dominated,
        "method": "Endpoint decrease divided by window hours; linearly interpolate the starting count between adjacent snapshots.",
        "interval_dominance_method": "Largest interval decrease divided by the window decrease, prorating a boundary interval using the same linear interpolation; dominance means more than half of the decrease.",
        "limitations": [
            "Remaining means unique driven net/sink-wire pairs without a routed flag, not unresolved legal-congestion proof.",
            "Rates can change across routing phases and individual searches.",
            "First iteration is incomplete; cross-partition routing and later congestion/retry work remain.",
            "Scenarios are not confidence intervals, convergence guarantees or bitstream completion times.",
            "Full numeric timing and full image qualification remain after native routing.",
        ],
    }
    stem.with_suffix(".json").write_text(json.dumps(summary, indent=2) + "\n")
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, (observed, forecast) = plt.subplots(1, 2, figsize=(13, 5.8), gridspec_kw={"width_ratios": [1.15, 1]})
    times = [row["time"] for row in rows]
    counts = [row["remaining"] for row in rows]
    observed.plot(times, counts, color="#2463b6", linewidth=2, marker="o", markersize=3)
    observed.set_title(f"Measured progress — {len(rows)} successful samples", loc="left", fontweight="bold")
    first_hkt, last_hkt = first["time"].astimezone(HKT), last["time"].astimezone(HKT)
    date_label = first_hkt.strftime("%B %d, %Y")
    if first_hkt.date() != last_hkt.date():
        date_label += " to " + last_hkt.strftime("%B %d, %Y")
    observed.set_xlabel(date_label + " — Hong Kong time")
    observed.set_ylabel("Connections without a routed flag")
    observed.xaxis.set_major_locator(mdates.AutoDateLocator(tz=HKT, minticks=4, maxticks=8))
    observed.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=HKT))
    observed.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:,.0f}"))
    observed.grid(alpha=0.2)
    observed.annotate(f"{last['remaining']:,} at {last['time'].astimezone(HKT):%H:%M}",
                      xy=(last["time"], last["remaining"]), xytext=(-12, 22),
                      textcoords="offset points", ha="right", fontweight="bold")
    one_worker = next((row for row in rows if row["active_workers"] == 1), None)
    if one_worker:
        observed.axvline(one_worker["time"], color="#7b7b7b", linestyle=":", linewidth=1)
        observed.text(one_worker["time"], max(counts) - 2000, "  One worker observed", fontsize=9, color="#555555", va="top")
    observed.margins(y=0.15)
    if burst_dominated:
        dominant = max(
            (s for s in scenarios if s["dominated_by_one_sample_interval"]),
            key=lambda s: s["largest_interval_share_of_window_decrease"],
        )
        interval_end = datetime.fromisoformat(dominant["largest_interval_end_utc"])
        highlight = next(row for row in rows if row["time"] == interval_end)
        observed.annotate(
            f"{dominant['label']}: {dominant['largest_interval_share_of_window_decrease']:.0%} of decrease\n"
            f"{dominant['largest_interval_decrease_within_window']:,.0f} connections in one interval",
            xy=(highlight["time"], highlight["remaining"]),
            xytext=(-15, 45), textcoords="offset points", ha="right",
            fontsize=9, color="#9a5010",
            arrowprops={"arrowstyle": "->", "color": "#9a5010"},
        )
    forecast.set_title("If the observed rate stayed constant", loc="left", fontweight="bold")
    for scenario in scenarios:
        eta = scenario["hours_to_zero_if_rate_constant"]
        if eta is None:
            continue
        marker = " *" if scenario["dominated_by_one_sample_interval"] else ""
        forecast.plot([0, eta], [last["remaining"], 0], linestyle="--", linewidth=2,
                      color=scenario["color"], label=f"{scenario['label']}: {eta:.0f} h ({eta / 24:.1f} days){marker}")
        forecast.scatter([eta], [0], color=scenario["color"], s=30, zorder=3)
    forecast.set_xlabel("Additional hours from the latest observation")
    forecast.set_ylabel("Projected connections without a routed flag")
    forecast.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x / 1000:,.0f}k"))
    forecast.set_ylim(-15000, last["remaining"] * 1.08)
    forecast.set_xlim(0, max(s["hours_to_zero_if_rate_constant"] or 0 for s in scenarios) * 1.08)
    forecast.legend(loc="upper right", frameon=False, fontsize=9)
    forecast.grid(alpha=0.2)
    if burst_dominated:
        forecast.text(
            0.04, 0.08,
            "* Rate dominated by one sampling interval.\n"
            "No dependable bitstream completion ETA.",
            transform=forecast.transAxes, fontsize=9, color="#9a5010",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.9},
        )
    fig.suptitle("OpenXC7 full-design routing: observed progress and conditional projections", x=0.06, ha="left", fontsize=14, fontweight="bold")
    fig.text(0.06, 0.03, "Zero routed-flag gaps does not establish legal routing. Cross-partition work, congestion retries, timing and image checks remain.", fontsize=9, color="#555555")
    fig.tight_layout(rect=(0.02, 0.07, 0.99, 0.92))
    fig.savefig(stem.with_suffix(".png"), dpi=160)
    fig.savefig(stem.with_suffix(".svg"))
    print(json.dumps({"plot": str(stem.with_suffix('.png')), **summary}, indent=2))


if __name__ == "__main__":
    main()
