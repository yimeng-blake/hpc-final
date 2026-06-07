from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd


def _save(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_stacked_percent_bars(
    labels: list[str],
    series: list[tuple[str, list[float], str]],
    title: str,
    path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    bottoms = [0.0] * len(labels)
    for name, values, color in series:
        bars = ax.bar(labels, values, bottom=bottoms, label=name, color=color, edgecolor="white", linewidth=0.8)
        for bar, value, bottom in zip(bars, values, bottoms):
            if value >= 8:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bottom + value / 2,
                    f"{value:.0f}%",
                    ha="center",
                    va="center",
                    color="white" if color != "#C9C9C9" else "black",
                    fontsize=8,
                )
        bottoms = [bottom + value for bottom, value in zip(bottoms, values)]

    ax.set_ylim(0, 100)
    ax.set_ylabel("Share of modeled dynamic energy (%)")
    ax.set_xlabel("Gaussian kernel")
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="upper right", fontsize=8, frameon=True)
    _save(fig, path)


def _selected_1080p_winners(summary_path: Path, deadline_ms: float = 33.0) -> pd.DataFrame:
    winner_path = summary_path / "minimum_energy_designs.csv"
    if not winner_path.exists():
        return pd.DataFrame()
    winners = pd.read_csv(winner_path)
    if winners.empty:
        return winners
    winners = winners[(winners["resolution"] == "1080p") & (winners["deadline_ms"].round(6) == deadline_ms)].copy()
    winners = winners.sort_values("gaussian_kernel")
    if winners.empty:
        return winners
    winners["mac_pct"] = winners["energy_mac_pj"] / winners["energy_total_pj"] * 100
    winners["sram_pct"] = winners["energy_sram_pj"] / winners["energy_total_pj"] * 100
    winners["dram_pct"] = winners["energy_dram_pj"] / winners["energy_total_pj"] * 100
    return winners


def _generate_selected_design_charts(summary_path: Path, figures_path: Path) -> list[Path]:
    generated: list[Path] = []
    winners = _selected_1080p_winners(summary_path)
    if winners.empty:
        return generated

    labels = [f"{int(value)}x{int(value)}" for value in winners["gaussian_kernel"]]
    component_path = figures_path / "component_energy_split.png"
    _plot_stacked_percent_bars(
        labels,
        [
            ("MAC", [float(v) for v in winners["mac_pct"]], "#59A14F"),
            ("SRAM dynamic", [float(v) for v in winners["sram_pct"]], "#4E79A7"),
            ("DRAM dynamic", [float(v) for v in winners["dram_pct"]], "#F28E2B"),
        ],
        "Dynamic component energy split",
        component_path,
    )
    generated.append(component_path)

    bottleneck_path = summary_path / "bottleneck_summary.csv"
    if not bottleneck_path.exists():
        return generated
    bottleneck = pd.read_csv(bottleneck_path)
    if bottleneck.empty:
        return generated

    selected = bottleneck.merge(
        winners[
            [
                "resolution",
                "tile_width",
                "tile_height",
                "gaussian_kernel",
                "array_size",
                "sram_budget_kb",
                "bandwidth_gbps",
                "dataflow",
            ]
        ],
        on=[
            "resolution",
            "tile_width",
            "tile_height",
            "gaussian_kernel",
            "array_size",
            "sram_budget_kb",
            "bandwidth_gbps",
            "dataflow",
        ],
        how="inner",
    )
    if selected.empty:
        return generated

    stage = (
        selected.pivot_table(
            index="gaussian_kernel",
            columns="stage_op",
            values="energy_share_pct",
            aggfunc="first",
        )
        .reindex(winners["gaussian_kernel"])
        .fillna(0)
    )
    stage_path = figures_path / "stage_share_by_kernel.png"
    _plot_stacked_percent_bars(
        labels,
        [
            ("Gaussian", [float(v) for v in stage.get("gaussian", pd.Series([0] * len(stage))).tolist()], "#4E79A7"),
            ("Sobel", [float(v) for v in stage.get("sobel", pd.Series([0] * len(stage))).tolist()], "#F28E2B"),
        ],
        "Stage energy share by Gaussian kernel",
        stage_path,
    )
    generated.append(stage_path)
    return generated


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

    deadline_ms = 33.0
    dataflow_colors = {"ws": "#4C78A8", "os": "#F58518", "is": "#54A24B"}
    dataflow_labels = {
        "ws": "Weight-stationary",
        "os": "Output-stationary",
        "is": "Input-stationary",
    }
    resolution_markers = {"720p": "o", "1080p": "s", "hires": "^"}
    observed_dataflows = set(pipeline["dataflow"])
    observed_resolutions = set(pipeline["resolution"])

    winner_path = summary_path / "minimum_energy_designs.csv"
    winners = pd.DataFrame()
    if winner_path.exists():
        winners = pd.read_csv(winner_path)
        if "deadline_ms" in winners.columns:
            winners = winners[winners["deadline_ms"].round(6) == deadline_ms]
        winners = winners.drop_duplicates(
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

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for ax in axes:
        for (dataflow, resolution), group in pipeline.groupby(["dataflow", "resolution"]):
            ax.scatter(
                group["latency_ms"],
                group["energy_total_mj"],
                color=dataflow_colors.get(dataflow, "0.45"),
                marker=resolution_markers.get(resolution, "o"),
                s=20,
                alpha=0.45,
                linewidths=0,
                rasterized=True,
            )
        ax.axvspan(0, deadline_ms, color="#54A24B", alpha=0.07)
        ax.axvline(deadline_ms, color="#D62728", linestyle="--", linewidth=1.6)
        if not winners.empty:
            ax.scatter(
                winners["latency_ms"],
                winners["energy_total_mj"],
                color="black",
                edgecolors="white",
                linewidths=0.6,
                marker="*",
                s=140,
                zorder=5,
            )
        ax.set_xlabel("Latency per frame at 1 GHz (ms)")
        ax.grid(True, alpha=0.3)

    axes[0].set_title("Full sweep")
    axes[0].set_xlim(left=0)
    axes[0].set_ylabel("Energy per frame (mJ)")
    axes[1].set_title("0-40 ms deadline zoom")
    axes[1].set_xlim(0, 40)
    axes[1].text(
        0.03,
        0.96,
        "green region = <=33 ms (30 FPS)",
        transform=axes[1].transAxes,
        ha="left",
        va="top",
        fontsize=8,
        color="#8C1D18",
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8, "pad": 2},
    )
    if not winners.empty:
        label_offsets = {3: (6, -12), 5: (6, 6), 7: (6, 6), 11: (6, 6)}
        for _, row in winners[winners["resolution"].eq("1080p")].iterrows():
            kernel = int(row["gaussian_kernel"])
            axes[1].annotate(
                f"k={kernel} {str(row['dataflow']).upper()}",
                (row["latency_ms"], row["energy_total_mj"]),
                xytext=label_offsets.get(kernel, (6, 6)),
                textcoords="offset points",
                fontsize=7,
                arrowprops={"arrowstyle": "-", "lw": 0.5, "color": "0.25"},
            )

    legend_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=color,
            markeredgecolor="none",
            label=label,
            markersize=7,
        )
        for key, label in dataflow_labels.items()
        if key in observed_dataflows
        for color in [dataflow_colors[key]]
    ]
    legend_handles.extend(
        Line2D(
            [0],
            [0],
            marker=marker,
            color="0.35",
            linestyle="none",
            label=resolution,
            markersize=7,
        )
        for resolution, marker in resolution_markers.items()
        if resolution in observed_resolutions
    )
    legend_handles.append(Line2D([0], [0], color="#D62728", linestyle="--", label="33 ms deadline"))
    if not winners.empty:
        legend_handles.append(
            Line2D(
                [0],
                [0],
                marker="*",
                color="black",
                linestyle="none",
                label="Min-energy feasible",
                markersize=10,
            )
        )
    axes[0].legend(handles=legend_handles, fontsize=7, loc="upper right", frameon=True)
    fig.suptitle("Energy-delay design space")
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

    generated.extend(_generate_selected_design_charts(summary_path, figures_path))
    return generated
