from __future__ import annotations

from typing import Any

GATE_NAMES = {
    "A": "Geometry",
    "B": "Selections",
    "C": "Materials",
    "D": "Physics",
    "E": "Expressions and units",
    "F": "Study and solver sequence",
    "G": "Mesh",
    "H": "DOF and computational budget",
}


def evaluate_pre_solve_gates(required: list[str], evidence: dict[str, Any]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    overall = "PASS"
    for gate in required:
        if gate not in GATE_NAMES:
            results[gate] = {"status": "BLOCKED", "reason": "Unknown gate identifier"}
            overall = "BLOCKED"
            continue
        item = evidence.get(gate)
        if not isinstance(item, dict):
            results[gate] = {
                "name": GATE_NAMES[gate],
                "status": "BLOCKED",
                "reason": "No evidence supplied; missing evidence is not a pass"
            }
            overall = "BLOCKED"
            continue
        checks = item.get("checks")
        if not isinstance(checks, list) or not checks:
            results[gate] = {
                "name": GATE_NAMES[gate],
                "status": "BLOCKED",
                "reason": "Gate requires one or more explicit checks"
            }
            overall = "BLOCKED"
            continue
        failed = [check for check in checks if not isinstance(check, dict) or check.get("passed") is not True]
        approval = bool(item.get("requires_approval"))
        status = "REQUIRES_APPROVAL" if approval and not failed else ("BLOCKED" if failed else "PASS")
        results[gate] = {
            "name": GATE_NAMES[gate],
            "status": status,
            "checks": checks,
            "failed_check_count": len(failed)
        }
        if status == "BLOCKED":
            overall = "BLOCKED"
        elif status == "REQUIRES_APPROVAL" and overall == "PASS":
            overall = "REQUIRES_APPROVAL"
    return {"status": overall, "gates": results, "solve_allowed": overall == "PASS"}


def require_solve_permission(gate_report: dict[str, Any]) -> None:
    if gate_report.get("solve_allowed") is not True or gate_report.get("status") != "PASS":
        raise RuntimeError("Pre-Solve Dry-Run Gate did not pass; COMSOL solve is blocked")
