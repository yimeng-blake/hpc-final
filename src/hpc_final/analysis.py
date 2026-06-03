from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .accelergy_backend import (
    BRANCH_COMPONENT_ACTIONS,
    BRANCH_COMPONENTS,
    generate_accelergy_plugin_energy_params,
    write_accelergy_plugin_backend_summary,
)
from .energy import energy_breakdown_from_component_action_energy_pj
from .parser import parse_reports, reports_exist


GROUP_COLS = [
    "resolution",
    "frame_width",
    "frame_height",
    "tile_width",
    "tile_height",
    "gaussian_kernel",
    "array_size",
    "sram_budget_kb",
    "bandwidth_gbps",
    "dataflow",
]


def _num(value: Any) -> float:
    return float(value)


def _energy_param_resolver(
    config: dict,
    energy_backend: str,
    out_dir: Path,
) -> tuple[Any, dict[tuple[int, int, int], dict[str, float | str]]]:
    if energy_backend != "accelergy_plugin":
        raise ValueError(f"Unsupported energy backend for summary generation: {energy_backend}")

    generated: dict[tuple[int, int, int], dict[str, float | str]] = {}

    def resolve(metadata: dict) -> dict[str, float | str]:
        key = (int(metadata["array_size"]), int(metadata["sram_budget_kb"]), int(metadata["word_bytes"]))
        if key not in generated:
            generated[key] = generate_accelergy_plugin_energy_params(
                config,
                out_dir,
                array_size=key[0],
                sram_budget_kb=key[1],
                word_bytes=key[2],
            )
        return generated[key]

    return resolve, generated


def _stage_records_for_run(
    run_dir: Path,
    config: dict,
    energy_backend: str,
    energy_params_for: Any,
) -> list[dict]:
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.exists():
        return []
    base_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    report_dir = run_dir / "scalesim" / base_metadata["run_name"]
    if not reports_exist(report_dir):
        return []

    parsed = parse_reports(report_dir, base_metadata["stage_names"])
    records: list[dict] = []
    alias_path = run_dir / "aliases.jsonl"
    if alias_path.exists():
        metadata_items = [json.loads(line) for line in alias_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        metadata_items = [base_metadata]

    for metadata in metadata_items:
        energy_params = energy_params_for(metadata)
        stage_meta = {stage["name"]: stage for stage in metadata["stages"]}
        for record in parsed:
            stage = stage_meta[record["stage"]]
            tile_count = metadata["tile_count"]
            cycles = _num(record["compute_total_cycles_incl_prefetch"])
            total_cycles = _num(record["compute_total_cycles"])
            stall_cycles = _num(record["compute_stall_cycles"])

            sram_ifmap_reads = _num(record["detail_sram_ifmap_reads"])
            sram_filter_reads = _num(record["detail_sram_filter_reads"])
            sram_ofmap_writes = _num(record["detail_sram_ofmap_writes"])
            dram_ifmap_reads = _num(record["detail_dram_ifmap_reads"])
            dram_filter_reads = _num(record["detail_dram_filter_reads"])
            dram_ofmap_writes = _num(record["detail_dram_ofmap_writes"])
            sram_accesses = sram_ifmap_reads + sram_filter_reads + sram_ofmap_writes
            dram_accesses = dram_ifmap_reads + dram_filter_reads + dram_ofmap_writes
            scaled_macs = stage["macs"] * tile_count
            scaled_sram = sram_accesses * tile_count
            scaled_dram = dram_accesses * tile_count
            scaled_sram_ifmap_reads = sram_ifmap_reads * tile_count
            scaled_sram_filter_reads = sram_filter_reads * tile_count
            scaled_sram_ofmap_writes = sram_ofmap_writes * tile_count
            scaled_dram_ifmap_reads = dram_ifmap_reads * tile_count
            scaled_dram_filter_reads = dram_filter_reads * tile_count
            scaled_dram_ofmap_writes = dram_ofmap_writes * tile_count
            scaled_cycles = cycles * tile_count
            scaled_stalls = stall_cycles * tile_count

            energy = energy_breakdown_from_component_action_energy_pj(
                macs=scaled_macs,
                sram_ifmap_reads=scaled_sram_ifmap_reads,
                sram_filter_reads=scaled_sram_filter_reads,
                sram_ofmap_writes=scaled_sram_ofmap_writes,
                dram_ifmap_reads=scaled_dram_ifmap_reads,
                dram_filter_reads=scaled_dram_filter_reads,
                dram_ofmap_writes=scaled_dram_ofmap_writes,
                mac_pj_per_action=energy_params["mac_pj"],
                sram_ifmap_read_pj_per_action=energy_params["sram_ifmap_read_pj_per_action"],
                sram_filter_read_pj_per_action=energy_params["sram_filter_read_pj_per_action"],
                sram_ofmap_write_pj_per_action=energy_params["sram_ofmap_write_pj_per_action"],
                dram_ifmap_read_pj_per_action=energy_params["dram_ifmap_read_pj_per_action"],
                dram_filter_read_pj_per_action=energy_params["dram_filter_read_pj_per_action"],
                dram_ofmap_write_pj_per_action=energy_params["dram_ofmap_write_pj_per_action"],
            )

            records.append(
                {
                    **{key: metadata[key] for key in GROUP_COLS},
                    "run_name": metadata["run_name"],
                    "spec_hash": metadata.get("spec_hash", ""),
                    "simulation_hash": metadata.get("simulation_hash", ""),
                    "tile_class": metadata["tile_class"],
                    "tile_out_width": metadata["tile_out_width"],
                    "tile_out_height": metadata["tile_out_height"],
                    "tile_count": tile_count,
                    "stage": record["stage"],
                    "stage_op": stage["op"],
                    "stage_m": stage["m"],
                    "stage_n": stage["n"],
                    "stage_k": stage["k"],
                    "stage_macs_per_tile": stage["macs"],
                    "stage_input_pixels_with_halo": stage["input_pixels_with_halo"],
                    "stage_output_pixels": stage["output_pixels"],
                    "cycles_per_tile": cycles,
                    "compute_cycles_per_tile": total_cycles,
                    "stall_cycles_per_tile": stall_cycles,
                    "scaled_cycles": scaled_cycles,
                    "scaled_stall_cycles": scaled_stalls,
                    "scaled_macs": scaled_macs,
                    "scaled_sram_accesses": scaled_sram,
                    "scaled_sram_ifmap_reads": scaled_sram_ifmap_reads,
                    "scaled_sram_filter_reads": scaled_sram_filter_reads,
                    "scaled_sram_ofmap_writes": scaled_sram_ofmap_writes,
                    "scaled_dram_accesses": scaled_dram,
                    "scaled_dram_ifmap_reads": scaled_dram_ifmap_reads,
                    "scaled_dram_filter_reads": scaled_dram_filter_reads,
                    "scaled_dram_ofmap_writes": scaled_dram_ofmap_writes,
                    "overall_util_pct": _num(record["compute_overall_util_pct"]),
                    "mapping_efficiency_pct": _num(record["compute_mapping_efficiency_pct"]),
                    "compute_util_pct": _num(record["compute_compute_util_pct"]),
                    "analytical_lower_bound_ms": metadata["analytical_lower_bound_ms"],
                    "energy_backend": energy_backend,
                    **energy_params,
                    **energy,
                }
            )
    return records


def load_stage_records(
    raw_dir: str | Path,
    config: dict,
    energy_backend: str = "accelergy_plugin",
    energy_params_for: Any | None = None,
) -> pd.DataFrame:
    raw_path = Path(raw_dir)
    if energy_params_for is None:
        energy_params_for, _ = _energy_param_resolver(config, energy_backend, Path.cwd())
    records: list[dict] = []
    for metadata in sorted(raw_path.glob("run_*/metadata.json")):
        records.extend(_stage_records_for_run(metadata.parent, config, energy_backend, energy_params_for))
    return pd.DataFrame.from_records(records)


def load_skipped_records(raw_dir: str | Path) -> pd.DataFrame:
    records: list[dict] = []
    for skipped_path in Path(raw_dir).glob("run_*/SKIPPED.json"):
        payload = json.loads(skipped_path.read_text(encoding="utf-8"))
        alias_path = skipped_path.parent / "aliases.jsonl"
        if alias_path.exists():
            metadata_items = [json.loads(line) for line in alias_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        else:
            metadata_items = [payload["metadata"]]
        for metadata in metadata_items:
            records.append(
                {
                    **{key: metadata.get(key) for key in GROUP_COLS},
                    "run_name": metadata.get("run_name"),
                    "spec_hash": metadata.get("spec_hash", ""),
                    "simulation_hash": metadata.get("simulation_hash", ""),
                    "tile_class": metadata.get("tile_class"),
                    "reason": payload["reason"],
                }
            )
    return pd.DataFrame.from_records(records)


def filter_stage_records(stage_df: pd.DataFrame, tile_width: int | None, tile_height: int | None) -> pd.DataFrame:
    if stage_df.empty:
        return stage_df
    filtered = stage_df
    if tile_width is not None:
        filtered = filtered[filtered["tile_width"] == tile_width]
    if tile_height is not None:
        filtered = filtered[filtered["tile_height"] == tile_height]
    return filtered.copy()


def drop_incomplete_configs(stage_df: pd.DataFrame, skipped_df: pd.DataFrame) -> pd.DataFrame:
    if stage_df.empty or skipped_df.empty:
        return stage_df

    skipped_keys = skipped_df[GROUP_COLS].drop_duplicates().copy()
    skipped_keys["_incomplete_config"] = True
    merged = stage_df.merge(skipped_keys, on=GROUP_COLS, how="left")
    complete = merged[merged["_incomplete_config"].isna()].drop(columns=["_incomplete_config"])
    return complete.reset_index(drop=True)


def pipeline_summary(stage_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    if stage_df.empty:
        return pd.DataFrame()

    agg = (
        stage_df.groupby(GROUP_COLS, as_index=False)
        .agg(
            total_cycles=("scaled_cycles", "sum"),
            total_stall_cycles=("scaled_stall_cycles", "sum"),
            total_macs=("scaled_macs", "sum"),
            total_sram_accesses=("scaled_sram_accesses", "sum"),
            total_sram_ifmap_reads=("scaled_sram_ifmap_reads", "sum"),
            total_sram_filter_reads=("scaled_sram_filter_reads", "sum"),
            total_sram_ofmap_writes=("scaled_sram_ofmap_writes", "sum"),
            total_dram_accesses=("scaled_dram_accesses", "sum"),
            total_dram_ifmap_reads=("scaled_dram_ifmap_reads", "sum"),
            total_dram_filter_reads=("scaled_dram_filter_reads", "sum"),
            total_dram_ofmap_writes=("scaled_dram_ofmap_writes", "sum"),
            energy_mac_pj=("energy_mac_pj", "sum"),
            energy_sram_ifmap_pj=("energy_sram_ifmap_pj", "sum"),
            energy_sram_filter_pj=("energy_sram_filter_pj", "sum"),
            energy_sram_ofmap_pj=("energy_sram_ofmap_pj", "sum"),
            energy_sram_pj=("energy_sram_pj", "sum"),
            energy_dram_ifmap_pj=("energy_dram_ifmap_pj", "sum"),
            energy_dram_filter_pj=("energy_dram_filter_pj", "sum"),
            energy_dram_ofmap_pj=("energy_dram_ofmap_pj", "sum"),
            energy_dram_pj=("energy_dram_pj", "sum"),
            energy_total_pj=("energy_total_pj", "sum"),
            analytical_lower_bound_ms=("analytical_lower_bound_ms", "first"),
            energy_backend=("energy_backend", "first"),
            energy_model=("energy_model", "first"),
            sram_read_pj_per_byte=("sram_read_pj_per_byte", "first"),
            sram_write_pj_per_byte=("sram_write_pj_per_byte", "first"),
            dram_read_pj_per_byte=("dram_read_pj_per_byte", "first"),
            dram_write_pj_per_byte=("dram_write_pj_per_byte", "first"),
        )
    )
    agg["latency_ms"] = agg["total_cycles"] / config["frequency_hz"] * 1000
    agg["num_pes"] = agg["array_size"] * agg["array_size"]
    agg["cycles_x_pes"] = agg["total_cycles"] * agg["num_pes"]
    agg["stall_pct"] = agg["total_stall_cycles"] / agg["total_cycles"].where(agg["total_cycles"] != 0, 1) * 100
    agg["energy_total_mj"] = agg["energy_total_pj"] / 1_000_000_000
    agg["edp_mj_ms"] = agg["energy_total_mj"] * agg["latency_ms"]
    agg["average_power_w_at_30fps"] = agg["energy_total_pj"] * 30 / 1_000_000_000_000
    return agg


def feasible_designs(pipeline_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows: list[dict] = []
    if pipeline_df.empty:
        return pd.DataFrame()
    for _, row in pipeline_df.iterrows():
        deadlines = config["resolutions"][row["resolution"]]["deadlines_ms"]
        for deadline_ms in deadlines:
            item = row.to_dict()
            item["deadline_ms"] = deadline_ms
            item["feasible"] = bool(row["latency_ms"] <= deadline_ms)
            item["average_power_w_at_deadline_fps"] = row["energy_total_pj"] * (1000 / deadline_ms) / 1_000_000_000_000
            rows.append(item)
    return pd.DataFrame(rows)


def pareto_frontier(feasible_df: pd.DataFrame) -> pd.DataFrame:
    if feasible_df.empty:
        return pd.DataFrame()
    frontiers: list[pd.DataFrame] = []
    for _, group in feasible_df[feasible_df["feasible"]].groupby(["resolution", "tile_width", "tile_height", "gaussian_kernel", "deadline_ms"]):
        sorted_group = group.sort_values(["latency_ms", "energy_total_mj"], ascending=[True, True]).copy()
        best_energy = float("inf")
        keep = []
        for _, row in sorted_group.iterrows():
            is_frontier = row["energy_total_mj"] < best_energy
            keep.append(is_frontier)
            if is_frontier:
                best_energy = row["energy_total_mj"]
        frontier = sorted_group[keep].copy()
        frontiers.append(frontier)
    if not frontiers:
        return pd.DataFrame()
    return pd.concat(frontiers, ignore_index=True)


def minimum_energy_designs(feasible_df: pd.DataFrame) -> pd.DataFrame:
    feasible = feasible_df[feasible_df["feasible"]].copy()
    if feasible.empty:
        return pd.DataFrame()
    idx = feasible.groupby(["resolution", "tile_width", "tile_height", "gaussian_kernel", "deadline_ms"])["energy_total_mj"].idxmin()
    return feasible.loc[idx].sort_values(["resolution", "gaussian_kernel", "deadline_ms"]).reset_index(drop=True)


def bottleneck_summary(stage_df: pd.DataFrame) -> pd.DataFrame:
    if stage_df.empty:
        return pd.DataFrame()
    stage_totals = (
        stage_df.groupby(GROUP_COLS + ["stage_op"], as_index=False)
        .agg(
            stage_cycles=("scaled_cycles", "sum"),
            stage_energy_mj=("energy_total_mj", "sum"),
            energy_backend=("energy_backend", "first"),
        )
    )
    totals = (
        stage_totals.groupby(GROUP_COLS, as_index=False)
        .agg(total_cycles=("stage_cycles", "sum"), total_energy_mj=("stage_energy_mj", "sum"))
    )
    merged = stage_totals.merge(totals, on=GROUP_COLS)
    merged["latency_share_pct"] = merged["stage_cycles"] / merged["total_cycles"] * 100
    merged["energy_share_pct"] = merged["stage_energy_mj"] / merged["total_energy_mj"] * 100
    return merged.sort_values(GROUP_COLS + ["stage_op"]).reset_index(drop=True)


def accelergy_action_counts_table(stage_df: pd.DataFrame, energy_backend: str = "accelergy_plugin") -> pd.DataFrame:
    if stage_df.empty:
        return pd.DataFrame()
    if energy_backend != "accelergy_plugin":
        raise ValueError(f"Unsupported Accelergy action-count backend: {energy_backend}")

    component_specs = [
        (BRANCH_COMPONENTS["mac"], BRANCH_COMPONENT_ACTIONS["mac"], "scaled_macs"),
        (BRANCH_COMPONENTS["sram_ifmap"], BRANCH_COMPONENT_ACTIONS["sram_ifmap"], "scaled_sram_ifmap_reads"),
        (BRANCH_COMPONENTS["sram_filter"], BRANCH_COMPONENT_ACTIONS["sram_filter"], "scaled_sram_filter_reads"),
        (BRANCH_COMPONENTS["sram_ofmap"], BRANCH_COMPONENT_ACTIONS["sram_ofmap"], "scaled_sram_ofmap_writes"),
        (BRANCH_COMPONENTS["dram_ifmap"], BRANCH_COMPONENT_ACTIONS["dram_ifmap"], "scaled_dram_ifmap_reads"),
        (BRANCH_COMPONENTS["dram_filter"], BRANCH_COMPONENT_ACTIONS["dram_filter"], "scaled_dram_filter_reads"),
        (BRANCH_COMPONENTS["dram_ofmap"], BRANCH_COMPONENT_ACTIONS["dram_ofmap"], "scaled_dram_ofmap_writes"),
    ]
    rows: list[dict] = []
    context_cols = GROUP_COLS + ["run_name", "spec_hash", "simulation_hash", "tile_class", "stage", "stage_op"]
    for _, row in stage_df.iterrows():
        base = {col: row[col] for col in context_cols}
        for component, action, count_col in component_specs:
            if "{pe_range}" in component:
                pe_range = f"0..{int(row['array_size']) * int(row['array_size']) - 1}"
                component = component.format(pe_range=pe_range)
            rows.append({**base, "component": component, "action": action, "count": row[count_col]})
    return pd.DataFrame(rows)


def summarize(
    raw_dir: str | Path,
    out_dir: str | Path,
    config: dict,
    tile_width: int | None = None,
    tile_height: int | None = None,
    energy_backend: str = "accelergy_plugin",
) -> dict[str, pd.DataFrame]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    energy_params_for, accelergy_plugin_cache = _energy_param_resolver(config, energy_backend, out_path)
    stage_df = filter_stage_records(
        load_stage_records(raw_dir, config, energy_backend, energy_params_for),
        tile_width,
        tile_height,
    )
    skipped_df = filter_stage_records(load_skipped_records(raw_dir), tile_width, tile_height)
    stage_df = drop_incomplete_configs(stage_df, skipped_df)
    pipe_df = pipeline_summary(stage_df, config)
    feas_df = feasible_designs(pipe_df, config)
    pareto_df = pareto_frontier(feas_df)
    min_df = minimum_energy_designs(feas_df)
    bottleneck_df = bottleneck_summary(stage_df)
    accelergy_counts_df = accelergy_action_counts_table(stage_df, energy_backend)

    outputs = {
        "all_runs": stage_df,
        "pipeline_runs": pipe_df,
        "feasible_designs": feas_df,
        "pareto_frontier": pareto_df,
        "minimum_energy_designs": min_df,
        "bottleneck_summary": bottleneck_df,
        "skipped_runs": skipped_df,
    }
    write_accelergy_plugin_backend_summary(config, out_path, list(accelergy_plugin_cache.values()))
    accelergy_counts_df.to_csv(out_path / "accelergy_action_counts.csv", index=False)
    for name, df in outputs.items():
        df.to_csv(out_path / f"{name}.csv", index=False)
    return outputs
