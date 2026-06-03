# Deadline-Constrained Systolic Array Design for Image Processing

## Motivation

Real-time embedded vision systems have to process frames on a fixed schedule. A 30 FPS camera pipeline receives a new frame every 33 ms, so an accelerator does not need to be maximally fast; it needs to finish before the deadline while using as little energy as possible.

This project models that tradeoff for a simple but realistic image-processing pipeline:

```text
Gaussian blur -> Sobel edge detection
```

The central design question is not "which configuration is fastest?" The useful question is:

> Which systolic array configuration minimizes energy per frame while still meeting the frame deadline?

That framing matters because a design that finishes in 4 ms can be worse than a design that finishes in 14 ms if both meet a 33 ms deadline and the slower one uses less energy.

## Problem Statement

The project explores a deadline-constrained hardware design space for a tiled image-processing workload. Each design is defined by:

- Systolic array size.
- SRAM budget.
- External memory bandwidth.
- Dataflow.
- Gaussian kernel size.
- Image resolution.

For each design, the project estimates:

- Full-frame latency.
- Full-frame energy.
- Average power at 30 FPS.
- Energy-delay product.
- Deadline feasibility.

The selection rule is:

1. Simulate each tile-level workload with SCALE-Sim.
2. Scale representative tile results to a full frame.
3. Convert compute and memory activity into Accelergy action counts.
4. Let Accelergy generate Energy Reference Tables through its component-library/table-plug-in path.
5. Compute energy from the generated per-action costs.
6. Remove designs that miss the target deadline.
7. Pick the minimum-energy feasible design.

## Workload Explored And Justification

The modeled workload is grayscale Gaussian blur followed by Sobel edge detection.

This workload was chosen because it is small enough to model clearly, but large enough to expose real accelerator tradeoffs:

- It touches every pixel.
- It has regular stencil-style memory access.
- It maps naturally to matrix-style compute after lowering.
- Its compute intensity changes with Gaussian kernel size.
- It is common in embedded image-processing and computer-vision front ends.

The evaluated frame resolutions are:

| Resolution | Frame Size | Pixels |
| --- | ---: | ---: |
| 720p | 1280 x 720 | 921,600 |
| 1080p | 1920 x 1080 | 2,073,600 |
| hires | 2048 x 2048 | 4,194,304 |

The Gaussian kernels are:

| Gaussian Kernel | Values Per Output Pixel |
| --- | ---: |
| 3x3 | 9 |
| 5x5 | 25 |
| 7x7 | 49 |
| 11x11 | 121 |

Sobel uses the standard 3x3 horizontal and vertical filters. That means the Sobel stage has fixed work per pixel, while the Gaussian stage becomes increasingly dominant as kernel size grows.

## Methodology

### GEMM Lowering

SCALE-Sim models matrix-style workloads on systolic arrays. The stencil kernels are lowered into GEMM-like shapes.

For Gaussian blur:

```text
M = output tile pixels
N = 1
K = kernel_size^2
```

For Sobel edge detection:

```text
M = output tile pixels
N = 2
K = 9
```

`M` is the number of output pixels in the tile, `N` is the number of output channels or filters, and `K` is the number of input values used per output.

These are skinny GEMMs. That is important because larger systolic arrays are not always better: the workload may not expose enough parallelism to keep every processing element busy.

### Tiled Full-Frame Scaling

The full sweep would be too expensive if every full frame were simulated directly. Instead, the project simulates representative tile classes and scales them to the full frame.

The final experiment uses 128 x 128 output tiles. The model accounts for:

- Full interior tiles.
- Right-edge tiles.
- Bottom-edge tiles.
- Corner tiles.
- Halo pixels needed by convolution kernels.

Tile-level cycles, memory accesses, and action counts are multiplied by the number of occurrences of each tile class in the full frame.

### SCALE-Sim Performance Modeling

SCALE-Sim provides the performance and activity side of the model:

- Cycles.
- Stall cycles.
- Utilization.
- SRAM IFMAP reads.
- SRAM filter reads.
- SRAM OFMAP writes.
- DRAM IFMAP reads.
- DRAM filter reads.
- DRAM OFMAP writes.

The final sweep covers these hardware parameters:

| Parameter | Values |
| --- | --- |
| Array sizes | 8x8, 16x16, 32x32, 64x64, 128x128 |
| SRAM budgets | 256 KB, 1024 KB, 4096 KB |
| Bandwidths | 50 GB/s, 200 GB/s, 800 GB/s |
| Dataflows | weight-stationary, output-stationary, input-stationary |
| Frequency | 1 GHz |
| Word size | 1 byte |

### Frequency Assumption

SCALE-Sim reports cycle counts, not wall-clock time. This project converts cycles to milliseconds by assuming a 1 GHz accelerator clock:

```text
latency_ms = cycles / 1e9 * 1000
```

The 1 GHz value is used as a clear reference operating point rather than a claim that every implementation would close timing at exactly that frequency. It is a common modeling convention for architecture studies because it makes cycle counts easy to interpret: one cycle is one nanosecond, and one million cycles is one millisecond.

The assumption is also intentionally separated from the energy model. In this project, Accelergy estimates energy from action counts and generated per-action costs. Changing the clock frequency would scale latency and EDP, but it would not change the counted MAC, SRAM, or DRAM actions for a given SCALE-Sim run. Therefore, the frequency assumption mainly affects deadline feasibility and latency-derived metrics.

The selected 33 ms designs have enough timing margin at 1 GHz. Across all 33 ms winners, the slowest selected design is the hires 3x3 input-stationary case at 26.89 ms. That design would need roughly 815 MHz to meet 33 ms:

```text
required_frequency = reported_latency_at_1GHz / deadline * 1GHz
                   = 26.89 / 33 * 1GHz
                   = 0.815GHz
```

For the main 1080p cases, the required frequency is lower:

| Kernel | Selected Dataflow | Latency At 1 GHz | Minimum Frequency For 33 ms |
| --- | --- | ---: | ---: |
| 3x3 | IS | 13.30 ms | 403 MHz |
| 5x5 | IS | 13.96 ms | 423 MHz |
| 7x7 | WS | 4.64 ms | 141 MHz |
| 11x11 | WS | 7.62 ms | 231 MHz |

This makes 1 GHz a reasonable reference point for the deadline-constrained study: it is high enough to keep the selected real-time designs feasible, but the conclusion is not relying on a barely feasible timing point. If a different target clock is desired, the reported latencies can be rescaled linearly.

### Accelergy Energy Modeling

Energy is modeled through the Accelergy component-library/table-plug-in path, not through manually hardcoded ERT constants.

The project writes Accelergy architecture and action-count YAML files, invokes Accelergy, and parses the generated `energy_estimation.yaml` and ERT outputs. The generated pJ/action values are then applied to the SCALE-Sim counts.

The key component mappings are:

| SCALE-Sim Count | Accelergy Component | Action |
| --- | --- | --- |
| MAC operations | `systolic_array.PE[0..N].mac` | `mac_random` |
| SRAM IFMAP reads | `systolic_array.ifmap_glb` | `read` |
| SRAM filter reads | `systolic_array.weights_glb` | `read` |
| SRAM OFMAP writes | `systolic_array.psum_glb` | `update` |
| DRAM IFMAP reads | `systolic_array.ifmap_dram` | `read` |
| DRAM filter reads | `systolic_array.weights_dram` | `read` |
| DRAM OFMAP writes | `systolic_array.psum_dram` | `write` |

The generated Accelergy artifacts are saved under:

```text
outputs/summary_accelergy_plugin/accelergy_plugin/
```

### Skipped-Only Retry Pass

After adding input-stationary dataflow, some large-kernel SCALE-Sim demand-generation cases became pathological. Rather than leaving all of them skipped, the project added a skipped-only retry script:

```text
scripts/rerun_skipped.py
```

This script reruns only raw directories that contain `SKIPPED.json`. Each case runs in an isolated child process with an RSS guard. This recovered many cases without rerunning the full sweep.

Retry outcome:

| Metric | Count |
| --- | ---: |
| Original unique raw skipped runs | 128 |
| Recovered raw runs | 76 |
| Remaining unique raw skipped runs | 52 |
| Final summary-level skipped rows | 116 |
| Remaining skipped IS rows | 98 |
| Remaining skipped OS rows | 18 |

Remaining skipped cases are documented in:

```text
outputs/summary_accelergy_plugin/skipped_runs.csv
outputs/summary_accelergy_plugin/rerun_skipped_log.csv
```

## Results

### Final Dataset

The final Accelergy-plugin-backed summary contains:

| Output | Rows |
| --- | ---: |
| Stage-level rows | 5,068 |
| Complete pipeline configurations | 1,521 |
| Feasibility rows | 4,563 |
| Pareto-frontier rows | 150 |
| Minimum-energy design rows | 36 |
| Bottleneck-summary rows | 3,042 |
| Accelergy action-count rows | 35,476 |
| Skipped simulator rows | 116 |

The final outputs are in:

```text
outputs/summary_accelergy_plugin/
figures_accelergy_plugin/
```

### 1080p At 33 ms

For the main 1080p real-time case, the minimum-energy feasible designs are:

| Gaussian Kernel | Best Design | SRAM | Bandwidth | Latency | Energy | EDP |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 3x3 | 128x128 input-stationary | 1024 KB | 50 GB/s | 13.30 ms | 0.445 mJ | 5.92 mJ-ms |
| 5x5 | 128x128 input-stationary | 4096 KB | 50 GB/s | 13.96 ms | 0.779 mJ | 10.88 mJ-ms |
| 7x7 | 64x64 weight-stationary | 256 KB | 50 GB/s | 4.64 ms | 1.279 mJ | 5.93 mJ-ms |
| 11x11 | 128x128 weight-stationary | 256 KB | 50 GB/s | 7.62 ms | 2.773 mJ | 21.12 mJ-ms |

The important change after adding input-stationary is that the conclusion is no longer "weight-stationary is always best." Input-stationary wins the smaller 3x3 and 5x5 kernels by energy, even though it is slower. Because it still meets the 33 ms deadline, the deadline-constrained optimizer correctly chooses lower energy over extra speed.

### 33 ms Winners Across Resolutions

| Resolution | Kernel | Best Design | Latency | Energy |
| --- | ---: | --- | ---: | ---: |
| 720p | 3x3 | 128x128 IS, 1024 KB, 50 GB/s | 5.91 ms | 0.198 mJ |
| 720p | 5x5 | 32x32 WS, 256 KB, 50 GB/s | 2.05 ms | 0.346 mJ |
| 720p | 7x7 | 64x64 WS, 256 KB, 50 GB/s | 2.06 ms | 0.568 mJ |
| 720p | 11x11 | 128x128 WS, 256 KB, 50 GB/s | 3.39 ms | 1.233 mJ |
| 1080p | 3x3 | 128x128 IS, 1024 KB, 50 GB/s | 13.30 ms | 0.445 mJ |
| 1080p | 5x5 | 128x128 IS, 4096 KB, 50 GB/s | 13.96 ms | 0.779 mJ |
| 1080p | 7x7 | 64x64 WS, 256 KB, 50 GB/s | 4.64 ms | 1.279 mJ |
| 1080p | 11x11 | 128x128 WS, 256 KB, 50 GB/s | 7.62 ms | 2.773 mJ |
| hires | 3x3 | 128x128 IS, 1024 KB, 50 GB/s | 26.89 ms | 0.901 mJ |
| hires | 5x5 | 32x32 WS, 256 KB, 50 GB/s | 9.29 ms | 1.573 mJ |
| hires | 7x7 | 64x64 WS, 256 KB, 50 GB/s | 9.34 ms | 2.585 mJ |
| hires | 11x11 | 128x128 WS, 256 KB, 50 GB/s | 15.37 ms | 5.608 mJ |

Across all deadline-expanded minimum-energy rows:

| Dataflow | Minimum-Energy Rows |
| --- | ---: |
| Weight-stationary | 24 |
| Input-stationary | 12 |
| Output-stationary | 0 |

### Stage Energy Share

For the 1080p @ 33 ms minimum-energy designs:

| Gaussian Kernel | Selected Dataflow | Gaussian Energy Share | Sobel Energy Share |
| --- | --- | ---: | ---: |
| 3x3 | IS | 45.91% | 54.09% |
| 5x5 | IS | 69.09% | 30.91% |
| 7x7 | WS | 81.01% | 18.99% |
| 11x11 | WS | 91.24% | 8.76% |

The Gaussian stage becomes dominant as the kernel grows. For 11x11, over 91% of selected-design energy is spent in Gaussian blur.

### Figures

The generated plots are:

| Figure | Path |
| --- | --- |
| Latency by array size | `figures_accelergy_plugin/latency_by_array.png` |
| Energy by array size | `figures_accelergy_plugin/energy_by_array.png` |
| Energy-latency scatter | `figures_accelergy_plugin/energy_latency_scatter.png` |
| Feasible counts | `figures_accelergy_plugin/feasible_counts.png` |
| Memory traffic by array | `figures_accelergy_plugin/memory_traffic_by_array.png` |
| Pareto frontier | `figures_accelergy_plugin/pareto_frontier.png` |
| Stage energy share | `figures_accelergy_plugin/stage_energy_share.png` |
| Stall percentage by array | `figures_accelergy_plugin/stall_pct_by_array.png` |
| Utilization by array | `figures_accelergy_plugin/utilization_by_array.png` |

Interpretation for the energy-latency scatter: lower-left is better. Points left of the red 33 ms line meet the 30 FPS timing target at the assumed 1 GHz clock, and black stars mark the minimum-energy feasible designs selected in the results tables.

## Discussion

### Dataflow Is Workload-Dependent

Adding input-stationary changed the interpretation of the project. The result is not that a single dataflow dominates. Instead:

- Input-stationary is energy-best for 1080p 3x3 and 5x5.
- Weight-stationary is energy-best for 1080p 7x7 and 11x11.
- Output-stationary does not win any minimum-energy row in the final Accelergy-plugin-backed results.

This makes the result more credible because the sweep now treats dataflow as an actual design parameter rather than omitting one of SCALE-Sim's supported modes.

### Deadline-Constrained Selection Changes The Design Choice

For the smaller kernels, the input-stationary winners are slower than the corresponding low-latency weight-stationary designs. They still meet the 33 ms deadline. Since the objective is minimum energy among feasible designs, the slower but lower-energy configuration is preferred.

That is the main value of the deadline-constrained framing. It avoids over-designing the accelerator for speed that the application does not need.

### Kernel Size Drives Architecture

As the Gaussian kernel grows, the Gaussian stage dominates both work and energy. The best design shifts accordingly:

- 3x3 and 5x5 have enough deadline slack for energy-oriented IS designs.
- 7x7 shifts back to a 64x64 WS design.
- 11x11 uses a 128x128 WS design because the heavier Gaussian stage exposes more useful parallelism.

The best array size is therefore tied to workload shape, not just frame resolution.

### Energy Modeling Is More Defensible

Earlier hardcoded ERT-style constants would have been difficult to defend. The final pipeline is closer to the assignment methodology:

```text
SCALE-Sim reports -> action counts -> Accelergy component-library/table plug-ins -> generated ERT -> energy results
```

The project still produces modeled energy, not measured silicon energy. But the energy path is reproducible, tool-driven, and inspectable through generated Accelergy artifacts.

### Remaining Skips Are Simulator Resource Limits

The remaining skipped cases are not energy shortcuts. They are SCALE-Sim demand-generation cases that exceeded the retry RSS guard. The retry pass recovered most originally skipped raw runs, then regenerated summaries from the expanded raw cache.

The key point is that the final minimum-energy conclusion is stable after the skipped-only retry:

- Before retry: 24 WS minimum rows, 12 IS minimum rows.
- After retry: 24 WS minimum rows, 12 IS minimum rows.

The recovered cases improved coverage but did not change the architectural conclusion.

## Takeaways

- The final project should conclude that the best dataflow is workload-dependent, not that weight-stationary is universally best.
- Input-stationary is energy-best for the 1080p 3x3 and 5x5 cases.
- Weight-stationary remains energy-best for the 1080p 7x7 and 11x11 cases.
- Deadline-constrained optimization matters: slower designs can be better if they meet the deadline with lower energy.
- Gaussian blur becomes the dominant energy contributor as kernel size increases.
- The Accelergy component-library/table-plug-in path avoids manually hardcoding ERT values and makes the energy flow more defensible.
- The skipped-only retry pass recovered 76 unique raw SCALE-Sim runs and showed that the remaining skips are resource-limited simulator cases, not an unexamined omission.
- The final design recommendation is to size the accelerator and choose the dataflow based on workload shape and frame deadline, not simply to choose the largest array or a fixed dataflow.
