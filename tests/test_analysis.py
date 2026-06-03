import pandas as pd

from hpc_final.analysis import GROUP_COLS, drop_incomplete_configs, pipeline_summary


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


def test_pipeline_summary_reports_cycles_times_pes():
    stage_row = {
        **_record("720p"),
        "scaled_cycles": 1000,
        "scaled_stall_cycles": 100,
        "scaled_macs": 2000,
        "scaled_sram_accesses": 300,
        "scaled_sram_ifmap_reads": 100,
        "scaled_sram_filter_reads": 50,
        "scaled_sram_ofmap_writes": 150,
        "scaled_dram_accesses": 40,
        "scaled_dram_ifmap_reads": 20,
        "scaled_dram_filter_reads": 10,
        "scaled_dram_ofmap_writes": 10,
        "energy_mac_pj": 2,
        "energy_sram_ifmap_pj": 3,
        "energy_sram_filter_pj": 4,
        "energy_sram_ofmap_pj": 5,
        "energy_sram_pj": 12,
        "energy_dram_ifmap_pj": 6,
        "energy_dram_filter_pj": 7,
        "energy_dram_ofmap_pj": 8,
        "energy_dram_pj": 21,
        "energy_total_pj": 35,
        "analytical_lower_bound_ms": 0.001,
        "energy_backend": "accelergy_plugin",
        "energy_model": "accelergy_component_library_table_plugin",
        "sram_read_pj_per_byte": 5,
        "sram_write_pj_per_byte": 5,
        "dram_read_pj_per_byte": 160,
        "dram_write_pj_per_byte": 160,
    }
    summary = pipeline_summary(pd.DataFrame([stage_row]), {"frequency_hz": 1_000_000_000})

    assert summary.loc[0, "num_pes"] == 128 * 128
    assert summary.loc[0, "cycles_x_pes"] == 1000 * 128 * 128
