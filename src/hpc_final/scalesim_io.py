from __future__ import annotations

from pathlib import Path

from .workloads import StageSpec


def bandwidth_words_per_cycle(bandwidth_gbps: float, frequency_hz: float, word_bytes: int) -> int:
    """Convert decimal GB/s to SCALE-Sim words/cycle."""
    if bandwidth_gbps <= 0 or frequency_hz <= 0 or word_bytes <= 0:
        raise ValueError("bandwidth, frequency, and word size must be positive")
    words = bandwidth_gbps * 1_000_000_000 / frequency_hz / word_bytes
    return max(1, int(round(words)))


def split_sram_budget(total_kb: int, ifmap_frac: float, filter_frac: float, ofmap_frac: float) -> tuple[int, int, int]:
    if total_kb <= 0:
        raise ValueError("total SRAM budget must be positive")
    total_frac = ifmap_frac + filter_frac + ofmap_frac
    if total_frac <= 0:
        raise ValueError("SRAM fractions must sum to a positive value")

    ifmap = max(1, int(round(total_kb * ifmap_frac / total_frac)))
    filt = max(1, int(round(total_kb * filter_frac / total_frac)))
    ofmap = max(1, total_kb - ifmap - filt)
    return ifmap, filt, ofmap


def write_topology(path: Path, stages: list[StageSpec]) -> None:
    lines = ["Layer,M,N,K,"]
    lines.extend(f"{stage.name},{stage.m},{stage.n},{stage.k}," for stage in stages)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_layout(path: Path, stages: list[StageSpec]) -> None:
    # Custom layouts are disabled in the config, but SCALE-Sim still opens this file.
    lines = ["Layer,"]
    lines.extend(f"{stage.name}," for stage in stages)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_config(
    path: Path,
    *,
    run_name: str,
    array_size: int,
    sram_budget_kb: int,
    bandwidth_words: int,
    dataflow: str,
    scalesim_config: dict,
) -> None:
    ifmap_kb, filter_kb, ofmap_kb = split_sram_budget(
        sram_budget_kb,
        scalesim_config["ifmap_sram_fraction"],
        scalesim_config["filter_sram_fraction"],
        scalesim_config["ofmap_sram_fraction"],
    )
    text = f"""[general]
run_name = {run_name}

[architecture_presets]
ArrayHeight: {array_size}
ArrayWidth: {array_size}
IfmapSramSzkB: {ifmap_kb}
FilterSramSzkB: {filter_kb}
OfmapSramSzkB: {ofmap_kb}
IfmapOffset: 0
FilterOffset: 10000000
OfmapOffset: 20000000
Bandwidth: {bandwidth_words}
Dataflow: {dataflow}
MemoryBanks: 1
ReadRequestBuffer: {scalesim_config["read_request_buffer"]}
WriteRequestBuffer: {scalesim_config["write_request_buffer"]}

[layout]
IfmapCustomLayout: False
IfmapSRAMBankBandwidth: {bandwidth_words}
IfmapSRAMBankNum: 1
IfmapSRAMBankPort: 2
FilterCustomLayout: False
FilterSRAMBankBandwidth: {bandwidth_words}
FilterSRAMBankNum: 1
FilterSRAMBankPort: 2

[sparsity]
SparsitySupport: false
SparseRep: ellpack_block
OptimizedMapping: false
BlockSize: 8
RandomNumberGeneratorSeed: 40

[run_presets]
InterfaceBandwidth: USER
UseRamulatorTrace: False
"""
    path.write_text(text, encoding="utf-8")
