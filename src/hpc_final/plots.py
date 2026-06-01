from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def _save(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def generate_plots(summary_dir: str | Path, figures_dir: str | Path) -> list[Path]:
    summary_path = Path(summary_dir)
    figures_path = Path(figures_dir)
    generated: list[Path] = []

    all_runs_path = summary_path / "all_runs.csv"
    pipeline_path = summary_path / "pipeline_runs.csv"
    feasible_path = summary_path / "feasible_designs.csv"
    pareto_path = summary_path / "pareto_frontier.csv"
    bottleneck_path = summary_path / "bottleneck_summary.csv"
    if not pipeline_path.exists():
        return generated

    pipeline = pd.read_csv(pipeline_path)
    if pipeline.empty:
        return generated

    fig, ax = plt.subplots(figsize=(8, 5))
    for (resolution, kernel), group in pipeline.groupby(["resolution", "gaussian_kernel"]):
        subset = group.groupby("array_size", as_index=False)["latency_ms"].min()
        ax.plot(subset["array_size"], subset["latency_ms"], marker="o", label=f"{resolution} k={kernel}")
    ax.set_xlabel("Array size")
    ax.set_ylabel("Best latency per frame (ms)")
    ax.set_title("Latency vs array size")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7)
    path = figures_path / "latency_by_array.png"
    _save(fig, path)
    generated.append(path)

    fig, ax = plt.subplots(figsize=(8, 5))
    for (resolution, kernel), group in pipeline.groupby(["resolution", "gaussian_kernel"]):
        subset = group.groupby("array_size", as_index=False)["energy_total_mj"].min()
        ax.plot(subset["array_size"], subset["energy_total_mj"], marker="o", label=f"{resolution} k={kernel}")
    ax.set_xlabel("Array size")
    ax.set_ylabel("Best energy per frame (mJ)")
    ax.set_title("Energy vs array size")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7)
    path = figures_path / "energy_by_array.png"
    _save(fig, path)
    generated.append(path)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(pipeline["latency_ms"], pipeline["energy_total_mj"], c=pipeline["array_size"], cmap="viridis", alpha=0.75)
    ax.set_xlabel("Latency per frame (ms)")
    ax.set_ylabel("Energy per frame (mJ)")
    ax.set_title("Energy-delay design space")
    ax.grid(True, alpha=0.3)
    path = figures_path / "energy_latency_scatter.png"
    _save(fig, path)
    generated.append(path)

    fig, ax = plt.subplots(figsize=(8, 5))
    for (resolution, kernel), group in pipeline.groupby(["resolution", "gaussian_kernel"]):
        best = group.sort_values("latency_ms").groupby("array_size", as_index=False).first()
        ax.plot(best["array_size"], best["stall_pct"], marker="o", label=f"{resolution} k={kernel}")
    ax.set_xlabel("Array size")
    ax.set_ylabel("Stall cycles (%)")
    ax.set_title("Stall rate of fastest design at each array size")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7)
    path = figures_path / "stall_pct_by_array.png"
    _save(fig, path)
    generated.append(path)

    traffic = pipeline.groupby("array_size", as_index=False).agg(
        sram_mb=("total_sram_accesses", lambda x: x.median() / 1_000_000),
        dram_mb=("total_dram_accesses", lambda x: x.median() / 1_000_000),
    )
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(traffic["array_size"], traffic["sram_mb"], marker="o", label="SRAM")
    ax.plot(traffic["array_size"], traffic["dram_mb"], marker="o", label="DRAM")
    ax.set_xlabel("Array size")
    ax.set_ylabel("Median traffic per frame (MB)")
    ax.set_title("Memory traffic vs array size")
    ax.grid(True, alpha=0.3)
    ax.legend()
    path = figures_path / "memory_traffic_by_array.png"
    _save(fig, path)
    generated.append(path)

    if all_runs_path.exists():
        all_runs = pd.read_csv(all_runs_path)
        if not all_runs.empty:
            weighted = all_runs.copy()
            weighted["util_cycles"] = weighted["overall_util_pct"] * weighted["scaled_cycles"]
            util = (
                weighted.groupby(["resolution", "gaussian_kernel", "array_size"], as_index=False)
                .agg(util_cycles=("util_cycles", "sum"), scaled_cycles=("scaled_cycles", "sum"))
            )
            util["weighted_util_pct"] = util["util_cycles"] / util["scaled_cycles"].where(util["scaled_cycles"] != 0, 1)
            fig, ax = plt.subplots(figsize=(8, 5))
            for (resolution, kernel), group in util.groupby(["resolution", "gaussian_kernel"]):
                ax.plot(group["array_size"], group["weighted_util_pct"], marker="o", label=f"{resolution} k={kernel}")
            ax.set_xlabel("Array size")
            ax.set_ylabel("Cycle-weighted utilization (%)")
            ax.set_title("Utilization vs array size")
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=7)
            path = figures_path / "utilization_by_array.png"
            _save(fig, path)
            generated.append(path)

    if feasible_path.exists():
        feasible = pd.read_csv(feasible_path)
        if not feasible.empty:
            counts = feasible.groupby(["resolution", "deadline_ms"])["feasible"].sum().reset_index()
            fig, ax = plt.subplots(figsize=(7, 4))
            labels = [f"{r}\n{d:g}ms" for r, d in zip(counts["resolution"], counts["deadline_ms"])]
            ax.bar(labels, counts["feasible"])
            ax.set_ylabel("Feasible design count")
            ax.set_title("Feasible configurations")
            path = figures_path / "feasible_counts.png"
            _save(fig, path)
            generated.append(path)

    if pareto_path.exists():
        pareto = pd.read_csv(pareto_path)
        if not pareto.empty:
            pareto = pareto.drop_duplicates(
                subset=[
                    "resolution",
                    "gaussian_kernel",
                    "array_size",
                    "sram_budget_kb",
                    "bandwidth_gbps",
                    "dataflow",
                    "latency_ms",
                    "energy_total_mj",
                ]
            )
            fig, ax = plt.subplots(figsize=(7, 5))
            ax.scatter(pipeline["latency_ms"], pipeline["energy_total_mj"], color="0.82", s=14, label="All designs")
            for (resolution, kernel), group in pareto.groupby(["resolution", "gaussian_kernel"]):
                group = group.sort_values("latency_ms")
                ax.plot(group["latency_ms"], group["energy_total_mj"], marker="o", linewidth=1.5, label=f"{resolution} k={kernel}")
            ax.set_xlabel("Latency per frame (ms)")
            ax.set_ylabel("Energy per frame (mJ)")
            ax.set_title("Pareto frontier")
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=7)
            path = figures_path / "pareto_frontier.png"
            _save(fig, path)
            generated.append(path)

    if bottleneck_path.exists():
        bottleneck = pd.read_csv(bottleneck_path)
        if not bottleneck.empty:
            share = bottleneck.groupby("stage_op", as_index=False)["energy_share_pct"].mean()
            fig, ax = plt.subplots(figsize=(5, 4))
            ax.bar(share["stage_op"], share["energy_share_pct"])
            ax.set_ylabel("Mean energy share (%)")
            ax.set_title("Stage energy contribution")
            path = figures_path / "stage_energy_share.png"
            _save(fig, path)
            generated.append(path)

    return generated
