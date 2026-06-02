from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any


def _resolve_table_path(config: dict[str, Any], table_path: str) -> Path:
    path = Path(table_path)
    if path.is_absolute():
        return path
    config_dir = Path(config.get("_config_dir", "."))
    return (config_dir / path).resolve()


def _display_table_path(config: dict[str, Any], table_path: str) -> str:
    path = Path(table_path)
    if path.is_absolute():
        return str(path)
    config_dir = Path(config.get("_config_dir", "."))
    resolved = config_dir / path
    try:
        return str(resolved.relative_to(config_dir.parent))
    except ValueError:
        return str(resolved)


@lru_cache(maxsize=8)
def load_cacti_sram_table(path: str) -> dict[int, dict[str, Any]]:
    table_path = Path(path)
    if not table_path.exists():
        raise FileNotFoundError(f"CACTI SRAM energy table not found: {table_path}")

    rows: dict[int, dict[str, Any]] = {}
    with table_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            budget_kb = int(raw["sram_budget_kb"])
            rows[budget_kb] = {
                "sram_budget_kb": budget_kb,
                "capacity_bytes": int(raw["capacity_bytes"]),
                "technology_nm": float(raw["technology_nm"]),
                "access_bytes": int(raw["access_bytes"]),
                "bus_width_bits": int(raw["bus_width_bits"]),
                "read_pj_per_access": float(raw["read_pj_per_access"]),
                "write_pj_per_access": float(raw["write_pj_per_access"]),
                "read_pj_per_byte": float(raw["read_pj_per_byte"]),
                "write_pj_per_byte": float(raw["write_pj_per_byte"]),
                "access_time_ns": float(raw["access_time_ns"]),
                "cycle_time_ns": float(raw["cycle_time_ns"]),
                "leakage_mw": float(raw["leakage_mw"]),
                "gate_leakage_mw": float(raw["gate_leakage_mw"]),
                "area_mm2": float(raw["area_mm2"]),
                "source": raw.get("source", "CACTI"),
            }

    if not rows:
        raise ValueError(f"CACTI SRAM energy table is empty: {table_path}")
    return rows


def sram_energy_for_budget(config: dict[str, Any], sram_budget_kb: int) -> dict[str, Any]:
    energy_config = config["energy"]
    sram_config = energy_config.get("sram", {})

    if sram_config.get("source") == "cacti":
        table_path = _resolve_table_path(config, sram_config["table"])
        table = load_cacti_sram_table(str(table_path))
        if sram_budget_kb not in table:
            available = ", ".join(str(key) for key in sorted(table))
            raise KeyError(f"No CACTI SRAM row for {sram_budget_kb} KB; available budgets: {available}")
        row = table[sram_budget_kb]
        return {
            "sram_energy_source": "cacti",
            "sram_energy_table": _display_table_path(config, sram_config["table"]),
            "sram_read_pj_per_byte": row["read_pj_per_byte"],
            "sram_write_pj_per_byte": row["write_pj_per_byte"],
            "sram_read_pj_per_access": row["read_pj_per_access"],
            "sram_write_pj_per_access": row["write_pj_per_access"],
            "sram_access_bytes": row["access_bytes"],
            "sram_technology_nm": row["technology_nm"],
            "sram_access_time_ns": row["access_time_ns"],
            "sram_cycle_time_ns": row["cycle_time_ns"],
            "sram_leakage_mw": row["leakage_mw"],
            "sram_area_mm2": row["area_mm2"],
        }

    if "sram_pj_per_byte" not in energy_config:
        raise KeyError("energy.sram_pj_per_byte is required when energy.sram.source is not 'cacti'")

    sram_pj_per_byte = float(energy_config["sram_pj_per_byte"])
    return {
        "sram_energy_source": "fixed",
        "sram_energy_table": "",
        "sram_read_pj_per_byte": sram_pj_per_byte,
        "sram_write_pj_per_byte": sram_pj_per_byte,
        "sram_read_pj_per_access": sram_pj_per_byte * config["word_bytes"],
        "sram_write_pj_per_access": sram_pj_per_byte * config["word_bytes"],
        "sram_access_bytes": config["word_bytes"],
        "sram_technology_nm": 0.0,
        "sram_access_time_ns": 0.0,
        "sram_cycle_time_ns": 0.0,
        "sram_leakage_mw": 0.0,
        "sram_area_mm2": 0.0,
    }


def dram_energy_params(config: dict[str, Any]) -> dict[str, float]:
    energy_config = config["energy"]
    read = energy_config.get("dram_read_pj_per_byte", energy_config.get("dram_pj_per_byte"))
    write = energy_config.get("dram_write_pj_per_byte", energy_config.get("dram_pj_per_byte"))
    if read is None or write is None:
        raise KeyError("DRAM energy requires dram_pj_per_byte or separate dram_read/write_pj_per_byte values")
    return {"dram_read_pj_per_byte": float(read), "dram_write_pj_per_byte": float(write)}
