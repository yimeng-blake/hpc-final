#!/usr/bin/env python3
from __future__ import annotations

import argparse

from _bootstrap import add_project_src_to_path

ROOT = add_project_src_to_path()

from hpc_final.config import load_experiment_config
from hpc_final.runner import filter_specs_by_lower_bound, iter_run_specs, run_many


def main() -> int:
    parser = argparse.ArgumentParser(description="Run tiled SCALE-Sim experiment sweep.")
    parser.add_argument("--config", default=str(ROOT / "configs" / "experiment.yaml"))
    parser.add_argument(
        "--mode",
        choices=["sanity", "full", "refinement"],
        default="sanity",
        help="Sweep mode. Use refinement after the broad full pass to add finer candidate points.",
    )
    parser.add_argument("--raw-dir", default=str(ROOT / "outputs" / "raw"))
    parser.add_argument("--force", action="store_true", help="Re-run cached simulations.")
    parser.add_argument("--dry-run", action="store_true", help="Only print the number of runs.")
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N generated specs.")
    parser.add_argument("--no-skip-lower-bound", action="store_true", help="Run configs even if analytical lower bounds miss all deadlines.")
    parser.add_argument("--workers", type=int, default=None, help="Parallel SCALE-Sim workers. Defaults to min(4, CPU cores).")
    args = parser.parse_args()

    config = load_experiment_config(args.config)
    specs = list(iter_run_specs(config, args.mode))
    if not args.no_skip_lower_bound:
        specs, skipped = filter_specs_by_lower_bound(specs, config)
    else:
        skipped = []
    if args.limit is not None:
        specs = specs[: args.limit]
    if args.dry_run:
        print(f"{len(specs)} SCALE-Sim runs would execute for mode={args.mode}")
        if skipped:
            print(f"{len(skipped)} runs would be skipped by analytical lower bounds")
        return 0

    run_many(
        config,
        args.mode,
        args.raw_dir,
        force=args.force,
        limit=args.limit,
        skip_lower_bound=not args.no_skip_lower_bound,
        workers=args.workers,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
