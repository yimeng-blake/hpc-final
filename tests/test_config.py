from hpc_final.config import selected_sweep_values


def _base_config():
    return {
        "resolutions": {
            "720p": {"width": 1280, "height": 720, "deadlines_ms": [33]},
            "1080p": {"width": 1920, "height": 1080, "deadlines_ms": [33]},
        },
        "gaussian_kernels": [3, 5, 7, 11],
        "array_sizes": [8, 16, 32, 64, 128],
        "sram_budgets_kb": [256, 1024, 4096],
        "bandwidths_gbps": [50, 200, 800],
        "dataflows": ["ws", "os", "is"],
        "tile_sizes": {
            "sanity": {"width": 64, "height": 64},
            "full": {"width": 128, "height": 128},
        },
    }


def test_refinement_sweep_uses_configured_fine_values_and_full_tile_default():
    config = {
        **_base_config(),
        "refinement_sweep": {
            "array_sizes": [24, 32, 48],
            "sram_budgets_kb": [256, 512, 1024],
            "bandwidths_gbps": [50, 100],
            "dataflows": ["ws", "is"],
        },
    }

    values = selected_sweep_values(config, "refinement")

    assert values["resolutions"] == ["720p", "1080p"]
    assert values["array_sizes"] == [24, 32, 48]
    assert values["sram_budgets_kb"] == [256, 512, 1024]
    assert values["bandwidths_gbps"] == [50, 100]
    assert values["dataflows"] == ["ws", "is"]
    assert values["tile_size"] == {"width": 128, "height": 128}
