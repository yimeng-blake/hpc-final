from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ACCELERGY_COMPONENTS = {
    "mac": "accelerator.mac_array",
    "sram_ifmap": "accelerator.ifmap_sram",
    "sram_filter": "accelerator.filter_sram",
    "sram_ofmap": "accelerator.ofmap_sram",
    "dram_ifmap": "accelerator.ifmap_dram",
    "dram_filter": "accelerator.filter_dram",
    "dram_ofmap": "accelerator.ofmap_dram",
}

COMPONENT_ACTIONS = {
    "mac": "mac",
    "sram_ifmap": "read",
    "sram_filter": "read",
    "sram_ofmap": "write",
    "dram_ifmap": "read",
    "dram_filter": "read",
    "dram_ofmap": "write",
}


def accelergy_available() -> bool:
    try:
        import accelergy  # noqa: F401
    except Exception:
        return False
    return True


def _require_accelergy() -> tuple[Any, Any, Any]:
    try:
        from accelergy.ERT_generator import ERT_dict_to_obj
        from accelergy.action_counts_dict_2_obj import action_counts_dict_2_obj
        from accelergy.energy_calculator import EnergyCalculator
    except Exception as exc:
        raise RuntimeError(
            "Accelergy is not available. Install it from "
            "https://github.com/Accelergy-Project/accelergy to use --energy-backend accelergy."
        ) from exc
    return ERT_dict_to_obj, action_counts_dict_2_obj, EnergyCalculator


def accelergy_ert_dict(
    *,
    word_bytes: int,
    mac_pj: float,
    sram_read_pj_per_byte: float,
    sram_write_pj_per_byte: float,
    dram_read_pj_per_byte: float,
    dram_write_pj_per_byte: float,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    return {
        ACCELERGY_COMPONENTS["mac"]: {
            "mac": [{"name": "mac", "arguments": {}, "energy": mac_pj}],
        },
        ACCELERGY_COMPONENTS["sram_ifmap"]: _read_write_entries(
            word_bytes * sram_read_pj_per_byte,
            word_bytes * sram_write_pj_per_byte,
        ),
        ACCELERGY_COMPONENTS["sram_filter"]: _read_write_entries(
            word_bytes * sram_read_pj_per_byte,
            word_bytes * sram_write_pj_per_byte,
        ),
        ACCELERGY_COMPONENTS["sram_ofmap"]: _read_write_entries(
            word_bytes * sram_read_pj_per_byte,
            word_bytes * sram_write_pj_per_byte,
        ),
        ACCELERGY_COMPONENTS["dram_ifmap"]: _read_write_entries(
            word_bytes * dram_read_pj_per_byte,
            word_bytes * dram_write_pj_per_byte,
        ),
        ACCELERGY_COMPONENTS["dram_filter"]: _read_write_entries(
            word_bytes * dram_read_pj_per_byte,
            word_bytes * dram_write_pj_per_byte,
        ),
        ACCELERGY_COMPONENTS["dram_ofmap"]: _read_write_entries(
            word_bytes * dram_read_pj_per_byte,
            word_bytes * dram_write_pj_per_byte,
        ),
    }


def _read_write_entries(read_energy_pj: float, write_energy_pj: float) -> dict[str, list[dict[str, Any]]]:
    return {
        "read": [{"name": "read", "arguments": {}, "energy": read_energy_pj}],
        "write": [{"name": "write", "arguments": {}, "energy": write_energy_pj}],
    }


def accelergy_action_counts_dict(
    *,
    macs: float,
    sram_ifmap_reads: float,
    sram_filter_reads: float,
    sram_ofmap_writes: float,
    dram_ifmap_reads: float,
    dram_filter_reads: float,
    dram_ofmap_writes: float,
) -> dict[str, list[dict[str, Any]]]:
    return {
        ACCELERGY_COMPONENTS["mac"]: [{"name": "mac", "counts": macs}],
        ACCELERGY_COMPONENTS["sram_ifmap"]: [{"name": "read", "counts": sram_ifmap_reads}],
        ACCELERGY_COMPONENTS["sram_filter"]: [{"name": "read", "counts": sram_filter_reads}],
        ACCELERGY_COMPONENTS["sram_ofmap"]: [{"name": "write", "counts": sram_ofmap_writes}],
        ACCELERGY_COMPONENTS["dram_ifmap"]: [{"name": "read", "counts": dram_ifmap_reads}],
        ACCELERGY_COMPONENTS["dram_filter"]: [{"name": "read", "counts": dram_filter_reads}],
        ACCELERGY_COMPONENTS["dram_ofmap"]: [{"name": "write", "counts": dram_ofmap_writes}],
    }


def accelergy_energy_breakdown_pj(
    *,
    macs: float,
    sram_ifmap_reads: float,
    sram_filter_reads: float,
    sram_ofmap_writes: float,
    dram_ifmap_reads: float,
    dram_filter_reads: float,
    dram_ofmap_writes: float,
    word_bytes: int,
    mac_pj: float,
    sram_read_pj_per_byte: float,
    sram_write_pj_per_byte: float,
    dram_read_pj_per_byte: float,
    dram_write_pj_per_byte: float,
) -> dict[str, float]:
    ERT_dict_to_obj, action_counts_dict_2_obj, EnergyCalculator = _require_accelergy()
    ert = accelergy_ert_dict(
        word_bytes=word_bytes,
        mac_pj=mac_pj,
        sram_read_pj_per_byte=sram_read_pj_per_byte,
        sram_write_pj_per_byte=sram_write_pj_per_byte,
        dram_read_pj_per_byte=dram_read_pj_per_byte,
        dram_write_pj_per_byte=dram_write_pj_per_byte,
    )
    action_counts = accelergy_action_counts_dict(
        macs=macs,
        sram_ifmap_reads=sram_ifmap_reads,
        sram_filter_reads=sram_filter_reads,
        sram_ofmap_writes=sram_ofmap_writes,
        dram_ifmap_reads=dram_ifmap_reads,
        dram_filter_reads=dram_filter_reads,
        dram_ofmap_writes=dram_ofmap_writes,
    )

    ert_obj = ERT_dict_to_obj({"ERT_dict": ert, "parser_version": 0.4, "precision": 6})
    action_counts_obj = action_counts_dict_2_obj(action_counts)
    calculator = EnergyCalculator({"action_counts": action_counts_obj, "ERT": ert_obj, "parser_version": 0.4})

    mac_energy = float(calculator.energy_estimates.get_energy_estimation(ACCELERGY_COMPONENTS["mac"]))
    sram_ifmap_energy = float(calculator.energy_estimates.get_energy_estimation(ACCELERGY_COMPONENTS["sram_ifmap"]))
    sram_filter_energy = float(calculator.energy_estimates.get_energy_estimation(ACCELERGY_COMPONENTS["sram_filter"]))
    sram_ofmap_energy = float(calculator.energy_estimates.get_energy_estimation(ACCELERGY_COMPONENTS["sram_ofmap"]))
    dram_ifmap_energy = float(calculator.energy_estimates.get_energy_estimation(ACCELERGY_COMPONENTS["dram_ifmap"]))
    dram_filter_energy = float(calculator.energy_estimates.get_energy_estimation(ACCELERGY_COMPONENTS["dram_filter"]))
    dram_ofmap_energy = float(calculator.energy_estimates.get_energy_estimation(ACCELERGY_COMPONENTS["dram_ofmap"]))
    sram_energy = sram_ifmap_energy + sram_filter_energy + sram_ofmap_energy
    dram_energy = dram_ifmap_energy + dram_filter_energy + dram_ofmap_energy
    total = float(calculator.energy_estimates.total_design_energy)

    return {
        "energy_mac_pj": mac_energy,
        "energy_sram_ifmap_pj": sram_ifmap_energy,
        "energy_sram_filter_pj": sram_filter_energy,
        "energy_sram_ofmap_pj": sram_ofmap_energy,
        "energy_sram_pj": sram_energy,
        "energy_dram_ifmap_pj": dram_ifmap_energy,
        "energy_dram_filter_pj": dram_filter_energy,
        "energy_dram_ofmap_pj": dram_ofmap_energy,
        "energy_dram_pj": dram_energy,
        "energy_total_pj": total,
        "energy_total_mj": total / 1_000_000_000,
    }


def write_accelergy_reference_files(config: dict, out_dir: str | Path) -> None:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    energy_config = config["energy"]
    sram_read = energy_config.get("sram_read_pj_per_byte", energy_config.get("sram_pj_per_byte"))
    sram_write = energy_config.get("sram_write_pj_per_byte", energy_config.get("sram_pj_per_byte"))
    dram_read = energy_config.get("dram_read_pj_per_byte", energy_config.get("dram_pj_per_byte"))
    dram_write = energy_config.get("dram_write_pj_per_byte", energy_config.get("dram_pj_per_byte"))
    ert = accelergy_ert_dict(
        word_bytes=config["word_bytes"],
        mac_pj=energy_config["mac_pj"],
        sram_read_pj_per_byte=float(sram_read),
        sram_write_pj_per_byte=float(sram_write),
        dram_read_pj_per_byte=float(dram_read),
        dram_write_pj_per_byte=float(dram_write),
    )
    payload = {
        "ERT": {
            "version": 0.4,
            "tables": [
                {
                    "name": component,
                    "actions": [
                        {
                            "name": action_name,
                            "arguments": action_info["arguments"],
                            "energy": action_info["energy"],
                        }
                        for action_name, action_entries in actions.items()
                        for action_info in action_entries
                    ],
                }
                for component, actions in ert.items()
            ],
        }
    }
    (out_path / "accelergy_backend.yaml").write_text(
        yaml.safe_dump(
            {
                "energy_backend": "accelergy",
                "source": "SCALE-Sim component action counts with Accelergy table-based ERT/action-count energy calculation",
                "word_bytes": config["word_bytes"],
                "energy_model": energy_config.get("model", "table_based_accelergy"),
                "mac_pj": energy_config["mac_pj"],
                "sram_read_pj_per_byte": float(sram_read),
                "sram_write_pj_per_byte": float(sram_write),
                "dram_read_pj_per_byte": float(dram_read),
                "dram_write_pj_per_byte": float(dram_write),
                "components": ACCELERGY_COMPONENTS,
                "component_actions": COMPONENT_ACTIONS,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (out_path / "accelergy_ERT.yaml").write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
