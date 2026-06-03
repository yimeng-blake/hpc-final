from __future__ import annotations


def energy_breakdown_from_component_action_energy_pj(
    *,
    macs: float,
    sram_ifmap_reads: float,
    sram_filter_reads: float,
    sram_ofmap_writes: float,
    dram_ifmap_reads: float,
    dram_filter_reads: float,
    dram_ofmap_writes: float,
    mac_pj_per_action: float,
    sram_ifmap_read_pj_per_action: float,
    sram_filter_read_pj_per_action: float,
    sram_ofmap_write_pj_per_action: float,
    dram_ifmap_read_pj_per_action: float,
    dram_filter_read_pj_per_action: float,
    dram_ofmap_write_pj_per_action: float,
) -> dict[str, float]:
    energy_mac_pj = macs * mac_pj_per_action
    energy_sram_ifmap_pj = sram_ifmap_reads * sram_ifmap_read_pj_per_action
    energy_sram_filter_pj = sram_filter_reads * sram_filter_read_pj_per_action
    energy_sram_ofmap_pj = sram_ofmap_writes * sram_ofmap_write_pj_per_action
    energy_dram_ifmap_pj = dram_ifmap_reads * dram_ifmap_read_pj_per_action
    energy_dram_filter_pj = dram_filter_reads * dram_filter_read_pj_per_action
    energy_dram_ofmap_pj = dram_ofmap_writes * dram_ofmap_write_pj_per_action
    energy_sram_pj = energy_sram_ifmap_pj + energy_sram_filter_pj + energy_sram_ofmap_pj
    energy_dram_pj = energy_dram_ifmap_pj + energy_dram_filter_pj + energy_dram_ofmap_pj
    total = energy_mac_pj + energy_sram_pj + energy_dram_pj
    return {
        "energy_mac_pj": energy_mac_pj,
        "energy_sram_ifmap_pj": energy_sram_ifmap_pj,
        "energy_sram_filter_pj": energy_sram_filter_pj,
        "energy_sram_ofmap_pj": energy_sram_ofmap_pj,
        "energy_sram_pj": energy_sram_pj,
        "energy_dram_ifmap_pj": energy_dram_ifmap_pj,
        "energy_dram_filter_pj": energy_dram_filter_pj,
        "energy_dram_ofmap_pj": energy_dram_ofmap_pj,
        "energy_dram_pj": energy_dram_pj,
        "energy_total_pj": total,
        "energy_total_mj": total / 1_000_000_000,
    }
