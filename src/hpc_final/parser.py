from __future__ import annotations

from pathlib import Path

import pandas as pd


def _normalize_column(name: str) -> str:
    normalized = name.strip().rstrip(",").lower()
    replacements = {
        "%": "pct",
        "(": "",
        ")": "",
        ".": "",
        "/": "_",
    }
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    normalized = normalized.replace("incl.", "incl")
    return "_".join(normalized.split())


def _read_report(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path, skipinitialspace=True)
    df.columns = [_normalize_column(col) for col in df.columns]
    return df.dropna(axis=1, how="all")


def reports_exist(report_dir: Path) -> bool:
    return all((report_dir / name).exists() for name in REPORT_FILES)


REPORT_FILES = ("COMPUTE_REPORT.csv", "BANDWIDTH_REPORT.csv", "DETAILED_ACCESS_REPORT.csv")


def parse_reports(report_dir: Path, stage_names: list[str]) -> list[dict]:
    compute = _read_report(report_dir / "COMPUTE_REPORT.csv")
    bandwidth = _read_report(report_dir / "BANDWIDTH_REPORT.csv")
    detail = _read_report(report_dir / "DETAILED_ACCESS_REPORT.csv")

    records: list[dict] = []
    for idx, stage_name in enumerate(stage_names):
        c = compute.iloc[idx].to_dict()
        b = bandwidth.iloc[idx].to_dict()
        d = detail.iloc[idx].to_dict()
        record = {"stage": stage_name, "stage_index": idx}
        record.update({f"compute_{key}": value for key, value in c.items()})
        record.update({f"bandwidth_{key}": value for key, value in b.items()})
        record.update({f"detail_{key}": value for key, value in d.items()})
        records.append(record)
    return records
