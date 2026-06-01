#!/usr/bin/env python3
from __future__ import annotations

from _bootstrap import add_project_src_to_path

add_project_src_to_path()

from hpc_final.energy import energy_breakdown_from_access_counts_pj


def main() -> int:
    result = energy_breakdown_from_access_counts_pj(
        macs=10,
        sram_ifmap_reads=8,
        sram_filter_reads=7,
        sram_ofmap_writes=5,
        dram_ifmap_reads=11,
        dram_filter_reads=13,
        dram_ofmap_writes=6,
        word_bytes=1,
        mac_pj=0.2,
        sram_pj_per_byte=5.0,
        dram_pj_per_byte=100.0,
        backend="accelergy",
    )
    expected = 3102.0
    if abs(result["energy_total_pj"] - expected) > 1e-9:
        raise RuntimeError(f"Expected {expected} pJ, got {result['energy_total_pj']} pJ")
    print("Accelergy smoke test passed: ERT/action-count energy calculation returned 3102.0 pJ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
