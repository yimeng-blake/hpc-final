# Deadline-Constrained Systolic Array Design for Image Processing

Blake Wang and Yu Cheng Wu  
CSEN 318 High-Performance Computer Architecture and Systems, Spring 2026

## 1. Introduction

### Motivation

Real-time embedded vision systems process frames on a fixed schedule. A 30 FPS camera pipeline receives a new frame every 33.33 ms, so the accelerator does not need to be the fastest possible design. It needs to finish the full image-processing pipeline before the frame deadline while using as little energy as possible.

This project studies that tradeoff for a grayscale image-processing front end:

```text
input frame -> Gaussian blur -> Sobel edge detection -> edge frame
```

The project models accelerator performance and energy for the two compute stages. It does not model camera capture, display, CPU orchestration, software scheduling overhead, image quality, or full-system idle power. Those parts are outside the boundary of this class project.

### Objective

The objective is to find the minimum-energy systolic array configuration that completes a full image frame before a target deadline. Each design is defined by array size, SRAM budget, external memory bandwidth, dataflow, Gaussian kernel size, image resolution, and frame deadline. For each design, the framework estimates full-frame latency, full-frame energy, average power at a target frame rate, energy-delay product, and deadline feasibility.

The selection rule is:

1. Simulate tiled Gaussian and Sobel workloads with SCALE-Sim.
2. Scale tile-level results to a full frame.
3. Convert compute and memory activity into Accelergy action counts.
4. Use Accelergy-generated energy tables for per-action energy.
5. Remove designs that miss the deadline.
6. Select the minimum-energy feasible design.

### Literature And Market Context

Systolic arrays are a standard architecture for regular matrix-style computation because processing elements can reuse operands while data moves through the array [1]. Modern vision and machine-learning accelerators use similar ideas because image filters and convolution layers can be expressed as matrix operations. SCALE-Sim provides a configurable cycle-level systolic-array simulator [2], while Accelergy provides architecture-level energy estimation from component actions and energy reference tables [3].

The market motivation is embedded and edge vision, where power budgets matter as much as raw throughput. A camera service may target 24 FPS for video-like processing, 30 FPS for common real-time vision, or 60 FPS for smoother interactive systems. The experiment therefore treats the frame deadline as a first-class constraint instead of optimizing only for minimum latency.

## 2. System Design And Implementation Details

### Application Scenario

The modeled application is a grayscale camera front end. Each frame is first smoothed with Gaussian blur to reduce noise, then passed through Sobel edge detection to produce horizontal and vertical gradients. The Gaussian stage has variable compute intensity because the kernel sizes are swept across 3x3, 5x5, 7x7, and 11x11. Sobel always uses two 3x3 filters.

The end-to-end modeled frame latency is:

```text
T_frame = T_gaussian + T_sobel
```

The end-to-end modeled frame energy is:

```text
E_frame = E_gaussian + E_sobel
```

The output overhead in `configs/experiment.yaml` is set to 0 cycles. This is an explicit simplification so the project focuses on accelerator mapping and architecture tradeoffs for the two compute stages.

### Workload Mapping To GEMM

The project does not run arbitrary GEMMs unrelated to the application. It lowers each image filter tile into a GEMM-like workload because SCALE-Sim accepts matrix-style inputs.

For one output pixel, a stencil filter is a dot product between a local image neighborhood and filter weights. For a whole output tile, these dot products become a matrix multiply:

```text
output matrix = lowered image neighborhoods x filter weights
```

For Gaussian blur:

```text
M = output pixels in the tile
N = 1 output channel
K = gaussian_kernel_size^2
MACs per tile = M * K
```

For Sobel edge detection:

```text
M = output pixels in the tile
N = 2 output channels, one for Gx and one for Gy
K = 9 input values per 3x3 filter
MACs per tile = M * 2 * 9
```

These are skinny GEMMs because `N` is only 1 or 2. That shape is important: a large systolic array can have poor utilization if the workload does not expose enough parallelism across the matrix dimensions.

### Tiled Full-Frame Scaling

Directly simulating every full frame for every design would be too slow. The framework simulates representative 128x128 output tiles and scales them to full frames. It handles full interior tiles, right-edge tiles, bottom-edge tiles, and corner tiles. Halo pixels are included in input traffic because convolution filters need neighboring pixels, but halo pixels do not produce additional output pixels.

For each tile class, SCALE-Sim reports cycles, stalls, utilization, SRAM accesses, and DRAM accesses. The framework multiplies those values by the tile-class count and then sums Gaussian and Sobel to produce frame-level metrics.

### Tools And Technologies

The framework uses:

- Python scripts and a small reusable `src/hpc_final` package for workload generation, tiling, parsing, aggregation, and plotting.
- SCALE-Sim for systolic-array cycle, utilization, stall, SRAM, and DRAM access estimates.
- Accelergy through the component-library/table-plug-in path for generated per-action energy values.
- Pandas and Matplotlib for summary CSVs and figures.
- Pytest tests for config parsing, workload shapes, tiling, energy accounting, result aggregation, and SCALE-Sim I/O generation.

The active pipeline is:

```text
image-filter stage -> GEMM topology -> SCALE-Sim reports
-> action counts -> Accelergy ERT -> energy and latency summaries
```

CACTI, Timeloop, Aladdin, RTL synthesis, and measured silicon power are not part of the active final pipeline.

### Design Space And Assumptions

The coarse sweep covers three resolutions: 720p, 1080p, and 2048x2048. It evaluates Gaussian kernels of 3x3, 5x5, 7x7, and 11x11; array sizes from 8x8 to 128x128; SRAM budgets of 256 KB, 1024 KB, and 4096 KB; bandwidths of 50 GB/s, 200 GB/s, and 800 GB/s; and weight-stationary, output-stationary, and input-stationary dataflows.

A focused refinement sweep is added around the main 1080p real-time objective. It evaluates 32x32, 48x48, 64x64, 96x96, and 128x128 arrays; SRAM budgets from 256 KB to 4096 KB; 50 GB/s and 100 GB/s bandwidth; and weight-stationary plus input-stationary dataflows.

The clock is modeled as 1 GHz, so:

```text
latency_ms = cycles / 1e9 * 1000
deadline_cycles = deadline_ms * 1e9 / 1000
```

At 1 GHz, 60 FPS corresponds to 16.67 million cycles, 30 FPS to 33.33 million cycles, and 24 FPS to 41.67 million cycles. Changing the clock would linearly scale latency and deadline feasibility, but it would not change the counted MAC, SRAM, or DRAM actions for a fixed SCALE-Sim run.

The energy model is dynamic action-count energy. It includes MAC actions and SRAM/DRAM read/write actions reported through the model. It does not include SRAM leakage/static energy, wire energy, memory-controller energy, host CPU energy, or idle power. Therefore, any energy conclusion should be read as a comparative modeled result, not a measured full-system power claim.

## 3. Experimental Results And Evaluation

### Experimental Setup

The final Accelergy-backed summary contains 6,052 stage-level rows, 1,767 complete pipeline configurations, 5,301 deadline-expanded feasibility rows, 165 Pareto-frontier rows, 36 minimum-energy rows, and 42,364 Accelergy action-count rows. The final CSV outputs are in `outputs/summary_accelergy_plugin/`, and final figures are in `figures_accelergy_plugin/`.

Some pathological SCALE-Sim demand-generation cases were skipped by a resource guard and recorded in `skipped_runs.csv`. A retry pass recovered 76 of the original 128 unique raw skipped runs. Remaining skipped rows are excluded from full-pipeline summaries so partial tile results do not contaminate end-to-end frame results.

### Main 1080p Real-Time Results

For the main 1080p @ 33 ms objective, the minimum-energy feasible designs are:

| Gaussian Kernel | Best Design | SRAM | Bandwidth | Latency | Energy | EDP |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 3x3 | 128x128 input-stationary | 1024 KB | 50 GB/s | 13.30 ms | 0.445 mJ | 5.92 mJ-ms |
| 5x5 | 128x128 input-stationary | 2048 KB | 50 GB/s | 13.96 ms | 0.779 mJ | 10.88 mJ-ms |
| 7x7 | 64x64 weight-stationary | 256 KB | 50 GB/s | 4.64 ms | 1.279 mJ | 5.93 mJ-ms |
| 11x11 | 128x128 weight-stationary | 256 KB | 50 GB/s | 7.62 ms | 2.773 mJ | 21.12 mJ-ms |

The result is workload-dependent. Input-stationary wins the smaller 3x3 and 5x5 kernels by energy even though it is slower. Because those designs still meet the deadline, the optimizer chooses lower energy over extra speed. Weight-stationary wins for 7x7 and 11x11 because the heavier Gaussian stage exposes more useful work for the array.

The focused 1080p refinement pass did not find a lower-energy design than the coarse sweep. It did improve the selected 5x5 SRAM point from 4096 KB to 2048 KB at the same modeled latency and energy.

### Deadline Sensitivity: 60 FPS, 30 FPS, And 24 FPS

The frame-rate feedback does not require new simulator runs because `pipeline_runs.csv` already contains per-frame latency and energy. Different FPS targets simply change the deadline filter.

For the 1080p winners above, all four selected designs meet 60 FPS, 30 FPS, and 24 FPS:

| Kernel | Selected Design | Latency | 60 FPS Deadline | 30 FPS Deadline | 24 FPS Deadline |
| --- | --- | ---: | ---: | ---: | ---: |
| 3x3 | 128x128 IS | 13.30 ms | feasible | feasible | feasible |
| 5x5 | 128x128 IS | 13.96 ms | feasible | feasible | feasible |
| 7x7 | 64x64 WS | 4.64 ms | feasible | feasible | feasible |
| 11x11 | 128x128 WS | 7.62 ms | feasible | feasible | feasible |

Because the selected 1080p designs are already below the 16.67 ms 60 FPS deadline, changing from 30 FPS to 60 FPS or 24 FPS does not change the selected 1080p designs in the current sweep. Energy per frame also stays the same; average power scales with frame rate.

### Resolution Sensitivity

The 33 ms winners across the evaluated resolutions are:

| Resolution | Kernel | Best Design | Latency | Energy |
| --- | ---: | --- | ---: | ---: |
| 720p | 3x3 | 128x128 IS, 1024 KB, 50 GB/s | 5.91 ms | 0.198 mJ |
| 720p | 5x5 | 32x32 WS, 256 KB, 50 GB/s | 2.05 ms | 0.346 mJ |
| 720p | 7x7 | 64x64 WS, 256 KB, 50 GB/s | 2.06 ms | 0.568 mJ |
| 720p | 11x11 | 128x128 WS, 256 KB, 50 GB/s | 3.39 ms | 1.233 mJ |
| 1080p | 3x3 | 128x128 IS, 1024 KB, 50 GB/s | 13.30 ms | 0.445 mJ |
| 1080p | 5x5 | 128x128 IS, 2048 KB, 50 GB/s | 13.96 ms | 0.779 mJ |
| 1080p | 7x7 | 64x64 WS, 256 KB, 50 GB/s | 4.64 ms | 1.279 mJ |
| 1080p | 11x11 | 128x128 WS, 256 KB, 50 GB/s | 7.62 ms | 2.773 mJ |
| 2048x2048 | 3x3 | 128x128 IS, 1024 KB, 50 GB/s | 26.89 ms | 0.901 mJ |
| 2048x2048 | 5x5 | 32x32 WS, 256 KB, 50 GB/s | 9.29 ms | 1.573 mJ |
| 2048x2048 | 7x7 | 64x64 WS, 256 KB, 50 GB/s | 9.34 ms | 2.585 mJ |
| 2048x2048 | 11x11 | 128x128 WS, 256 KB, 50 GB/s | 15.37 ms | 5.608 mJ |

The project evaluates up to 2048x2048, not 8K. An 8K frame would require a new workload point because it has about 33.2 million pixels, roughly 16 times 1080p. The current tiling and aggregation framework can support adding that case, but it is left as future work because the final report focuses on completed, reproduced results.

### Stage And Component Energy Analysis

For the 1080p @ 33 ms minimum-energy designs, Gaussian energy share increases with kernel size:

| Kernel | Selected Dataflow | Gaussian Energy Share | Sobel Energy Share |
| --- | --- | ---: | ---: |
| 3x3 | IS | 45.91% | 54.09% |
| 5x5 | IS | 69.09% | 30.91% |
| 7x7 | WS | 81.01% | 18.99% |
| 11x11 | WS | 91.24% | 8.76% |

This happens because Sobel remains fixed at two 3x3 filters, while Gaussian work grows from 9 values per output pixel at 3x3 to 121 values per output pixel at 11x11.

The component energy split for the same selected designs is:

| Kernel | MAC Energy | SRAM Dynamic Energy | DRAM Dynamic Energy |
| --- | ---: | ---: | ---: |
| 3x3 | 12.6% | 77.6% | 9.8% |
| 5x5 | 11.4% | 78.7% | 9.9% |
| 7x7 | 10.9% | 78.7% | 10.5% |
| 11x11 | 10.4% | 79.3% | 10.3% |

This supports a scoped conclusion: in this dynamic action-count model, memory actions dominate the selected designs. It does not prove that all physical systolic arrays are memory dominated, because static SRAM energy, wires, clocking, control, and system overhead are outside the model.

### Interpretation

The main architectural finding is that the best array is not simply the largest array or a fixed dataflow. It depends on workload shape and deadline. For small kernels, input-stationary can save energy while still meeting the real-time deadline. For larger kernels, weight-stationary becomes better because Gaussian blur dominates total work and larger arrays are used more effectively.

The deadline-constrained framing matters because minimum latency and minimum energy are different objectives. A design that finishes far before the frame deadline can still be worse if a slower design satisfies the deadline with lower energy.

## 4. Conclusions

The project successfully built a reproducible SCALE-Sim plus Accelergy framework for deadline-constrained systolic-array design exploration. The implementation connects a concrete image-processing application to GEMM-lowered tile workloads, scales tile results to full frames, and reports latency, energy, EDP, feasibility, bottlenecks, and Pareto results.

Things that worked well:

- Tiled simulation made full-frame sweeps tractable.
- Accelergy action-count energy made the energy model more defensible than manually hardcoded constants.
- The 1080p refinement sweep showed that the coarse design grid did not hide a lower-energy winner.
- The analysis identified workload-dependent dataflow choices instead of claiming that one dataflow always wins.

Things that did not work as well:

- Some SCALE-Sim input-stationary and output-stationary large-kernel cases became resource-heavy and had to be skipped with documented guards.
- The model covers dynamic accelerator actions but not static/leakage energy or full-system overhead.
- The evaluated application is grayscale Gaussian plus Sobel only; color images, 8K frames, and additional image-processing stages are left for future work.

The final conclusion is that real-time accelerator sizing should be based on workload shape and frame deadline. For this workload, 1080p 3x3 and 5x5 kernels favor 128x128 input-stationary designs, while 7x7 and 11x11 favor weight-stationary designs. Bigger hardware is not automatically better; it is only useful when the workload can keep it busy enough to justify the energy cost.

## 5. Team Contributions And Acknowledgement

### Task Allocation And Contributions

| Component | Assigned / Completed By | Contribution |
| --- | --- | ---: |
| Project framing, workload selection, and presentation narrative | Blake Wang and Yu Cheng Wu | Shared |
| SCALE-Sim workload generation, tiling, and sweep scripts | Blake Wang | 50% |
| Accelergy integration, action-count mapping, and energy summaries | Yu Cheng Wu | 50% |
| Result analysis, figures, report writing, and feedback-driven revision | Blake Wang and Yu Cheng Wu | Shared |

Estimated total contribution: Blake Wang 50%, Yu Cheng Wu 50%.

### Generative AI Use

Generative AI tools were used to help revise writing, organize the report, inspect code consistency, and suggest ways to explain the experiment more clearly. The team remained responsible for running the experiments, checking generated result tables, validating repository outputs, and deciding the final technical conclusions.

## References

[1] H. T. Kung, "Why Systolic Architectures?", Computer, vol. 15, no. 1, pp. 37-46, 1982.

[2] A. Samajdar et al., "SCALE-Sim: Systolic CNN Accelerator Simulator", arXiv:1811.02883, 2018. https://arxiv.org/abs/1811.02883

[3] Y. N. Wu et al., "Accelergy: An Architecture-Level Energy Estimation Methodology for Accelerator Designs", IEEE/ACM ICCAD, 2019. https://accelergy.mit.edu/paper.pdf
