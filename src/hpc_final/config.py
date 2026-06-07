from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_experiment_config(path: str | Path) -> dict[str, Any]:
    """Load and lightly validate the experiment YAML."""
    config_path = Path(path).resolve()
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    required = [
        "frequency_hz",
        "word_bytes",
        "resolutions",
        "gaussian_kernels",
        "array_sizes",
        "sram_budgets_kb",
        "bandwidths_gbps",
        "dataflows",
        "tile_sizes",
        "energy",
        "scalesim",
    ]
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(f"Missing config keys: {', '.join(missing)}")

    if config["word_bytes"] <= 0:
        raise ValueError("word_bytes must be positive")
    if config["frequency_hz"] <= 0:
        raise ValueError("frequency_hz must be positive")

    config["_config_path"] = str(config_path)
    config["_config_dir"] = str(config_path.parent)
    return config


def selected_sweep_values(config: dict[str, Any], mode: str) -> dict[str, Any]:
    """Return the sweep values for sanity, full, or refinement mode."""
    if mode not in {"sanity", "full", "refinement"}:
        raise ValueError("mode must be 'sanity', 'full', or 'refinement'")

    if mode == "full":
        return {
            "resolutions": list(config["resolutions"].keys()),
            "gaussian_kernels": config["gaussian_kernels"],
            "array_sizes": config["array_sizes"],
            "sram_budgets_kb": config["sram_budgets_kb"],
            "bandwidths_gbps": config["bandwidths_gbps"],
            "dataflows": config["dataflows"],
            "tile_size": config["tile_sizes"]["full"],
        }

    if mode == "refinement":
        refinement = config.get("refinement_sweep")
        if refinement is None:
            raise ValueError("mode='refinement' requires a refinement_sweep config section")
        return {
            "resolutions": refinement.get("resolutions", list(config["resolutions"].keys())),
            "gaussian_kernels": refinement.get("gaussian_kernels", config["gaussian_kernels"]),
            "array_sizes": refinement.get("array_sizes", config["array_sizes"]),
            "sram_budgets_kb": refinement.get("sram_budgets_kb", config["sram_budgets_kb"]),
            "bandwidths_gbps": refinement.get("bandwidths_gbps", config["bandwidths_gbps"]),
            "dataflows": refinement.get("dataflows", config["dataflows"]),
            "tile_size": refinement.get(
                "tile_size",
                config["tile_sizes"].get("refinement", config["tile_sizes"]["full"]),
            ),
        }

    sanity = config.get("sanity_sweep", {})
    return {
        "resolutions": sanity.get("resolutions", [next(iter(config["resolutions"]))]),
        "gaussian_kernels": sanity.get("gaussian_kernels", config["gaussian_kernels"][:1]),
        "array_sizes": sanity.get("array_sizes", config["array_sizes"][:1]),
        "sram_budgets_kb": sanity.get("sram_budgets_kb", config["sram_budgets_kb"][:1]),
        "bandwidths_gbps": sanity.get("bandwidths_gbps", config["bandwidths_gbps"][:1]),
        "dataflows": sanity.get("dataflows", config["dataflows"][:1]),
        "tile_size": config["tile_sizes"]["sanity"],
    }
