from hpc_final.runner import RunSpec, skip_reason


def make_spec(**overrides):
    values = {
        "resolution": "1080p",
        "frame_width": 1920,
        "frame_height": 1080,
        "tile_width": 128,
        "tile_height": 128,
        "tile_class": "full",
        "tile_out_width": 128,
        "tile_out_height": 128,
        "tile_count": 120,
        "gaussian_kernel": 7,
        "array_size": 32,
        "sram_budget_kb": 256,
        "bandwidth_gbps": 50.0,
        "bandwidth_words_per_cycle": 50,
        "dataflow": "is",
        "frequency_hz": 1_000_000_000,
        "word_bytes": 1,
    }
    values.update(overrides)
    return RunSpec(**values)


def test_input_stationary_large_kernel_128_wide_tiles_are_skipped():
    assert skip_reason(make_spec(gaussian_kernel=7, array_size=32)) is not None
    assert (
        skip_reason(
            make_spec(
                gaussian_kernel=11,
                array_size=8,
                tile_class="bottom_edge",
                tile_out_height=56,
            )
        )
        is not None
    )


def test_input_stationary_smaller_large_kernel_tiles_still_run():
    assert skip_reason(make_spec(gaussian_kernel=7, array_size=16)) is None
    assert skip_reason(make_spec(gaussian_kernel=7, array_size=32, tile_out_width=64)) is None


def test_output_stationary_128_array_11x11_full_tiles_are_skipped():
    assert skip_reason(make_spec(dataflow="os", gaussian_kernel=11, array_size=128)) is not None
    assert skip_reason(make_spec(dataflow="os", gaussian_kernel=11, array_size=64)) is None
