from __future__ import annotations

import hashlib
import fcntl
import json
import os
import shutil
from dataclasses import asdict, dataclass
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import product
from pathlib import Path
from typing import Iterable

from scalesim.scale_sim import scalesim

from .config import selected_sweep_values
from .parser import reports_exist
from .scalesim_io import bandwidth_words_per_cycle, write_config, write_layout, write_topology
from .tiling import TileClass, derive_tile_classes
from .workloads import frame_macs, pipeline_stages


@dataclass(frozen=True)
class RunSpec:
    resolution: str
    frame_width: int
    frame_height: int
    tile_width: int
    tile_height: int
    tile_class: str
    tile_out_width: int
    tile_out_height: int
    tile_count: int
    gaussian_kernel: int
    array_size: int
    sram_budget_kb: int
    bandwidth_gbps: float
    bandwidth_words_per_cycle: int
    dataflow: str
    frequency_hz: int
    word_bytes: int

    @property
    def tile(self) -> TileClass:
        return TileClass(self.tile_class, self.tile_out_width, self.tile_out_height, self.tile_count)


def spec_hash(spec: RunSpec) -> str:
    payload = json.dumps(asdict(spec), sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def simulation_key(spec: RunSpec) -> dict:
    """Key fields that affect the SCALE-Sim tile result."""
    return {
        "tile_out_width": spec.tile_out_width,
        "tile_out_height": spec.tile_out_height,
        "gaussian_kernel": spec.gaussian_kernel,
        "array_size": spec.array_size,
        "sram_budget_kb": spec.sram_budget_kb,
        "bandwidth_gbps": spec.bandwidth_gbps,
        "bandwidth_words_per_cycle": spec.bandwidth_words_per_cycle,
        "dataflow": spec.dataflow,
        "frequency_hz": spec.frequency_hz,
        "word_bytes": spec.word_bytes,
    }


def simulation_hash(spec: RunSpec) -> str:
    payload = json.dumps(simulation_key(spec), sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def _metadata_for_spec(spec: RunSpec, run_name: str, stages: list) -> dict:
    metadata = asdict(spec)
    metadata.update(
        {
            "run_name": run_name,
            "spec_hash": spec_hash(spec),
            "simulation_hash": simulation_hash(spec),
            "simulation_key": simulation_key(spec),
            "stage_names": [stage.name for stage in stages],
            "stages": [asdict(stage) for stage in stages],
            "analytical_lower_bound_ms": analytical_lower_bound_ms(spec),
        }
    )
    return metadata


def _same_simulation(metadata: dict, spec: RunSpec) -> bool:
    if "simulation_key" in metadata:
        return metadata["simulation_key"] == simulation_key(spec)
    keys = simulation_key(spec)
    return all(metadata.get(key) == value for key, value in keys.items())


def _alias_path(run_dir: Path) -> Path:
    return run_dir / "aliases.jsonl"


def _same_alias(left: dict, right: dict) -> bool:
    if left.get("spec_hash") and right.get("spec_hash"):
        return left["spec_hash"] == right["spec_hash"]
    fields = [
        "resolution",
        "frame_width",
        "frame_height",
        "tile_width",
        "tile_height",
        "tile_class",
        "tile_out_width",
        "tile_out_height",
        "tile_count",
        "gaussian_kernel",
        "array_size",
        "sram_budget_kb",
        "bandwidth_gbps",
        "bandwidth_words_per_cycle",
        "dataflow",
        "frequency_hz",
        "word_bytes",
    ]
    return all(left.get(field) == right.get(field) for field in fields)


def _append_alias(run_dir: Path, alias: dict) -> None:
    lock_path = run_dir / "aliases.lock"
    alias_path = _alias_path(run_dir)
    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle, fcntl.LOCK_EX)
        existing_aliases: list[dict] = []
        if alias_path.exists():
            with alias_path.open("r", encoding="utf-8") as handle:
                existing_aliases = [json.loads(line) for line in handle if line.strip()]
        elif (run_dir / "metadata.json").exists():
            existing_aliases = [json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))]

        if not any(_same_alias(item, alias) for item in existing_aliases):
            existing_aliases.append(alias)

        tmp_path = run_dir / "aliases.jsonl.tmp"
        with tmp_path.open("w", encoding="utf-8") as handle:
            for item in existing_aliases:
                handle.write(json.dumps(item, sort_keys=True) + "\n")
        tmp_path.replace(alias_path)
        fcntl.flock(lock_handle, fcntl.LOCK_UN)


def _find_existing_simulation(raw_path: Path, spec: RunSpec) -> Path | None:
    canonical = raw_path / f"run_{simulation_hash(spec)}"
    if canonical.exists():
        metadata_path = canonical / "metadata.json"
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if _same_simulation(metadata, spec) and (
                reports_exist(report_dir_for_run(canonical, metadata["run_name"]))
                or (canonical / "SKIPPED.json").exists()
            ):
                return canonical

    for metadata_path in raw_path.glob("run_*/metadata.json"):
        run_dir = metadata_path.parent
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if _same_simulation(metadata, spec) and (
            reports_exist(report_dir_for_run(run_dir, metadata["run_name"]))
            or (run_dir / "SKIPPED.json").exists()
        ):
            return run_dir
    return None


def skip_reason(spec: RunSpec) -> str | None:
    """Return a reason to analytically skip known pathological SCALE-Sim shapes."""
    if (
        spec.dataflow == "os"
        and spec.array_size >= 128
        and spec.gaussian_kernel >= 11
        and spec.tile_out_width >= 128
        and spec.tile_out_height >= 128
    ):
        return (
            "SCALE-Sim output-stationary demand generation is pathological for "
            "11x11 Gaussian full 128x128 tiles on 128x128 arrays; this case is "
            "severely underutilized and excluded from simulator execution."
        )
    if (
        spec.dataflow == "is"
        and spec.tile_out_width >= 128
        and (spec.gaussian_kernel >= 11 or (spec.gaussian_kernel >= 7 and spec.array_size >= 32))
    ):
        return (
            "SCALE-Sim input-stationary demand generation is pathological for "
            "large-kernel 128-wide tiles in this GEMM-lowered workload; "
            "the demand matrices grow excessively and this case is excluded from simulator execution."
        )
    return None


def iter_run_specs(config: dict, mode: str) -> Iterable[RunSpec]:
    values = selected_sweep_values(config, mode)
    tile_width = int(values["tile_size"]["width"])
    tile_height = int(values["tile_size"]["height"])

    for resolution_name in values["resolutions"]:
        resolution = config["resolutions"][resolution_name]
        frame_width = int(resolution["width"])
        frame_height = int(resolution["height"])
        tile_classes = derive_tile_classes(frame_width, frame_height, tile_width, tile_height)
        for gaussian_kernel, array_size, sram_budget_kb, bandwidth_gbps, dataflow in product(
            values["gaussian_kernels"],
            values["array_sizes"],
            values["sram_budgets_kb"],
            values["bandwidths_gbps"],
            values["dataflows"],
        ):
            bandwidth_words = bandwidth_words_per_cycle(
                bandwidth_gbps,
                config["frequency_hz"],
                config["word_bytes"],
            )
            for tile in tile_classes:
                yield RunSpec(
                    resolution=resolution_name,
                    frame_width=frame_width,
                    frame_height=frame_height,
                    tile_width=tile_width,
                    tile_height=tile_height,
                    tile_class=tile.name,
                    tile_out_width=tile.out_width,
                    tile_out_height=tile.out_height,
                    tile_count=tile.count,
                    gaussian_kernel=int(gaussian_kernel),
                    array_size=int(array_size),
                    sram_budget_kb=int(sram_budget_kb),
                    bandwidth_gbps=float(bandwidth_gbps),
                    bandwidth_words_per_cycle=bandwidth_words,
                    dataflow=str(dataflow),
                    frequency_hz=int(config["frequency_hz"]),
                    word_bytes=int(config["word_bytes"]),
                )


def analytical_lower_bound_ms(spec: RunSpec) -> float:
    macs = frame_macs(spec.frame_width, spec.frame_height, spec.gaussian_kernel)
    compute_seconds = macs / (spec.array_size * spec.array_size * spec.frequency_hz)
    frame_bytes = spec.frame_width * spec.frame_height * spec.word_bytes
    memory_seconds = frame_bytes / (spec.bandwidth_gbps * 1_000_000_000)
    return max(compute_seconds, memory_seconds) * 1000


def filter_specs_by_lower_bound(specs: Iterable[RunSpec], config: dict) -> tuple[list[RunSpec], list[RunSpec]]:
    runnable: list[RunSpec] = []
    skipped: list[RunSpec] = []
    for spec in specs:
        deadlines = config["resolutions"][spec.resolution]["deadlines_ms"]
        if analytical_lower_bound_ms(spec) <= max(deadlines):
            runnable.append(spec)
        else:
            skipped.append(spec)
    return runnable, skipped


def report_dir_for_run(run_dir: Path, run_name: str) -> Path:
    return run_dir / "scalesim" / run_name


def run_scalesim_spec(
    spec: RunSpec,
    config: dict,
    raw_dir: str | Path,
    force: bool = False,
    ignore_resource_guard: bool = False,
) -> Path:
    raw_path = Path(raw_dir)
    raw_path.mkdir(parents=True, exist_ok=True)
    stages = pipeline_stages(spec.tile, spec.gaussian_kernel)

    if not force:
        existing = _find_existing_simulation(raw_path, spec)
        if existing is not None:
            existing_metadata = json.loads((existing / "metadata.json").read_text(encoding="utf-8"))
            alias = _metadata_for_spec(spec, existing_metadata["run_name"], stages)
            _append_alias(existing, alias)
            return existing

    run_name = f"run_{simulation_hash(spec)}"
    run_dir = raw_path / run_name
    report_dir = report_dir_for_run(run_dir, run_name)

    if reports_exist(report_dir) and not force:
        alias = _metadata_for_spec(spec, run_name, stages)
        _append_alias(run_dir, alias)
        return run_dir

    if (run_dir / "SKIPPED.json").exists() and not force:
        alias = _metadata_for_spec(spec, run_name, stages)
        _append_alias(run_dir, alias)
        return run_dir

    run_dir.mkdir(parents=True, exist_ok=True)

    metadata = _metadata_for_spec(spec, run_name, stages)
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    _append_alias(run_dir, metadata)

    reason = None if ignore_resource_guard else skip_reason(spec)
    if reason is not None:
        (run_dir / "SKIPPED.json").write_text(
            json.dumps({"reason": reason, "metadata": metadata}, indent=2),
            encoding="utf-8",
        )
        return run_dir

    if force and (run_dir / "scalesim").exists():
        shutil.rmtree(run_dir / "scalesim")

    topology_path = run_dir / "topology.csv"
    layout_path = run_dir / "layout.csv"
    config_path = run_dir / "scale.cfg"
    write_topology(topology_path, stages)
    write_layout(layout_path, stages)
    write_config(
        config_path,
        run_name=run_name,
        array_size=spec.array_size,
        sram_budget_kb=spec.sram_budget_kb,
        bandwidth_words=spec.bandwidth_words_per_cycle,
        dataflow=spec.dataflow,
        scalesim_config=config["scalesim"],
    )

    simulator = scalesim(
        save_disk_space=True,
        verbose=False,
        config=str(config_path),
        topology=str(topology_path),
        layout=str(layout_path),
        input_type_gemm=True,
    )
    simulator.run_scale(top_path=str(run_dir / "scalesim"))

    if not reports_exist(report_dir):
        raise RuntimeError(f"SCALE-Sim completed without expected reports in {report_dir}")
    (run_dir / "SKIPPED.json").unlink(missing_ok=True)
    return run_dir


def _run_worker(args: tuple[RunSpec, dict, str, bool]) -> str:
    spec, config, raw_dir, force = args
    return str(run_scalesim_spec(spec, config, raw_dir, force=force))


def run_many(
    config: dict,
    mode: str,
    raw_dir: str | Path,
    force: bool = False,
    limit: int | None = None,
    skip_lower_bound: bool = True,
    workers: int | None = None,
) -> list[Path]:
    specs = list(iter_run_specs(config, mode))
    if skip_lower_bound:
        specs, skipped = filter_specs_by_lower_bound(specs, config)
        if skipped:
            print(f"Skipped {len(skipped)} runs whose analytical lower bound exceeds every deadline.")
    if limit is not None:
        specs = specs[:limit]

    if workers is None:
        workers = min(4, os.cpu_count() or 1)
    workers = max(1, int(workers))

    run_dirs: list[Path] = []
    if workers > 1:
        print(f"Running {len(specs)} specs with {workers} workers.")
        tasks = [(spec, config, str(raw_dir), force) for spec in specs]
        completed = 0
        with ProcessPoolExecutor(max_workers=workers) as executor:
            future_to_spec = {executor.submit(_run_worker, task): task[0] for task in tasks}
            for future in as_completed(future_to_spec):
                spec = future_to_spec[future]
                completed += 1
                run_dir = Path(future.result())
                run_dirs.append(run_dir)
                print(
                    f"[{completed}/{len(specs)}] {run_dir.name} {spec.resolution} "
                    f"k={spec.gaussian_kernel} {spec.array_size}x{spec.array_size} "
                    f"{spec.bandwidth_gbps:g}GB/s {spec.dataflow} tile={spec.tile_class}",
                    flush=True,
                )
        return run_dirs

    for idx, spec in enumerate(specs, 1):
        run_name = f"run_{spec_hash(spec)}"
        print(f"[{idx}/{len(specs)}] {run_name} {spec.resolution} k={spec.gaussian_kernel} "
              f"{spec.array_size}x{spec.array_size} {spec.bandwidth_gbps:g}GB/s "
              f"{spec.dataflow} tile={spec.tile_class}", flush=True)
        run_dirs.append(run_scalesim_spec(spec, config, raw_dir, force=force))
    return run_dirs
