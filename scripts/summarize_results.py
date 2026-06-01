#!/usr/bin/env python3
from __future__ import annotations

import argparse

from _bootstrap import add_project_src_to_path

ROOT = add_project_src_to_path()

from hpc_final.analysis import summarize
from hpc_final.config import load_experiment_config
from hpc_final.plots import generate_plots


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate SCALE-Sim raw outputs and generate plots.")
    parser.add_argument("--config", default=str(ROOT / "configs" / "experiment.yaml"))
    parser.add_argument("--results", default=str(ROOT / "outputs" / "raw"))
    parser.add_argument("--out", default=str(ROOT / "outputs" / "summary"))
    parser.add_argument("--figures", default=str(ROOT / "figures"))
    parser.add_argument("--tile-width", type=int, default=None, help="Only summarize runs with this output tile width.")
    parser.add_argument("--tile-height", type=int, default=None, help="Only summarize runs with this output tile height.")
    parser.add_argument(
        "--energy-backend",
        choices=["analytical", "accelergy"],
        default="analytical",
        help="Energy calculation backend. Accelergy reuses SCALE-Sim action counts through an Accelergy ERT.",
    )
    args = parser.parse_args()

    config = load_experiment_config(args.config)
    outputs = summarize(
        args.results,
        args.out,
        config,
        tile_width=args.tile_width,
        tile_height=args.tile_height,
        energy_backend=args.energy_backend,
    )
    plots = generate_plots(args.out, args.figures)
    print(f"Wrote {len(outputs)} summary CSV files to {args.out}")
    print(f"Wrote {len(plots)} plots to {args.figures}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
