from hpc_final.energy import energy_breakdown_pj


def test_energy_total_is_component_sum():
    result = energy_breakdown_pj(
        macs=10,
        sram_accesses=20,
        dram_accesses=30,
        word_bytes=1,
        mac_pj=0.2,
        sram_pj_per_byte=5,
        dram_pj_per_byte=100,
    )
    assert result["energy_total_pj"] == result["energy_mac_pj"] + result["energy_sram_pj"] + result["energy_dram_pj"]
