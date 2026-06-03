import pandas as pd

from hpc_final.analysis import accelergy_action_counts_table


def test_accelergy_plugin_action_counts_use_branch_component_names():
    stage_df = pd.DataFrame(
        [
            {
                "resolution": "720p",
                "frame_width": 1280,
                "frame_height": 720,
                "tile_width": 128,
                "tile_height": 128,
                "gaussian_kernel": 3,
                "array_size": 16,
                "sram_budget_kb": 256,
                "bandwidth_gbps": 50,
                "dataflow": "ws",
                "run_name": "run",
                "spec_hash": "spec",
                "simulation_hash": "sim",
                "tile_class": "full",
                "stage": "gaussian",
                "stage_op": "gaussian",
                "scaled_macs": 10,
                "scaled_sram_ifmap_reads": 8,
                "scaled_sram_filter_reads": 7,
                "scaled_sram_ofmap_writes": 5,
                "scaled_dram_ifmap_reads": 11,
                "scaled_dram_filter_reads": 13,
                "scaled_dram_ofmap_writes": 6,
            }
        ]
    )

    counts = accelergy_action_counts_table(stage_df)

    assert set(zip(counts["component"], counts["action"])) == {
        ("systolic_array.PE[0..255].mac", "mac_random"),
        ("systolic_array.ifmap_glb", "read"),
        ("systolic_array.weights_glb", "read"),
        ("systolic_array.psum_glb", "update"),
        ("systolic_array.ifmap_dram", "read"),
        ("systolic_array.weights_dram", "read"),
        ("systolic_array.psum_dram", "write"),
    }
