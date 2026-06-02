from __future__ import annotations

from pathlib import Path

import pytest

from hpc_final.sram_energy import sram_energy_for_budget


def test_cacti_sram_energy_lookup_uses_budget_specific_values(tmp_path: Path):
    table = tmp_path / "sram.csv"
    table.write_text(
        "\n".join(
            [
                "sram_budget_kb,capacity_bytes,technology_nm,access_bytes,bus_width_bits,cache_type,read_pj_per_access,write_pj_per_access,read_pj_per_byte,write_pj_per_byte,access_time_ns,cycle_time_ns,leakage_mw,gate_leakage_mw,area_mm2,source",
                "256,262144,45,4,32,ram,24,16,6,4,1.1,0.7,10,1,0.8,CACTI",
                "1024,1048576,45,4,32,ram,40,32,10,8,2.0,0.4,20,2,3.2,CACTI",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config = {
        "_config_dir": str(tmp_path),
        "word_bytes": 1,
        "energy": {"sram": {"source": "cacti", "table": "sram.csv"}},
    }

    small = sram_energy_for_budget(config, 256)
    large = sram_energy_for_budget(config, 1024)

    assert small["sram_read_pj_per_byte"] == pytest.approx(6)
    assert small["sram_write_pj_per_byte"] == pytest.approx(4)
    assert large["sram_read_pj_per_byte"] == pytest.approx(10)
    assert large["sram_write_pj_per_byte"] == pytest.approx(8)


def test_fixed_sram_energy_fallback_remains_available():
    config = {"word_bytes": 1, "energy": {"sram_pj_per_byte": 5.0}}

    energy = sram_energy_for_budget(config, 256)

    assert energy["sram_energy_source"] == "fixed"
    assert energy["sram_read_pj_per_byte"] == pytest.approx(5.0)
    assert energy["sram_write_pj_per_byte"] == pytest.approx(5.0)
