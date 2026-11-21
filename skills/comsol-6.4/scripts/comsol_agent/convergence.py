from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any

from .io_utils import atomic_write_json, canonical_json_sha256, safe_task_id


class ConvergenceError(ValueError):
    pass


def derive_child_manifests(parent: dict[str, Any], kind: str, levels: list[float]) -> list[dict[str, Any]]:
    if kind not in {"mesh", "time"}:
        raise ConvergenceError("kind must be mesh or time")
    if len(levels) < 2:
        raise ConvergenceError("At least two levels are required; three are recommended for formal GCI")
    if any(not math.isfinite(float(level)) or float(level) <= 0 for level in levels):
        raise ConvergenceError("All refinement levels must be finite positive numbers")
    base = copy.deepcopy(parent)
    if base["metadata"]["mode"] != "build":
        raise ConvergenceError("Convergence child derivation currently requires build mode")
    parent_id = safe_task_id(base["metadata"]["task_id"])
    frozen_sha = canonical_json_sha256(base)
    children = []
    for index, level in enumerate(levels, start=1):
        child = copy.deepcopy(base)
        variant = f"{kind}_L{index}"
        child_id = safe_task_id(f"{parent_id}.{variant}")
        child["metadata"]["task_id"] = child_id
        child["metadata"]["parent_task_id"] = parent_id
        child["metadata"]["variant_id"] = variant
        child["metadata"]["base_manifest_sha256"] = frozen_sha
        if kind == "mesh":
            child["mesh"]["refinement_factor"] = float(level)
        else:
            child["study"]["time_step_scale"] = float(level)
        children.append(child)
    return children


def write_convergence_plan(parent: dict[str, Any], kind: str, levels: list[float], output_dir: str | Path) -> Path:
    out = Path(output_dir).expanduser().resolve()
    if out.exists() and any(out.iterdir()):
        raise ConvergenceError(f"Refusing to overwrite a non-empty convergence plan directory: {out}")
    out.mkdir(parents=True, exist_ok=True)
    children = derive_child_manifests(parent, kind, levels)
    atomic_write_json(out / "parent_manifest.json", parent)
    records = []
    for child in children:
        child_dir = out / child["metadata"]["task_id"]
        child_dir.mkdir()
        manifest_path = child_dir / "manifest.json"
        atomic_write_json(manifest_path, child)
        records.append({
            "task_id": child["metadata"]["task_id"],
            "variant_id": child["metadata"]["variant_id"],
            "manifest": str(manifest_path.resolve()),
            "output_root": str((child_dir / "run").resolve()),
            "output_dir": None,
            "status": "PENDING",
            "refinement_value": child["mesh"]["refinement_factor"] if kind == "mesh" else child["study"]["time_step_scale"]
        })
    atomic_write_json(out / "child_tasks.json", {
        "parent_task_id": parent["metadata"]["task_id"],
        "kind": kind,
        "base_manifest_sha256": canonical_json_sha256(parent),
        "children": records
    })
    return out


def compute_gci(
    values: list[float],
    characteristic_sizes: list[float],
    *,
    safety_factor: float = 1.25,
    ratio_tolerance: float = 0.05
) -> dict[str, Any]:
    if len(values) != 3 or len(characteristic_sizes) != 3:
        raise ConvergenceError("GCI calculation requires exactly three mesh levels")
    phi1, phi2, phi3 = [float(value) for value in values]
    h1, h2, h3 = [float(value) for value in characteristic_sizes]
    if any(not math.isfinite(value) for value in [phi1, phi2, phi3, h1, h2, h3]):
        raise ConvergenceError("GCI inputs must be finite")
    if not (h1 > h2 > h3 > 0):
        raise ConvergenceError("Characteristic mesh sizes must be ordered coarse > medium > fine > 0")
    r21, r32 = h1 / h2, h2 / h3
    if abs(r21 - r32) / max(r21, r32) > ratio_tolerance:
        raise ConvergenceError("This observed-order implementation requires approximately equal refinement ratios")
    e21, e32 = phi1 - phi2, phi2 - phi3
    if e21 == 0 or e32 == 0 or e21 * e32 <= 0:
        raise ConvergenceError("Results are not monotonically convergent; simple GCI is not applicable")
    p = math.log(abs(e21 / e32)) / math.log(r21)
    if not math.isfinite(p) or p <= 0:
        raise ConvergenceError(f"Observed order is not positive: {p}")
    denom = r21 ** p - 1.0
    if denom <= 0 or phi2 == 0 or phi3 == 0:
        raise ConvergenceError("GCI denominator or normalization is invalid")
    gci21 = safety_factor * abs(e21 / phi2) / denom * 100.0
    gci32 = safety_factor * abs(e32 / phi3) / denom * 100.0
    asymptotic_ratio = gci21 / (gci32 * (r21 ** p)) if gci32 else None
    return {
        "status": "CALCULATED",
        "observed_order": p,
        "refinement_ratio_21": r21,
        "refinement_ratio_32": r32,
        "gci_medium_percent": gci21,
        "gci_fine_percent": gci32,
        "asymptotic_range_ratio": asymptotic_ratio,
        "safety_factor": safety_factor,
        "assumptions": [
            "three systematically refined meshes",
            "monotonic convergence",
            "approximately equal refinement ratios",
            "same physical model and comparable target observable"
        ]
    }


def aggregate_scalar_metrics(parent_dir: str | Path, metric_name: str) -> dict[str, Any]:
    root = Path(parent_dir).expanduser().resolve()
    plan_path = root / "child_tasks.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    records = []
    for child in plan["children"]:
        output_dir = child.get("output_dir")
        if not output_dir:
            records.append({
                "task_id": child["task_id"], "status": child.get("status", "PENDING"),
                "refinement_value": child.get("refinement_value")
            })
            continue
        child_out = Path(output_dir)
        metrics_path = child_out / "metrics.json"
        status_path = child_out / "worker_result.json"
        if not status_path.is_file() or not metrics_path.is_file():
            records.append({
                "task_id": child["task_id"], "status": "MISSING_ARTIFACT",
                "refinement_value": child.get("refinement_value")
            })
            continue
        status = json.loads(status_path.read_text(encoding="utf-8")).get("status")
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        value = metrics.get("target_values", {}).get(metric_name)
        records.append({
            "task_id": child["task_id"], "status": status, "value": value,
            "refinement_value": child.get("refinement_value"), "output_dir": str(child_out)
        })
    acceptable_statuses = {"NUMERICAL_SUCCESS_VALIDATION_PENDING", "NUMERICAL_SUCCESS_REPRODUCTION_CHECKED"}
    complete = all(item.get("status") in acceptable_statuses and isinstance(item.get("value"), (int, float)) for item in records)
    result: dict[str, Any] = {
        "parent_task_id": plan["parent_task_id"],
        "kind": plan["kind"],
        "metric_name": metric_name,
        "status": "READY_FOR_CONVERGENCE_ANALYSIS" if complete else "INCOMPLETE",
        "children": records
    }
    if complete and plan["kind"] == "mesh" and len(records) == 3:
        try:
            result["gci"] = compute_gci(
                [float(item["value"]) for item in records],
                [float(item["refinement_value"]) for item in records]
            )
        except (ConvergenceError, KeyError, TypeError, ValueError) as exc:
            result["gci"] = {"status": "NOT_APPLICABLE", "reason": str(exc)}
    elif complete and plan["kind"] == "time":
        values = [float(item["value"]) for item in records]
        reference = values[-1]
        result["time_step_sensitivity"] = {
            "coarse_to_fine_relative_changes": [
                abs(value - reference) / max(abs(reference), 1e-30)
                for value in values[:-1]
            ],
            "note": "Interpret using the declared time-step refinement order and task-specific tolerance."
        }
    atomic_write_json(root / "aggregation_report.json", result)
    return result
