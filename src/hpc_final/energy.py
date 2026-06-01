from __future__ import annotations

from .accelergy_backend import accelergy_energy_breakdown_pj


def energy_breakdown_pj(
    *,
    macs: float,
    sram_accesses: float,
    dram_accesses: float,
    word_bytes: int,
    mac_pj: float,
    sram_pj_per_byte: float,
    dram_pj_per_byte: float,
    backend: str = "analytical",
) -> dict[str, float]:
    if backend == "accelergy":
        return accelergy_energy_breakdown_pj(
            macs=macs,
            sram_ifmap_reads=sram_accesses,
            sram_filter_reads=0,
            sram_ofmap_writes=0,
            dram_ifmap_reads=dram_accesses,
            dram_filter_reads=0,
            dram_ofmap_writes=0,
            word_bytes=word_bytes,
            mac_pj=mac_pj,
            sram_pj_per_byte=sram_pj_per_byte,
            dram_pj_per_byte=dram_pj_per_byte,
        )
    if backend != "analytical":
        raise ValueError(f"Unknown energy backend: {backend}")

    energy_mac_pj = macs * mac_pj
    energy_sram_pj = sram_accesses * word_bytes * sram_pj_per_byte
    energy_dram_pj = dram_accesses * word_bytes * dram_pj_per_byte
    total = energy_mac_pj + energy_sram_pj + energy_dram_pj
    return {
        "energy_mac_pj": energy_mac_pj,
        "energy_sram_pj": energy_sram_pj,
        "energy_dram_pj": energy_dram_pj,
        "energy_total_pj": total,
        "energy_total_mj": total / 1_000_000_000,
    }


def energy_breakdown_from_access_counts_pj(
    *,
    macs: float,
    sram_ifmap_reads: float,
    sram_filter_reads: float,
    sram_ofmap_writes: float,
    dram_ifmap_reads: float,
    dram_filter_reads: float,
    dram_ofmap_writes: float,
    word_bytes: int,
    mac_pj: float,
    sram_pj_per_byte: float,
    dram_pj_per_byte: float,
    backend: str = "analytical",
) -> dict[str, float]:
    if backend == "accelergy":
        return accelergy_energy_breakdown_pj(
            macs=macs,
            sram_ifmap_reads=sram_ifmap_reads,
            sram_filter_reads=sram_filter_reads,
            sram_ofmap_writes=sram_ofmap_writes,
            dram_ifmap_reads=dram_ifmap_reads,
            dram_filter_reads=dram_filter_reads,
            dram_ofmap_writes=dram_ofmap_writes,
            word_bytes=word_bytes,
            mac_pj=mac_pj,
            sram_pj_per_byte=sram_pj_per_byte,
            dram_pj_per_byte=dram_pj_per_byte,
        )
    if backend != "analytical":
        raise ValueError(f"Unknown energy backend: {backend}")

    energy_mac_pj = macs * mac_pj
    energy_sram_ifmap_pj = sram_ifmap_reads * word_bytes * sram_pj_per_byte
    energy_sram_filter_pj = sram_filter_reads * word_bytes * sram_pj_per_byte
    energy_sram_ofmap_pj = sram_ofmap_writes * word_bytes * sram_pj_per_byte
    energy_dram_ifmap_pj = dram_ifmap_reads * word_bytes * dram_pj_per_byte
    energy_dram_filter_pj = dram_filter_reads * word_bytes * dram_pj_per_byte
    energy_dram_ofmap_pj = dram_ofmap_writes * word_bytes * dram_pj_per_byte
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
