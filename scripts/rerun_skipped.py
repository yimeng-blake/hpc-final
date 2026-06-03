#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from dataclasses import fields
from pathlib import Path

from _bootstrap import add_project_src_to_path

ROOT = add_project_src_to_path()

from hpc_final.config import load_experiment_config
from hpc_final.parser import reports_exist
from hpc_final.runner import RunSpec, report_dir_for_run, run_scalesim_spec


RUN_SPEC_FIELDS = {field.name for field in fields(RunSpec)}


def _metadata_for_run(run_dir: Path) -> dict:
    skipped_path = run_dir / "SKIPPED.json"
    if skipped_path.exists():
        return json.loads(skipped_path.read_text(encoding="utf-8"))["metadata"]
    return json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))


def _spec_for_run(run_dir: Path) -> RunSpec:
    metadata = _metadata_for_run(run_dir)
    return RunSpec(**{key: metadata[key] for key in RUN_SPEC_FIELDS})


def _report_dir(run_dir: Path) -> Path:
    metadata = _metadata_for_run(run_dir)
    return report_dir_for_run(run_dir, metadata["run_name"])


def _set_memory_limit(memory_gb: float | None) -> None:
    if memory_gb is None or memory_gb <= 0:
        return
    try:
        import resource

        limit = int(memory_gb * 1024**3)
        for name in ("RLIMIT_AS", "RLIMIT_DATA"):
            if hasattr(resource, name):
                resource.setrlimit(getattr(resource, name), (limit, limit))
    except Exception as exc:  # pragma: no cover - platform-dependent defensive path.
        print(f"warning: could not set memory limit: {exc}", file=sys.stderr, flush=True)


def _selected_skipped_dirs(args: argparse.Namespace) -> list[Path]:
    raw_dir = Path(args.raw_dir)
    run_dirs = sorted(path.parent for path in raw_dir.glob("run_*/SKIPPED.json"))
    selected: list[Path] = []
    for run_dir in run_dirs:
        metadata = _metadata_for_run(run_dir)
        if args.dataflow and metadata["dataflow"] != args.dataflow:
            continue
        if args.kernel and int(metadata["gaussian_kernel"]) not in args.kernel:
            continue
        if args.array_size and int(metadata["array_size"]) not in args.array_size:
            continue
        if args.tile_class and metadata["tile_class"] != args.tile_class:
            continue
        if args.reason_contains:
            reason = json.loads((run_dir / "SKIPPED.json").read_text(encoding="utf-8"))["reason"]
            if args.reason_contains not in reason:
                continue
        selected.append(run_dir)
    if args.max_cases is not None:
        selected = selected[: args.max_cases]
    return selected


def _child_main(args: argparse.Namespace) -> int:
    _set_memory_limit(args.memory_gb)
    config = load_experiment_config(args.config)
    run_dir = Path(args.child_run_dir)
    spec = _spec_for_run(run_dir)

    if reports_exist(_report_dir(run_dir)):
        (run_dir / "SKIPPED.json").unlink(missing_ok=True)
        print(f"reports already exist for {run_dir.name}; removed SKIPPED.json", flush=True)
        return 0

    try:
        result = run_scalesim_spec(
            spec,
            config,
            args.raw_dir,
            force=True,
            ignore_resource_guard=True,
        )
    except Exception as exc:
        print(f"{run_dir.name} failed: {exc}", file=sys.stderr, flush=True)
        return 2

    if not reports_exist(_report_dir(result)):
        print(f"{run_dir.name} finished without complete SCALE-Sim reports", file=sys.stderr, flush=True)
        return 3
    print(f"completed {run_dir.name}", flush=True)
    return 0


def _write_log(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "run_name",
        "status",
        "seconds",
        "resolution",
        "gaussian_kernel",
        "array_size",
        "sram_budget_kb",
        "bandwidth_gbps",
        "dataflow",
        "tile_class",
        "stdout_tail",
        "stderr_tail",
        "max_rss_gb",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _tail(text: str, limit: int = 1000) -> str:
    text = text.strip()
    clipped = text[-limit:] if len(text) > limit else text
    return clipped.replace("\n", "\\n")


def _rss_bytes(pid: int) -> int:
    result = subprocess.run(
        ["ps", "-o", "rss=", "-p", str(pid)],
        check=False,
        text=True,
        capture_output=True,
    )
    text = result.stdout.strip()
    if not text:
        return 0
    return int(text.splitlines()[0].strip()) * 1024


def _run_child_process(cmd: list[str], timeout_sec: float, max_rss_gb: float | None) -> tuple[str, float, str, str, float]:
    start = time.monotonic()
    process = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    max_rss = 0
    max_rss_bytes = int(max_rss_gb * 1024**3) if max_rss_gb and max_rss_gb > 0 else None
    status: str | None = None

    while True:
        returncode = process.poll()
        rss = _rss_bytes(process.pid)
        max_rss = max(max_rss, rss)
        elapsed = time.monotonic() - start
        if returncode is not None:
            status = "completed" if returncode == 0 else f"failed:{returncode}"
            break
        if max_rss_bytes is not None and rss > max_rss_bytes:
            process.kill()
            status = "rss_limit"
            break
        if elapsed > timeout_sec:
            process.kill()
            status = "timeout"
            break
        time.sleep(1)

    stdout, stderr = process.communicate()
    seconds = time.monotonic() - start
    return status, seconds, stdout, stderr, max_rss / 1024**3


def _parent_main(args: argparse.Namespace) -> int:
    run_dirs = _selected_skipped_dirs(args)
    print(f"Selected {len(run_dirs)} skipped raw runs.", flush=True)
    if args.dry_run:
        for run_dir in run_dirs:
            metadata = _metadata_for_run(run_dir)
            print(
                f"{run_dir.name} {metadata['resolution']} k={metadata['gaussian_kernel']} "
                f"{metadata['array_size']}x{metadata['array_size']} {metadata['bandwidth_gbps']:g}GB/s "
                f"{metadata['dataflow']} tile={metadata['tile_class']}",
                flush=True,
            )
        return 0

    rows: list[dict] = []
    completed = failed = timed_out = rss_limited = 0
    for idx, run_dir in enumerate(run_dirs, 1):
        metadata = _metadata_for_run(run_dir)
        label = (
            f"[{idx}/{len(run_dirs)}] {run_dir.name} {metadata['resolution']} "
            f"k={metadata['gaussian_kernel']} {metadata['array_size']}x{metadata['array_size']} "
            f"{metadata['bandwidth_gbps']:g}GB/s {metadata['dataflow']} tile={metadata['tile_class']}"
        )
        print(label, flush=True)
        cmd = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--child-run-dir",
            str(run_dir),
            "--config",
            args.config,
            "--raw-dir",
            args.raw_dir,
        ]
        if args.memory_gb is not None:
            cmd.extend(["--memory-gb", str(args.memory_gb)])

        status, seconds, stdout, stderr, max_rss_gb = _run_child_process(cmd, args.timeout_sec, args.max_rss_gb)
        if status == "completed":
            completed += 1
        elif status == "timeout":
            timed_out += 1
        elif status == "rss_limit":
            rss_limited += 1
        else:
            failed += 1

        rows.append(
            {
                "run_name": run_dir.name,
                "status": status,
                "seconds": f"{seconds:.3f}",
                "resolution": metadata["resolution"],
                "gaussian_kernel": metadata["gaussian_kernel"],
                "array_size": metadata["array_size"],
                "sram_budget_kb": metadata["sram_budget_kb"],
                "bandwidth_gbps": metadata["bandwidth_gbps"],
                "dataflow": metadata["dataflow"],
                "tile_class": metadata["tile_class"],
                "stdout_tail": _tail(stdout),
                "stderr_tail": _tail(stderr),
                "max_rss_gb": f"{max_rss_gb:.3f}",
            }
        )
        _write_log(Path(args.log), rows)
        print(f"  -> {status} in {seconds:.1f}s", flush=True)
        if status != "completed" and not args.keep_going:
            break

    print(
        f"Finished skipped rerun: completed={completed}, failed={failed}, timeout={timed_out}, "
        f"rss_limit={rss_limited}, "
        f"log={args.log}",
        flush=True,
    )
    return 0 if failed == 0 and timed_out == 0 and rss_limited == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Rerun only raw runs that are currently marked SKIPPED.")
    parser.add_argument("--config", default=str(ROOT / "configs" / "experiment.yaml"))
    parser.add_argument("--raw-dir", default=str(ROOT / "outputs" / "raw"))
    parser.add_argument("--log", default=str(ROOT / "outputs" / "summary_accelergy_plugin" / "rerun_skipped_log.csv"))
    parser.add_argument("--timeout-sec", type=float, default=180.0)
    parser.add_argument("--memory-gb", type=float, default=0.0)
    parser.add_argument("--max-rss-gb", type=float, default=8.0)
    parser.add_argument("--dataflow", choices=["ws", "os", "is"], default=None)
    parser.add_argument("--kernel", type=int, action="append", default=None)
    parser.add_argument("--array-size", type=int, action="append", default=None)
    parser.add_argument("--tile-class", choices=["full", "right_edge", "bottom_edge", "corner"], default=None)
    parser.add_argument("--reason-contains", default=None)
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keep-going", action="store_true", default=True)
    parser.add_argument("--child-run-dir", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.child_run_dir:
        return _child_main(args)
    return _parent_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
