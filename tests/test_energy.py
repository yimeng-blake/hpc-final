from hpc_final.energy import energy_breakdown_from_component_action_energy_pj


def test_energy_total_is_component_sum():
    result = energy_breakdown_from_component_action_energy_pj(
        macs=10,
        sram_ifmap_reads=8,
        sram_filter_reads=7,
        sram_ofmap_writes=5,
        dram_ifmap_reads=11,
        dram_filter_reads=13,
        dram_ofmap_writes=6,
        mac_pj_per_action=0.2,
        sram_ifmap_read_pj_per_action=8,
        sram_filter_read_pj_per_action=6,
        sram_ofmap_write_pj_per_action=7,
        dram_ifmap_read_pj_per_action=1,
        dram_filter_read_pj_per_action=2,
        dram_ofmap_write_pj_per_action=3,
    )
    assert (
        result["energy_total_pj"]
        == result["energy_mac_pj"] + result["energy_sram_pj"] + result["energy_dram_pj"]
    )


def test_component_action_energy_uses_separate_generated_action_costs():
    result = energy_breakdown_from_component_action_energy_pj(
        macs=10,
        sram_ifmap_reads=8,
        sram_filter_reads=7,
        sram_ofmap_writes=5,
        dram_ifmap_reads=11,
        dram_filter_reads=13,
        dram_ofmap_writes=6,
        mac_pj_per_action=0.2,
        sram_ifmap_read_pj_per_action=8,
        sram_filter_read_pj_per_action=6,
        sram_ofmap_write_pj_per_action=7,
        dram_ifmap_read_pj_per_action=1,
        dram_filter_read_pj_per_action=2,
        dram_ofmap_write_pj_per_action=3,
    )

    assert result["energy_mac_pj"] == 2
    assert result["energy_sram_pj"] == 141
    assert result["energy_dram_pj"] == 55
    assert result["energy_total_pj"] == 198
