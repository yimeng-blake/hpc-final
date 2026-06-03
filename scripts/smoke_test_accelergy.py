#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil

from _bootstrap import add_project_src_to_path

ROOT = add_project_src_to_path()

from hpc_final.accelergy_backend import generate_accelergy_plugin_energy_params
from hpc_final.config import load_experiment_config


def smoke_plugin_backend(keep: bool) -> None:
    out_dir = ROOT / "outputs" / "smoke_accelergy_plugin"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    config = load_experiment_config(ROOT / "configs" / "experiment.yaml")
    params = generate_accelergy_plugin_energy_params(
        config,
        out_dir,
        array_size=32,
        sram_budget_kb=1024,
        word_bytes=config["word_bytes"],
    )
    required = [
        "mac_pj",
        "sram_ifmap_read_pj_per_action",
        "sram_filter_read_pj_per_action",
        "sram_ofmap_write_pj_per_action",
        "dram_ifmap_read_pj_per_action",
        "dram_filter_read_pj_per_action",
        "dram_ofmap_write_pj_per_action",
    ]
    for key in required:
        if float(params[key]) <= 0:
            raise RuntimeError(f"Expected positive generated action energy for {key}, got {params[key]}")
    if not keep:
        shutil.rmtree(out_dir, ignore_errors=True)
        print("Accelergy plugin smoke test passed: generated and validated an Accelergy table-plug-in ERT")
    else:
        print(f"Accelergy plugin smoke test passed: generated ERT at {params['accelergy_ert']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Accelergy table-plug-in ERT generation.")
    parser.add_argument("--keep", action="store_true", help="Keep generated smoke output.")
    args = parser.parse_args()
    smoke_plugin_backend(args.keep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
