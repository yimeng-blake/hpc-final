#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
import subprocess
from pathlib import Path

from _bootstrap import add_project_src_to_path

ROOT = add_project_src_to_path()

from hpc_final.config import load_experiment_config


ACTIVE_LINE_PATTERNS = {
    "size": re.compile(r"^-size \(bytes\) .*$", re.MULTILINE),
    "block": re.compile(r"^-block size \(bytes\) .*$", re.MULTILINE),
    "assoc": re.compile(r"^-associativity .*$", re.MULTILINE),
    "ports": re.compile(r"^-read-write port .*$", re.MULTILINE),
    "read_ports": re.compile(r"^-exclusive read port .*$", re.MULTILINE),
    "write_ports": re.compile(r"^-exclusive write port .*$", re.MULTILINE),
    "banks": re.compile(r"^-UCA bank count .*$", re.MULTILINE),
    "tech": re.compile(r"^-technology \(u\) .*$", re.MULTILINE),
    "bus": re.compile(r"^-output/input bus width .*$", re.MULTILINE),
    "cache_type": re.compile(r"^-cache type .*$", re.MULTILINE),
    "ecc": re.compile(r"^-Add ECC - .*$", re.MULTILINE),
    "print_level": re.compile(r"^-Print level \(DETAILED, CONCISE\) - .*$", re.MULTILINE),
    "print_input": re.compile(r"^-Print input parameters - .*$", re.MULTILINE),
}

OUTPUT_PATTERNS = {
    "access_time_ns": re.compile(r"Access time \(ns\):\s*([0-9.eE+-]+)"),
    "cycle_time_ns": re.compile(r"Cycle time \(ns\):\s*([0-9.eE+-]+)"),
    "read_nj_per_access": re.compile(r"Total dynamic read energy per access \(nJ\):\s*([0-9.eE+-]+)"),
    "write_nj_per_access": re.compile(r"Total dynamic write energy per access \(nJ\):\s*([0-9.eE+-]+)"),
    "leakage_mw": re.compile(r"Total leakage power of a bank \(mW\):\s*([0-9.eE+-]+)"),
    "gate_leakage_mw": re.compile(r"Total gate leakage power of a bank \(mW\):\s*([0-9.eE+-]+)"),
    "height_width_mm": re.compile(r"Cache height x width \(mm\):\s*([0-9.eE+-]+)\s*x\s*([0-9.eE+-]+)"),
}


def replace_active_line(template: str, key: str, value: str) -> str:
    pattern = ACTIVE_LINE_PATTERNS[key]
    if not pattern.search(template):
        raise ValueError(f"Could not find active CACTI config line for {key}")
    return pattern.sub(value, template, count=1)


def make_sram_cfg(template: str, *, capacity_bytes: int, access_bytes: int, technology_um: float) -> str:
    cfg = template
    replacements = {
        "size": f"-size (bytes) {capacity_bytes}",
        "block": f"-block size (bytes) {access_bytes}",
        "assoc": "-associativity 1",
        "ports": "-read-write port 1",
        "read_ports": "-exclusive read port 0",
        "write_ports": "-exclusive write port 0",
        "banks": "-UCA bank count 1",
        "tech": f"-technology (u) {technology_um}",
        "bus": f"-output/input bus width {access_bytes * 8}",
        "cache_type": '-cache type "ram"',
        "ecc": '-Add ECC - "false"',
        "print_level": '-Print level (DETAILED, CONCISE) - "CONCISE"',
        "print_input": '-Print input parameters - "false"',
    }
    for key, value in replacements.items():
        cfg = replace_active_line(cfg, key, value)
    return cfg


def parse_cacti_output(text: str) -> dict[str, float]:
    parsed: dict[str, float] = {}
    for key, pattern in OUTPUT_PATTERNS.items():
        match = pattern.search(text)
        if not match:
            raise ValueError(f"Could not parse CACTI output field: {key}")
        if key == "height_width_mm":
            height = float(match.group(1))
            width = float(match.group(2))
            parsed["area_mm2"] = height * width
        else:
            parsed[key] = float(match.group(1))
    return parsed


def run_cacti(cacti_bin: Path, cfg_path: Path) -> str:
    proc = subprocess.run(
        [str(cacti_bin), "-infile", str(cfg_path)],
        check=True,
        text=True,
        capture_output=True,
        cwd=str(cacti_bin.parent),
    )
    return proc.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a CACTI-derived SRAM energy table for the experiment.")
    parser.add_argument("--config", default=str(ROOT / "configs" / "experiment.yaml"))
    parser.add_argument("--cacti-bin", required=True, help="Path to the built CACTI binary.")
    parser.add_argument("--template", default=None, help="CACTI cache.cfg template. Defaults to cache.cfg next to --cacti-bin.")
    parser.add_argument("--out", default=str(ROOT / "configs" / "cacti_sram_45nm.csv"))
    parser.add_argument("--work-dir", default=str(ROOT / "misc" / "cacti"))
    parser.add_argument("--technology-um", type=float, default=0.045)
    parser.add_argument("--access-bytes", type=int, default=4)
    args = parser.parse_args()

    if args.access_bytes <= 0:
        raise ValueError("--access-bytes must be positive")

    config = load_experiment_config(args.config)
    cacti_bin = Path(args.cacti_bin).resolve()
    template_path = Path(args.template).resolve() if args.template else cacti_bin.parent / "cache.cfg"
    out_path = Path(args.out).resolve()
    work_dir = Path(args.work_dir).resolve()
    cfg_dir = work_dir / "configs"
    raw_dir = work_dir / "raw_outputs"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    template = template_path.read_text(encoding="utf-8")
    rows = []
    for sram_budget_kb in config["sram_budgets_kb"]:
        capacity_bytes = int(sram_budget_kb) * 1024
        cfg_text = make_sram_cfg(
            template,
            capacity_bytes=capacity_bytes,
            access_bytes=args.access_bytes,
            technology_um=args.technology_um,
        )
        cfg_path = cfg_dir / f"sram_{sram_budget_kb}kb.cfg"
        raw_path = raw_dir / f"sram_{sram_budget_kb}kb.out"
        cfg_path.write_text(cfg_text, encoding="utf-8")
        output = run_cacti(cacti_bin, cfg_path)
        raw_path.write_text(output, encoding="utf-8")
        sidecar_path = cfg_path.with_name(f"{cfg_path.name}.out")
        if sidecar_path.exists():
            sidecar_path.unlink()
        parsed = parse_cacti_output(output)

        read_pj_per_access = parsed["read_nj_per_access"] * 1000
        write_pj_per_access = parsed["write_nj_per_access"] * 1000
        rows.append(
            {
                "sram_budget_kb": int(sram_budget_kb),
                "capacity_bytes": capacity_bytes,
                "technology_nm": args.technology_um * 1000,
                "access_bytes": args.access_bytes,
                "bus_width_bits": args.access_bytes * 8,
                "cache_type": "ram",
                "read_pj_per_access": read_pj_per_access,
                "write_pj_per_access": write_pj_per_access,
                "read_pj_per_byte": read_pj_per_access / args.access_bytes,
                "write_pj_per_byte": write_pj_per_access / args.access_bytes,
                "access_time_ns": parsed["access_time_ns"],
                "cycle_time_ns": parsed["cycle_time_ns"],
                "leakage_mw": parsed["leakage_mw"],
                "gate_leakage_mw": parsed["gate_leakage_mw"],
                "area_mm2": parsed["area_mm2"],
                "source": "CACTI 7.0.3DD scratch-RAM model",
            }
        )

    fieldnames = list(rows[0].keys())
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote CACTI SRAM table to {out_path}")
    print(f"Wrote CACTI configs and raw outputs to {work_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
