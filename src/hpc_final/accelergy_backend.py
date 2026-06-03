from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml


ACCELERGY_PLUGIN_MODEL = "accelergy_component_library_table_plugin"

BRANCH_COMPONENTS = {
    "mac": "systolic_array.PE[{pe_range}].mac",
    "sram_ifmap": "systolic_array.ifmap_glb",
    "sram_filter": "systolic_array.weights_glb",
    "sram_ofmap": "systolic_array.psum_glb",
    "dram_ifmap": "systolic_array.ifmap_dram",
    "dram_filter": "systolic_array.weights_dram",
    "dram_ofmap": "systolic_array.psum_dram",
}

BRANCH_COMPONENT_ACTIONS = {
    "mac": "mac_random",
    "sram_ifmap": "read",
    "sram_filter": "read",
    "sram_ofmap": "update",
    "dram_ifmap": "read",
    "dram_filter": "read",
    "dram_ofmap": "write",
}


def _repo_root(config: dict) -> Path:
    config_dir = config.get("_config_dir")
    if config_dir:
        return Path(config_dir).resolve().parent
    return Path.cwd()


def _resolve_path(value: str | None, root: Path) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _table_templates_root(accelergy_bin: Path) -> Path:
    return (
        accelergy_bin.parent.parent
        / "share"
        / "accelergy"
        / "estimation_plug_ins"
        / "accelergy-table-based-plug-ins"
        / "set_of_table_templates"
    )


def _primitive_components_root(accelergy_bin: Path) -> Path:
    return accelergy_bin.parent.parent / "share" / "accelergy" / "primitive_component_libs"


def _estimation_plugins_root(accelergy_bin: Path) -> Path:
    return accelergy_bin.parent.parent / "share" / "accelergy" / "estimation_plug_ins"


def _has_branch_table_plugin(accelergy_bin: Path) -> bool:
    return (
        accelergy_bin.exists()
        and _table_templates_root(accelergy_bin).exists()
        and _primitive_components_root(accelergy_bin).exists()
    )


def _default_accelergy_bin(root: Path) -> Path:
    candidates = [
        root.parent / "hpc-assignment-2" / ".venv" / "bin" / "accelergy",
        root.parent / "hpc-assignment-1" / ".venv" / "bin" / "accelergy",
        root / ".venv" / "bin" / "accelergy",
    ]
    which = shutil.which("accelergy")
    if which:
        candidates.append(Path(which))
    for candidate in candidates:
        if _has_branch_table_plugin(candidate):
            return candidate.resolve()
    raise FileNotFoundError(
        "No Accelergy install with accelergy-table-based-plug-ins/set_of_table_templates was found. "
        "Set energy.accelergy_plugin.accelergy_bin in the config."
    )


def _default_component_dir(root: Path) -> Path:
    candidates = [
        root.parent
        / "hpc-assignment-1"
        / "deps"
        / "SCALE-Sim-Accelergy"
        / "rundir-accelergy"
        / "accelergy_input"
        / "components",
        root / "deps" / "SCALE-Sim-Accelergy" / "rundir-accelergy" / "accelergy_input" / "components",
    ]
    for candidate in candidates:
        if candidate.exists() and list(candidate.glob("*.yaml")):
            return candidate.resolve()
    raise FileNotFoundError(
        "No SCALE-Sim-Accelergy component YAML directory was found. "
        "Set energy.accelergy_plugin.component_dir in the config."
    )


def _accelergy_plugin_config(config: dict) -> dict[str, Any]:
    energy_config = config.get("energy", {})
    return energy_config.get("accelergy_plugin", {})


def _accelergy_bin(config: dict) -> Path:
    root = _repo_root(config)
    configured = _resolve_path(_accelergy_plugin_config(config).get("accelergy_bin"), root)
    if configured:
        if not _has_branch_table_plugin(configured):
            raise FileNotFoundError(f"Configured Accelergy binary lacks required table plug-ins: {configured}")
        return configured
    return _default_accelergy_bin(root)


def _component_dir(config: dict) -> Path:
    root = _repo_root(config)
    configured = _resolve_path(_accelergy_plugin_config(config).get("component_dir"), root)
    if configured:
        if not configured.exists():
            raise FileNotFoundError(f"Configured Accelergy component directory does not exist: {configured}")
        return configured
    return _default_component_dir(root)


def _split_sram_budget(total_kb: int, config: dict) -> tuple[int, int, int]:
    scalesim_config = config["scalesim"]
    fractions = [
        float(scalesim_config["ifmap_sram_fraction"]),
        float(scalesim_config["filter_sram_fraction"]),
        float(scalesim_config["ofmap_sram_fraction"]),
    ]
    total_fraction = sum(fractions)
    raw = [total_kb * fraction / total_fraction for fraction in fractions]
    rounded = [max(1, int(round(value))) for value in raw]
    delta = total_kb - sum(rounded)
    rounded[-1] += delta
    if rounded[-1] <= 0:
        rounded[-1] = 1
    return tuple(rounded)  # type: ignore[return-value]


def _bank_depth_entries(size_kb: int, memory_width_bits: int) -> int:
    bits = max(1, size_kb) * 1024 * 8
    return max(1, int(round(bits / max(1, memory_width_bits))))


def _plugin_architecture(
    *,
    config: dict,
    array_size: int,
    sram_budget_kb: int,
    word_bytes: int,
) -> dict[str, Any]:
    plugin_config = _accelergy_plugin_config(config)
    technology = plugin_config.get("technology", "40nm")
    memory_width_bits = int(plugin_config.get("memory_width_bits", max(1, word_bytes) * 8))
    dram_width_bits = int(plugin_config.get("dram_width_bits", memory_width_bits))
    mac_datawidth = int(plugin_config.get("mac_datawidth", max(1, word_bytes) * 8))
    pe_memory_width = int(plugin_config.get("pe_memory_width", max(16, memory_width_bits)))
    ifmap_kb, filter_kb, ofmap_kb = _split_sram_budget(sram_budget_kb, config)

    def glb(name: str, size_kb: int) -> dict[str, Any]:
        return {
            "name": name,
            "class": "smartbuffer_SRAM",
            "attributes": {
                "memory_width": memory_width_bits,
                "n_banks": 1,
                "bank_depth": _bank_depth_entries(size_kb, memory_width_bits),
                "memory_depth": "bank_depth * n_banks",
                "n_buffets": 1,
            },
        }

    def dram(name: str) -> dict[str, Any]:
        return {"name": name, "class": "DRAM", "attributes": {"width": dram_width_bits}}

    pe_count = array_size * array_size
    pe = {
        "name": f"PE[0..{pe_count - 1}]",
        "attributes": {"memory_width": pe_memory_width},
        "local": [
            {"name": "mac", "class": "intmac", "attributes": {"datawidth": mac_datawidth}},
            {"name": "ifmap_spad", "class": "regfile", "attributes": {"depth": 1, "n_rdwr_ports": 1, "width": 1}},
            {"name": "weights_spad", "class": "regfile", "attributes": {"depth": 1, "n_rdwr_ports": 1, "width": 1}},
            {"name": "psum_spad", "class": "regfile", "attributes": {"depth": 1, "n_rdwr_ports": 1, "width": 1}},
        ],
    }
    return {
        "architecture": {
            "version": 0.3,
            "subtree": [
                {
                    "name": "systolic_array",
                    "attributes": {"technology": technology},
                    "local": [
                        glb("weights_glb", filter_kb),
                        glb("ifmap_glb", ifmap_kb),
                        glb("psum_glb", ofmap_kb),
                        dram("weights_dram"),
                        dram("ifmap_dram"),
                        dram("psum_dram"),
                    ],
                    "subtree": [pe],
                }
            ],
        }
    }


def _plugin_probe_action_counts(array_size: int) -> dict[str, Any]:
    pe_range = f"0..{array_size * array_size - 1}"

    def sram_action(component: str, action: str) -> dict[str, Any]:
        return {
            "name": component,
            "action_counts": [
                {
                    "name": action,
                    "arguments": {"address_delta": 1, "data_delta": 1},
                    "counts": 1,
                }
            ],
        }

    def simple_action(component: str, action: str) -> dict[str, Any]:
        return {"name": component, "action_counts": [{"name": action, "counts": 1}]}

    return {
        "action_counts": {
            "version": 0.3,
            "local": [
                simple_action(BRANCH_COMPONENTS["mac"].format(pe_range=pe_range), BRANCH_COMPONENT_ACTIONS["mac"]),
                sram_action(BRANCH_COMPONENTS["sram_ifmap"], BRANCH_COMPONENT_ACTIONS["sram_ifmap"]),
                sram_action(BRANCH_COMPONENTS["sram_filter"], BRANCH_COMPONENT_ACTIONS["sram_filter"]),
                sram_action(BRANCH_COMPONENTS["sram_ofmap"], BRANCH_COMPONENT_ACTIONS["sram_ofmap"]),
                simple_action(BRANCH_COMPONENTS["dram_ifmap"], BRANCH_COMPONENT_ACTIONS["dram_ifmap"]),
                simple_action(BRANCH_COMPONENTS["dram_filter"], BRANCH_COMPONENT_ACTIONS["dram_filter"]),
                simple_action(BRANCH_COMPONENTS["dram_ofmap"], BRANCH_COMPONENT_ACTIONS["dram_ofmap"]),
            ],
        }
    }


def _write_accelergy_cli_config(accelergy_bin: Path, accelergy_home: Path) -> None:
    config_path = accelergy_home / ".config" / "accelergy" / "accelergy_config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 0.3,
        "estimator_plug_ins": [str(_estimation_plugins_root(accelergy_bin))],
        "primitive_components": [str(_primitive_components_root(accelergy_bin))],
        "table_plug_ins": {"roots": [str(_table_templates_root(accelergy_bin))]},
    }
    config_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _run_accelergy_plugin(
    *,
    config: dict,
    architecture_path: Path,
    action_count_path: Path,
    output_dir: Path,
    accelergy_home: Path,
) -> None:
    accelergy_bin = _accelergy_bin(config)
    component_files = sorted(_component_dir(config).glob("*.yaml"))
    if not component_files:
        raise FileNotFoundError(f"No Accelergy component YAML files found in {_component_dir(config)}")

    _write_accelergy_cli_config(accelergy_bin, accelergy_home)
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        str(accelergy_bin),
        str(architecture_path),
        str(action_count_path),
        *[str(path) for path in component_files],
        "-o",
        str(output_dir),
        "-f",
        "ERT",
        "energy_estimation",
    ]
    env = os.environ.copy()
    env["HOME"] = str(accelergy_home)
    env["PATH"] = str(accelergy_bin.parent) + os.pathsep + env.get("PATH", "")
    log_path = output_dir / "accelergy.log"
    with log_path.open("w", encoding="utf-8") as log:
        completed = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
    if completed.returncode != 0 or not (output_dir / "energy_estimation.yaml").exists():
        tail = log_path.read_text(errors="ignore")[-4000:] if log_path.exists() else ""
        raise RuntimeError(f"Accelergy table plug-in run failed. See {log_path}\n{tail}")


def _component_energy(energy_path: Path, component_name: str) -> float:
    data = yaml.safe_load(energy_path.read_text(encoding="utf-8"))
    for component in data.get("energy_estimation", {}).get("components", []):
        if component.get("name") == component_name:
            return float(component["energy"])
    raise KeyError(f"Component {component_name} not found in {energy_path}")


def generate_accelergy_plugin_energy_params(
    config: dict,
    out_dir: str | Path,
    *,
    array_size: int,
    sram_budget_kb: int,
    word_bytes: int,
) -> dict[str, float | str]:
    out_path = Path(out_dir)
    run_dir = out_path / "accelergy_plugin" / f"array_{array_size}_sram_{sram_budget_kb}_word_{word_bytes}"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    input_dir = run_dir / "inputs"
    output_dir = run_dir / "outputs"
    accelergy_home = run_dir / "home"
    input_dir.mkdir(parents=True, exist_ok=True)
    architecture_path = input_dir / "architecture.yaml"
    action_count_path = input_dir / "action_count.yaml"
    architecture_path.write_text(
        yaml.safe_dump(
            _plugin_architecture(
                config=config,
                array_size=array_size,
                sram_budget_kb=sram_budget_kb,
                word_bytes=word_bytes,
            ),
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    action_count_path.write_text(
        yaml.safe_dump(_plugin_probe_action_counts(array_size), sort_keys=False),
        encoding="utf-8",
    )
    _run_accelergy_plugin(
        config=config,
        architecture_path=architecture_path,
        action_count_path=action_count_path,
        output_dir=output_dir,
        accelergy_home=accelergy_home,
    )

    pe_range = f"0..{array_size * array_size - 1}"
    energy_path = output_dir / "energy_estimation.yaml"
    mac_pj = _component_energy(energy_path, BRANCH_COMPONENTS["mac"].format(pe_range=pe_range))
    sram_ifmap = _component_energy(energy_path, BRANCH_COMPONENTS["sram_ifmap"])
    sram_filter = _component_energy(energy_path, BRANCH_COMPONENTS["sram_filter"])
    sram_ofmap = _component_energy(energy_path, BRANCH_COMPONENTS["sram_ofmap"])
    dram_ifmap = _component_energy(energy_path, BRANCH_COMPONENTS["dram_ifmap"])
    dram_filter = _component_energy(energy_path, BRANCH_COMPONENTS["dram_filter"])
    dram_ofmap = _component_energy(energy_path, BRANCH_COMPONENTS["dram_ofmap"])
    byte_scale = max(1, word_bytes)
    return {
        "energy_model": ACCELERGY_PLUGIN_MODEL,
        "mac_pj": mac_pj,
        "sram_read_pj_per_byte": sram_ifmap / byte_scale,
        "sram_write_pj_per_byte": sram_ofmap / byte_scale,
        "dram_read_pj_per_byte": dram_ifmap / byte_scale,
        "dram_write_pj_per_byte": dram_ofmap / byte_scale,
        "sram_ifmap_read_pj_per_action": sram_ifmap,
        "sram_filter_read_pj_per_action": sram_filter,
        "sram_ofmap_write_pj_per_action": sram_ofmap,
        "dram_ifmap_read_pj_per_action": dram_ifmap,
        "dram_filter_read_pj_per_action": dram_filter,
        "dram_ofmap_write_pj_per_action": dram_ofmap,
        "accelergy_architecture": str(architecture_path),
        "accelergy_action_count": str(action_count_path),
        "accelergy_output_dir": str(output_dir),
        "accelergy_ert": str(output_dir / "ERT.yaml"),
    }


def write_accelergy_plugin_backend_summary(
    config: dict,
    out_dir: str | Path,
    generated_params: list[dict[str, float | str]],
) -> None:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    accelergy_bin = _accelergy_bin(config)
    component_dir = _component_dir(config)
    payload = {
        "energy_backend": "accelergy_plugin",
        "source": "Accelergy CLI with SCALE-Sim-Accelergy component library and table plug-ins",
        "energy_model": ACCELERGY_PLUGIN_MODEL,
        "accelergy_bin": str(accelergy_bin),
        "component_dir": str(component_dir),
        "generated_erts": [
            {
                "architecture": item["accelergy_architecture"],
                "action_count": item["accelergy_action_count"],
                "ert": item["accelergy_ert"],
                "output_dir": item["accelergy_output_dir"],
                "mac_pj": item["mac_pj"],
                "sram_ifmap_read_pj_per_action": item["sram_ifmap_read_pj_per_action"],
                "sram_filter_read_pj_per_action": item["sram_filter_read_pj_per_action"],
                "sram_ofmap_write_pj_per_action": item["sram_ofmap_write_pj_per_action"],
                "dram_ifmap_read_pj_per_action": item["dram_ifmap_read_pj_per_action"],
                "dram_filter_read_pj_per_action": item["dram_filter_read_pj_per_action"],
                "dram_ofmap_write_pj_per_action": item["dram_ofmap_write_pj_per_action"],
            }
            for item in generated_params
        ],
    }
    (out_path / "accelergy_backend.yaml").write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
