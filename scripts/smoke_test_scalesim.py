#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

from _bootstrap import add_project_src_to_path

ROOT = add_project_src_to_path()

from hpc_final.config import load_experiment_config
from hpc_final.parser import parse_reports, reports_exist
from hpc_final.runner import iter_run_specs, report_dir_for_run, run_scalesim_spec


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one tiny SCALE-Sim validation case.")
    parser.add_argument("--config", default=str(ROOT / "configs" / "experiment.yaml"))
    parser.add_argument("--keep", action="store_true", help="Keep smoke output under outputs/smoke.")
    args = parser.parse_args()

    config = load_experiment_config(args.config)
    spec = next(iter(iter_run_specs(config, "sanity")))

    if args.keep:
        raw_dir = ROOT / "outputs" / "smoke"
        shutil.rmtree(raw_dir, ignore_errors=True)
        raw_dir.mkdir(parents=True, exist_ok=True)
        run_dir = run_scalesim_spec(spec, config, raw_dir, force=True)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = run_scalesim_spec(spec, config, Path(tmp), force=True)
            import json
            run_name = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))["run_name"]
            report_dir = report_dir_for_run(run_dir, run_name)
            if not reports_exist(report_dir):
                raise RuntimeError(f"Missing reports in {report_dir}")
            records = parse_reports(report_dir, ["gaussian_k3", "sobel_3x3"])
            print(f"Smoke test passed: parsed {len(records)} SCALE-Sim stage records")
            return 0

    import json
    run_name = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))["run_name"]
    report_dir = report_dir_for_run(run_dir, run_name)
    if not reports_exist(report_dir):
        raise RuntimeError(f"Missing reports in {report_dir}")
    records = parse_reports(report_dir, ["gaussian_k3", "sobel_3x3"])
    print(f"Smoke test passed: parsed {len(records)} SCALE-Sim stage records at {report_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
