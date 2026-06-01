import pandas as pd

from hpc_final.analysis import GROUP_COLS, drop_incomplete_configs


def _record(resolution: str) -> dict:
    return {
        "resolution": resolution,
        "frame_width": 1280,
        "frame_height": 720,
        "tile_width": 128,
        "tile_height": 128,
        "gaussian_kernel": 11,
        "array_size": 128,
        "sram_budget_kb": 256,
        "bandwidth_gbps": 50,
        "dataflow": "os",
        "tile_class": "right_edge",
    }


def test_drop_incomplete_configs_removes_all_rows_for_skipped_design():
    stage_df = pd.DataFrame([_record("720p"), _record("1080p")])
    skipped_df = pd.DataFrame([{key: _record("720p")[key] for key in GROUP_COLS}])

    complete = drop_incomplete_configs(stage_df, skipped_df)

    assert list(complete["resolution"]) == ["1080p"]
