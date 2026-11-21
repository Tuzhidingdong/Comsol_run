from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io_utils import atomic_write_json, atomic_write_text


def build_execution_report(
    *,
    task_id: str,
    job_id: str,
    output_dir: str | Path,
    api_success: bool,
    numerical_success: bool,
    physical_validation: bool | None,
    reproduction_success: bool | None,
    status: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "task_id": task_id,
        "job_id": job_id,
        "status": status,
        "api_success": bool(api_success),
        "numerical_success": bool(numerical_success),
        "physical_validation": physical_validation,
        "reproduction_success": reproduction_success,
        "output_dir": str(Path(output_dir).resolve()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "evidence": evidence or {}
    }


def write_report(output_dir: str | Path, report: dict[str, Any]) -> None:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out / "execution_report.json", report)
    evidence = report.get("evidence", {})
    lines = [
        "# COMSOL execution report",
        "",
        f"- Task ID: {report.get('task_id')}",
        f"- Job ID: {report.get('job_id')}",
        f"- Status: {report.get('status')}",
        f"- Output: {report.get('output_dir')}",
        f"- API success: {report.get('api_success')}",
        f"- Numerical success: {report.get('numerical_success')}",
        f"- Physical validation: {report.get('physical_validation')}",
        f"- Reproduction success: {report.get('reproduction_success')}",
        f"- Created: {report.get('created_at')}",
        "",
        "## Evidence",
        "",
        __import__("json").dumps(evidence, indent=2, ensure_ascii=False, default=str),
        ""
    ]
    atomic_write_text(out / "verification_report.md", "\n".join(lines))
