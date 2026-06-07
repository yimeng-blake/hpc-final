# Deadline-Constrained Systolic Array Design for Image Processing

This project evaluates systolic-array accelerator configurations for a grayscale image-processing pipeline:

```text
input frame -> Gaussian blur -> Sobel edge detection -> edge frame
```

The goal is to find the minimum-energy design that completes a full frame before a real-time deadline. The main case used in the report is 1080p at 30 FPS, or about 33 ms per frame.

## Package Contents

Submit these directories/files with the project package:

```text
README.md                         Setup and reproduction instructions.
FINAL_REPORT.tex                  Final report source.
FINAL_REPORT.docx                 Optional formatted report copy.
configs/experiment.yaml           Experiment configuration.
scripts/                          Experiment, summarization, and smoke-test scripts.
src/hpc_final/                    Reusable modeling and analysis code.
tests/                            Unit tests for the framework.
outputs/raw/                      Raw SCALE-Sim run outputs used to build the summaries.
outputs/summary_accelergy_plugin/ Final summary CSVs and Accelergy generated outputs.
figures_accelergy_plugin/         Figures generated from the final summary data.
```

Do not include local environment or cache directories such as `.venv/`, `build/`, `.pytest_cache/`, or `__pycache__/`.

## Setup

Create or use a Python virtual environment, then install dependencies:

```bash
.venv/bin/pip install -r requirements.txt
```

`numpy==1.26.4` is pinned because SCALE-Sim 3.0.0 has NumPy 2.x compatibility issues in this environment.

The final energy path uses Accelergy through the component-library/table-plug-in backend. If Accelergy or the SCALE-Sim-Accelergy component YAML directory is not auto-detected on another machine, set the paths in `configs/experiment.yaml`:

```yaml
energy:
  accelergy_plugin:
    accelergy_bin: ../hpc-assignment-2/.venv/bin/accelergy
    component_dir: ../hpc-assignment-1/deps/SCALE-Sim-Accelergy/rundir-accelergy/accelergy_input/components
```

## Reproducing Results

Run the smoke tests first:

```bash
.venv/bin/python scripts/smoke_test_scalesim.py
.venv/bin/python scripts/smoke_test_accelergy.py
```

Run the full experiment sweep:

```bash
.venv/bin/python scripts/run_sweep.py --mode full --workers 4
```

Run the focused 1080p refinement sweep:

```bash
.venv/bin/python scripts/run_sweep.py --mode refinement --workers 4
```

Regenerate the final summary CSVs and figures:

```bash
.venv/bin/python scripts/summarize_results.py \
  --config configs/experiment.yaml \
  --results outputs/raw \
  --energy-backend accelergy_plugin \
  --tile-width 128 \
  --tile-height 128 \
  --out outputs/summary_accelergy_plugin \
  --figures figures_accelergy_plugin
```

Run the unit tests:

```bash
.venv/bin/pytest -q
```

## Output Locations

Raw simulator outputs are stored in `outputs/raw/`.

Final summarized data is stored in `outputs/summary_accelergy_plugin/`:

```text
all_runs.csv
pipeline_runs.csv
feasible_designs.csv
minimum_energy_designs.csv
pareto_frontier.csv
bottleneck_summary.csv
accelergy_action_counts.csv
accelergy_backend.yaml
skipped_runs.csv
rerun_skipped_log.csv
accelergy_plugin/*/outputs/ERT.yaml
accelergy_plugin/*/outputs/energy_estimation.yaml
```

Final figures are stored in `figures_accelergy_plugin/`. The report appendix uses:

```text
energy_latency_scatter.png
stage_share_by_kernel.png
component_energy_split.png
```

## Notes

The modeled application includes only the accelerator compute stages, Gaussian blur and Sobel edge detection. Camera capture, display, CPU orchestration, static/leakage power, and full-system idle power are outside the model.

Some SCALE-Sim cases are skipped by resource guards and recorded in `outputs/summary_accelergy_plugin/skipped_runs.csv`. Skipped partial results are excluded from full-pipeline summaries.

The report source is `FINAL_REPORT.tex`. Compile it with a local TeX installation if a PDF is required:

```bash
latexmk -pdf FINAL_REPORT.tex
```
