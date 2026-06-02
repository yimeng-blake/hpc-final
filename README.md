# Deadline-Constrained Systolic Array Design for Image Processing

This project evaluates systolic array accelerator designs for a real-time grayscale image-processing pipeline:

**Gaussian blur -> Sobel edge detection**

The goal is to find the **minimum-energy systolic array configuration** that can process each image frame within a target deadline. The main real-time scenario is **30 FPS**, which gives a deadline of roughly **33 ms per frame**.

The final experiment uses:

- **SCALE-Sim** for systolic-array performance simulation.
- **Accelergy** for table-based ERT/action-count energy calculation.
- **Tiled full-frame scaling** to keep the experiment tractable.
- **Deadline-constrained design selection** to choose energy-efficient feasible hardware.

This version follows the same general direction as the class SCALE-Sim + Accelergy assignments: simulate accelerator performance, convert the simulator results into action counts, apply an Accelergy Energy Reference Table, and report latency, energy, and EDP. CACTI is not part of the active pipeline.

## Problem Statement

Embedded camera and vision systems often process frames on a fixed schedule. A 30 FPS system receives a new frame every 33 ms, so the accelerator must finish the full image-processing pipeline before the next frame arrives.

A design that finishes in 2 ms may waste energy if a smaller design can finish in 20 ms. For a deadline-constrained embedded system, the useful objective is:

> Minimize energy per frame while satisfying the frame deadline.

This project asks:

> Given a frame resolution and deadline, which systolic array size, SRAM budget, memory bandwidth, and dataflow gives the lowest energy while still completing Gaussian blur and Sobel edge detection on time?

The selection rule is:

1. Simulate each hardware design on the image-processing workload.
2. Scale tile-level results to the full frame.
3. Compute latency, energy, average power, and EDP.
4. Remove designs that miss the deadline.
5. Pick the minimum-energy design among the feasible designs.

## Workload Justification

Gaussian blur and Sobel edge detection are good workloads for this project because they are classic DSP and embedded-vision kernels. They are simple enough to model clearly, but large enough to expose real architecture tradeoffs because they touch every pixel in every frame.

A 1080p frame contains:

- 1920 x 1080 pixels.
- 2,073,600 total pixels.

Even a small amount of computation per pixel becomes meaningful when repeated across the full frame and across every frame period.

Gaussian blur smooths the image and reduces noise before edge detection. Sobel edge detection then estimates horizontal and vertical gradients to highlight edges. This is a common front-end image-processing pattern: first reduce noise, then detect structure.

The Gaussian workload scales with kernel size:

| Gaussian Kernel | Values Per Output Pixel |
| --- | ---: |
| 3x3 | 9 |
| 5x5 | 25 |
| 7x7 | 49 |
| 11x11 | 121 |

Sobel uses the standard 3x3 Sobel filters, so its per-pixel filter size stays fixed. This creates a useful experiment: as the Gaussian kernel grows, the Gaussian stage becomes heavier and the best accelerator design can change.

## Pipeline Overview

The modeled pipeline is:

1. Read an 8-bit grayscale image frame.
2. Run Gaussian blur.
3. Run Sobel edge detection.
4. Produce an output edge frame.

The frame latency is modeled as:

```text
T_frame = T_gaussian + T_sobel
```

The frame energy is modeled as:

```text
E_frame = E_gaussian + E_sobel
```

The output overhead is set to 0 cycles in `configs/experiment.yaml`. This is an explicit modeling assumption so the experiment focuses on the two compute stages.

The project models accelerator behavior, not image quality. It does not compare real edge maps or tune filter coefficients visually. The workload is used as a representative embedded image-processing service.

## GEMM Lowering

SCALE-Sim models matrix-style workloads on systolic arrays. Gaussian blur and Sobel edge detection are therefore lowered into GEMM-like shapes.

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

`M` is the number of output pixels produced by the tile. `N` is the number of output channels or filters. `K` is the number of input values used to produce each output value.

Gaussian uses `N = 1` because one blurred grayscale output is produced per pixel. Sobel uses `N = 2` because Sobel computes two gradients: one horizontal gradient and one vertical gradient. Sobel uses `K = 9` because the standard Sobel operator is 3x3.

These shapes are relatively skinny GEMMs. That matters because very large systolic arrays may not stay fully utilized when the matrix shape does not expose enough parallel work.

## Tiled Simulation

Directly simulating a full image frame for every configuration would be too slow. The experiment simulates representative tiles, then scales the results to the full frame.

The main output tile size is **128 x 128 pixels**. For each frame, the model derives tile classes:

- Full interior tile.
- Right-edge tile.
- Bottom-edge tile.
- Corner tile.

Only unique tile classes are simulated. Their cycles and memory accesses are multiplied by the number of times each tile class appears in the full frame.

Halo pixels are included because convolution-style filters need neighboring input pixels:

- Gaussian halo radius is `(kernel_size - 1) / 2`.
- Sobel halo radius is `1`.

Halo pixels increase input memory traffic. They do not increase the number of output pixels.

## SCALE-Sim + Accelergy Methodology

The final modeling pipeline is:

1. Generate Gaussian and Sobel GEMM workloads for each tile class.
2. Run each workload through SCALE-Sim.
3. Parse cycles, stalls, utilization, and detailed memory accesses.
4. Scale tile-level metrics to full-frame metrics.
5. Convert SCALE-Sim memory and compute counts into Accelergy action counts.
6. Generate a table-based Accelergy Energy Reference Table.
7. Use Accelergy to calculate per-component and total energy.
8. Aggregate latency, energy, power, EDP, feasibility, bottlenecks, and Pareto fronts.

SCALE-Sim provides the performance side:

- Total cycles.
- Stall cycles.
- Utilization.
- SRAM IFMAP reads.
- SRAM filter reads.
- SRAM OFMAP writes.
- DRAM IFMAP reads.
- DRAM filter reads.
- DRAM OFMAP writes.

Accelergy provides the energy-accounting side. The project maps SCALE-Sim counts into these Accelergy components:

| SCALE-Sim Count | Accelergy Component | Action |
| --- | --- | --- |
| MAC operations | `accelerator.mac_array` | `mac` |
| SRAM IFMAP reads | `accelerator.ifmap_sram` | `read` |
| SRAM filter reads | `accelerator.filter_sram` | `read` |
| SRAM OFMAP writes | `accelerator.ofmap_sram` | `write` |
| DRAM IFMAP reads | `accelerator.ifmap_dram` | `read` |
| DRAM filter reads | `accelerator.filter_dram` | `read` |
| DRAM OFMAP writes | `accelerator.ofmap_dram` | `write` |

The ERT values are configured in `configs/experiment.yaml`:

| Action Type | Energy |
| --- | ---: |
| 8-bit MAC | 0.23 pJ/action |
| SRAM byte access | 5.0 pJ/byte |
| DRAM byte access | 160.0 pJ/byte |

These values are **assignment-style ERT assumptions**. Accelergy applies them consistently to the action counts, but it does not create technology-specific SRAM or DRAM costs by itself. For this final version, the point is reproducible comparative energy modeling across the design sweep, not silicon-accurate energy prediction.

The generated Accelergy files are saved in `outputs/summary_accelergy/`:

- `accelergy_action_counts.csv`
- `accelergy_ERT.yaml`
- `accelergy_backend.yaml`

## Design Space

The sweep covers both workload parameters and hardware parameters.

| Workload Parameter | Values |
| --- | --- |
| Resolutions | 720p, 1080p, 2048 x 2048 |
| Gaussian kernels | 3x3, 5x5, 7x7, 11x11 |
| Deadlines | 33 ms, 100 ms, 200 ms |
| Primary tile size | 128 x 128 |
| Sanity tile size | 64 x 64 |

| Hardware Parameter | Values |
| --- | --- |
| Array sizes | 8x8, 16x16, 32x32, 64x64, 128x128 |
| SRAM budgets | 256 KB, 1024 KB, 4096 KB |
| Bandwidths | 50 GB/s, 200 GB/s, 800 GB/s |
| Dataflows | weight-stationary, output-stationary |
| Frequency | 1 GHz |
| Word size | 1 byte |

The summary also reports `cycles_x_pes`, which matches the class assignment style of comparing cycle count against the amount of hardware used.

## Repository Layout

```text
configs/experiment.yaml        Main experiment specification and ERT assumptions.
scripts/run_sweep.py           Runs SCALE-Sim sweeps with caching and resume support.
scripts/summarize_results.py   Aggregates raw runs and generates CSVs/plots.
scripts/smoke_test_scalesim.py Validates SCALE-Sim compatibility.
scripts/smoke_test_accelergy.py Validates Accelergy ERT/action-count accounting.
src/hpc_final/                 Reusable Python package for modeling and analysis.
outputs/summary_accelergy/     Final Accelergy-backed summary CSVs and ERT files.
figures_accelergy/             Final plots generated from Accelergy-backed summaries.
misc/                          Archived non-core artifacts and older explanation files.
```

## Setup

Create or use a Python virtual environment, then install the required packages:

```bash
.venv/bin/pip install -r requirements.txt
```

`numpy==1.26.4` is pinned because SCALE-Sim 3.0.0 has NumPy 2.x compatibility issues in this environment.

Accelergy is installed from a pinned GitHub commit in `requirements.txt`. CACTI is not required for the final pipeline.

## Running The Experiment

Validate SCALE-Sim:

```bash
.venv/bin/python scripts/smoke_test_scalesim.py
```

Validate Accelergy:

```bash
.venv/bin/python scripts/smoke_test_accelergy.py
```

Run the sanity sweep:

```bash
.venv/bin/python scripts/run_sweep.py --mode sanity
.venv/bin/python scripts/summarize_results.py --energy-backend accelergy
```

Run the full SCALE-Sim sweep:

```bash
.venv/bin/python scripts/run_sweep.py --mode full --workers 4
```

Generate final Accelergy-backed summaries and figures:

```bash
.venv/bin/python scripts/summarize_results.py \
  --config configs/experiment.yaml \
  --results outputs/raw \
  --energy-backend accelergy \
  --tile-width 128 \
  --tile-height 128 \
  --out outputs/summary_accelergy \
  --figures figures_accelergy
```

Run tests:

```bash
.venv/bin/pytest -q
```

## Generated Outputs

The final outputs are in `outputs/summary_accelergy/`.

| File | Description |
| --- | --- |
| `all_runs.csv` | Stage-level Gaussian and Sobel rows. |
| `pipeline_runs.csv` | End-to-end frame-level latency and energy. |
| `feasible_designs.csv` | Deadline-expanded feasibility table. |
| `minimum_energy_designs.csv` | Minimum-energy feasible design per scenario. |
| `pareto_frontier.csv` | Non-dominated feasible designs. |
| `bottleneck_summary.csv` | Gaussian vs. Sobel latency and energy shares. |
| `accelergy_action_counts.csv` | Component action counts passed into Accelergy. |
| `accelergy_ERT.yaml` | Table-based Accelergy Energy Reference Table. |
| `accelergy_backend.yaml` | Metadata describing the Accelergy backend and ERT values. |
| `skipped_runs.csv` | Simulator cases excluded by the resource guard. |

The final dataset contains:

| Output | Rows |
| --- | ---: |
| Stage-level rows | 3,570 |
| Complete pipeline configurations | 1,071 |
| Feasibility rows | 3,213 |
| Pareto-frontier rows | 273 |
| Minimum-energy design rows | 36 |
| Bottleneck-summary rows | 2,142 |
| Accelergy action-count rows | 24,990 |
| Skipped simulator cases | 9 |

## Results

For the main **1080p @ 33 ms** scenario, the minimum-energy feasible designs are:

| Gaussian Kernel | Best Design | SRAM | Bandwidth | Latency | Energy | EDP |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 3x3 | 32x32 output-stationary | 1024 KB | 50 GB/s | 10.07 ms | 7.26 mJ | 73.15 mJ-ms |
| 5x5 | 32x32 output-stationary | 4096 KB | 50 GB/s | 11.77 ms | 12.76 mJ | 150.22 mJ-ms |
| 7x7 | 32x32 output-stationary | 4096 KB | 50 GB/s | 14.32 ms | 21.01 mJ | 300.91 mJ-ms |
| 11x11 | 128x128 weight-stationary | 256 KB | 50 GB/s | 7.62 ms | 47.00 mJ | 357.99 mJ-ms |

The 3x3, 5x5, and 7x7 cases all meet the 33 ms deadline with a 32x32 array. The 11x11 Gaussian case is much heavier, so the minimum-energy feasible design shifts to a 128x128 weight-stationary array.

The same pattern appears across the other 33 ms scenarios:

| Resolution | Kernel | Best Design | Latency | Energy |
| --- | ---: | --- | ---: | ---: |
| 720p | 3x3 | 32x32 OS, 1024 KB, 50 GB/s | 4.48 ms | 3.23 mJ |
| 720p | 5x5 | 32x32 OS, 4096 KB, 50 GB/s | 5.23 ms | 5.67 mJ |
| 720p | 7x7 | 32x32 OS, 4096 KB, 50 GB/s | 6.37 ms | 9.34 mJ |
| 720p | 11x11 | 128x128 WS, 256 KB, 50 GB/s | 3.39 ms | 20.92 mJ |
| 2048x2048 | 3x3 | 32x32 OS, 1024 KB, 50 GB/s | 20.37 ms | 14.69 mJ |
| 2048x2048 | 5x5 | 32x32 OS, 4096 KB, 50 GB/s | 23.81 ms | 25.81 mJ |
| 2048x2048 | 7x7 | 32x32 OS, 4096 KB, 50 GB/s | 28.97 ms | 42.49 mJ |
| 2048x2048 | 11x11 | 128x128 WS, 256 KB, 50 GB/s | 15.37 ms | 94.80 mJ |

### Latency Scaling

![Latency by array size](figures_accelergy/latency_by_array.png)

Latency improves as array size increases, especially for heavier kernels. The improvement is not uniform. Smaller kernels can stop benefiting from larger arrays because their lowered GEMM shapes do not keep every processing element busy.

### Energy Scaling

![Energy by array size](figures_accelergy/energy_by_array.png)

Energy is affected by both work and hardware utilization. A larger array can reduce latency, but extra compute capacity does not automatically reduce energy. In this Accelergy ERT version, SRAM access energy is fixed per byte across all SRAM capacities, so SRAM capacity affects energy through the SCALE-Sim access counts rather than through different SRAM circuit costs.

### Utilization And Stalls

![Utilization by array size](figures_accelergy/utilization_by_array.png)

![Stall percentage by array size](figures_accelergy/stall_pct_by_array.png)

The utilization and stall plots explain why the largest array is not always the best design. A 128x128 array has more processing elements, but skinny GEMM shapes can leave many of them underused. This is why moderate arrays can be more energy-efficient for smaller kernels.

### Stage Energy Share

![Stage energy share](figures_accelergy/stage_energy_share.png)

For the 1080p @ 33 ms minimum-energy designs, the stage energy shares are:

| Gaussian Kernel | Gaussian Energy Share | Sobel Energy Share |
| --- | ---: | ---: |
| 3x3 | 47.59% | 52.41% |
| 5x5 | 70.17% | 29.83% |
| 7x7 | 81.88% | 18.12% |
| 11x11 | 90.45% | 9.55% |

The Gaussian stage becomes dominant as kernel size grows. For the 11x11 case, most of the energy is spent in Gaussian blur, so optimizing Sobel would have limited impact on total frame energy.

### Pareto Frontier

![Pareto frontier](figures_accelergy/pareto_frontier.png)

The Pareto frontier shows the latency-energy tradeoff among feasible configurations. A Pareto design is one where no other feasible design is both faster and lower energy. This matters because minimum latency and minimum energy are different objectives.

## Discussion

The main architectural result is that the best systolic array depends on the workload and deadline.

For 3x3, 5x5, and 7x7 Gaussian kernels, a 32x32 output-stationary array is enough to meet the 33 ms deadline for the tested resolutions. Moving to a larger array can reduce latency, but the extra hardware does not always reduce energy.

For the 11x11 Gaussian kernel, the computation per output pixel rises to 121 Gaussian filter values before Sobel even runs. That larger workload gives the 128x128 weight-stationary array enough work to become the minimum-energy feasible design. The dataflow shift also makes sense because the larger Gaussian filter increases weight reuse.

The deadline framing changes the design decision. A real-time embedded service only needs to finish before the next frame period. Once a design satisfies the deadline, lower energy becomes more valuable than extra speed.

The Accelergy path makes the energy calculation more structured than a single spreadsheet formula. SCALE-Sim produces per-stage action counts, the repo writes an explicit ERT, and Accelergy calculates per-component energy. The pJ/action values still come from the experiment configuration, so the results should be presented as comparative modeling results rather than measured hardware energy.

## Limitations

This experiment is scoped for a reproducible class project.

The main limitations are:

- The workload models grayscale 8-bit images only.
- The experiment evaluates accelerator performance and energy modeling, not image quality.
- Full-frame behavior is estimated from tiled simulations and analytical scaling.
- Accelergy uses a table-based ERT with configurable pJ/action assumptions.
- CACTI, Aladdin, and Timeloop are not used in the active final pipeline.
- The energy values are best interpreted as relative design comparisons.
- Leakage, wire energy, full memory-controller behavior, and host-system overhead are outside the model.
- A small number of pathological SCALE-Sim cases were skipped by a resource guard and recorded in `skipped_runs.csv`.

The skipped cases are output-stationary 11x11 Gaussian full-tile simulations on 128x128 arrays. They triggered excessive SCALE-Sim demand generation and were excluded from full pipeline summaries so partial tile results would not contaminate frame-level metrics.

## Takeaways

The final conclusions are:

- Gaussian blur plus Sobel edge detection is a tangible real-time embedded image-processing workload.
- Tiled SCALE-Sim simulation makes full-frame design exploration feasible.
- Accelergy provides reproducible component-level energy accounting from action counts and an explicit ERT.
- The best array is workload-dependent and deadline-dependent.
- For 3x3, 5x5, and 7x7 Gaussian kernels, the minimum-energy feasible 1080p @ 33 ms design is a 32x32 output-stationary array.
- For the 11x11 Gaussian kernel, the minimum-energy feasible 1080p @ 33 ms design shifts to a 128x128 weight-stationary array.
- Gaussian blur becomes the dominant energy contributor as kernel size increases.
- Minimum latency and minimum energy lead to different design choices.

In short:

> Size the accelerator to the workload and deadline. Do not simply choose the largest array.
