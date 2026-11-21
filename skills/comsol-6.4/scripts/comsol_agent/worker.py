from __future__ import annotations

import argparse
import json
import time
import traceback
from pathlib import Path
from typing import Any

from .comsol import ComsolSession, environment_report
from .gates import evaluate_pre_solve_gates, require_solve_permission
from .io_utils import atomic_write_json
from .manifest import load_and_validate
from .executor import ProfileExecutor
from .report import build_execution_report, write_report


def run_m0(output_dir: Path) -> dict[str, Any]:
    out = output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    env = environment_report()
    atomic_write_json(out / "environment_report.json", env)
    if env["system"] != "Windows" or env["python_bits"] != 64:
        raise RuntimeError("M0 requires Windows 64-bit and a 64-bit Python interpreter")
    if not env.get("comsol_server_executable"):
        raise RuntimeError(env.get("comsol_discovery_error", "COMSOL Server executable was not discovered"))
    if not env.get("mph_version"):
        raise RuntimeError("MPh is not installed")
    session = ComsolSession(cores=1, version="6.4", startup_timeout=120)
    process = None
    smoke = None
    cleanup = {}
    started = time.time()
    try:
        session.start()
        process = session.server.process
        smoke = session.smoke_test(out)
    finally:
        cleanup = session.close()
    process_exited = process is None or process.poll() is not None
    evidence = {
        "environment": env,
        "smoke_test": smoke,
        "cleanup": cleanup,
        "server_process_exited": process_exited,
        "elapsed_seconds": round(time.time() - started, 3),
        "server_process_pid": smoke.get("server_pid") if smoke else None
    }
    if not process_exited:
        raise RuntimeError("COMSOL Server process remains active after session cleanup")
    return evidence


def run_manifest(manifest_path: Path, output_dir: Path) -> dict[str, Any]:
    manifest, validation = load_and_validate(manifest_path)
    if manifest["metadata"]["mode"] != "build":
        raise RuntimeError("Patch mode is not enabled in this implementation")
    session = ComsolSession(
        cores=int(manifest["metadata"].get("execution_limits", {}).get("cores", 1)),
        version="6.4",
        startup_timeout=120
    )
    started = time.time()
    try:
        session.start()
        executor = ProfileExecutor(session.client, manifest, output_dir)
        build = executor.run()
        live_evidence = executor.collect_live_gate_evidence()
        gate_report = evaluate_pre_solve_gates(manifest["validation"]["required_gates"], live_evidence)
        atomic_write_json(output_dir / "pre_solve_gate_report.json", gate_report)

        numerical_success = False
        physical_validation = None
        reproduction_success = None
        output_evidence = None
        benchmark = None
        solved_model_path = None
        status = "BUILD_ONLY_PRE_SOLVE_GATES_REPORTED"

        if manifest["study"].get("run", False):
            require_solve_permission(gate_report)
            executor.execute_study()
            numerical_success = True
            output_evidence = executor.extract_outputs()
            benchmark = executor.compare_benchmark(output_evidence["results"])
            if benchmark is not None:
                atomic_write_json(output_dir / "benchmark_report.json", benchmark)
                reproduction_success = bool(benchmark["passed"])
            solved_model_path = (output_dir / "solved_model.mph").resolve()
            if solved_model_path.exists():
                raise RuntimeError(f"Refusing to overwrite solved model: {solved_model_path}")
            executor.model.save(str(solved_model_path))
            if not solved_model_path.is_file() or solved_model_path.stat().st_size == 0:
                raise RuntimeError("Solved MPH model was not saved correctly")
            target_values = {
                name: item["value"]
                for name, item in (output_evidence.get("results") or {}).items()
                if isinstance(item.get("value"), (int, float)) and not isinstance(item.get("value"), bool)
            }
            atomic_write_json(output_dir / "metrics.json", {"target_values": target_values})
            status = "NUMERICAL_SUCCESS_REPRODUCTION_CHECKED" if benchmark is not None else "NUMERICAL_SUCCESS_VALIDATION_PENDING"

        evidence = {
            "manifest_validation": validation,
            "profile_id": manifest["metadata"]["profile_id"],
            "completed_actions": build["completed_actions"],
            "pre_solve_checkpoint": build["checkpoint"],
            "pre_solve_gate_report": gate_report,
            "output_evidence": output_evidence,
            "benchmark": benchmark,
            "solved_model_path": str(solved_model_path) if solved_model_path else None,
            "server_pid": session.server_pid,
            "server_port": session.server_port,
            "elapsed_seconds": round(time.time() - started, 3)
        }
        return {
            "status": status,
            "task_id": manifest["metadata"]["task_id"],
            "api_success": True,
            "numerical_success": numerical_success,
            "physical_validation": physical_validation,
            "reproduction_success": reproduction_success,
            "manifest_validation": validation,
            "profile_id": manifest["metadata"]["profile_id"],
            "completed_actions": build["completed_actions"],
            "pre_solve_checkpoint": build["checkpoint"],
            "gate_report": gate_report,
            "output_evidence": output_evidence,
            "benchmark": benchmark,
            "solved_model_path": str(solved_model_path) if solved_model_path else None,
            "server_pid": session.server_pid,
            "evidence": evidence
        }
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--m0", action="store_true")
    parser.add_argument("--manifest")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    result_path = out / "worker_result.json"
    try:
        if args.m0:
            evidence = run_m0(out)
            result = {"status": "PASS", "mode": "m0", "evidence": evidence}
            report = build_execution_report(
                task_id=out.name, job_id=out.name, output_dir=out,
                api_success=True, numerical_success=False,
                physical_validation=None, reproduction_success=None,
                status="M0_SMOKE_PASS", evidence=evidence
            )
            write_report(out, report)
        elif args.manifest:
            result = run_manifest(Path(args.manifest).resolve(), out)
            report = build_execution_report(
                task_id=result["task_id"], job_id=result["task_id"], output_dir=out,
                api_success=result.get("api_success", False),
                numerical_success=result.get("numerical_success", False),
                physical_validation=result.get("physical_validation"),
                reproduction_success=result.get("reproduction_success"),
                status=result["status"], evidence=result.get("evidence", result)
            )
            write_report(out, report)
        else:
            raise ValueError("Specify --m0 or --manifest")
        atomic_write_json(result_path, result)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception as exc:
        result = {
            "status": "FAIL",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc()
        }
        atomic_write_json(result_path, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
