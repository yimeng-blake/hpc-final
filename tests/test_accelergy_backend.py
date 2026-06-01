import pytest

from hpc_final.energy import energy_breakdown_from_access_counts_pj


@pytest.mark.skipif(
    pytest.importorskip("accelergy", reason="Accelergy is optional") is None,
    reason="Accelergy is optional",
)
def test_accelergy_backend_matches_reference_energy_table():
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
        sram_pj_per_byte=5,
        dram_pj_per_byte=100,
        backend="accelergy",
    )
    assert result["energy_mac_pj"] == pytest.approx(2)
    assert result["energy_sram_pj"] == pytest.approx(100)
    assert result["energy_dram_pj"] == pytest.approx(3000)
    assert result["energy_total_pj"] == pytest.approx(3102)
