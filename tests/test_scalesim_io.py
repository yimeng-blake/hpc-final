from hpc_final.scalesim_io import bandwidth_words_per_cycle, split_sram_budget


def test_bandwidth_conversion_words_per_cycle():
    assert bandwidth_words_per_cycle(50, 1_000_000_000, 1) == 50
    assert bandwidth_words_per_cycle(200, 1_000_000_000, 2) == 100


def test_sram_split_preserves_budget():
    parts = split_sram_budget(1024, 0.45, 0.10, 0.45)
    assert sum(parts) == 1024
    assert all(part > 0 for part in parts)
