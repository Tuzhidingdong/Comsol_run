from __future__ import annotations

import argparse
import json
import math
import time
import traceback
from pathlib import Path
from typing import Any

from .comsol import ComsolSession, environment_report
from .gates import evaluate_pre_solve_gates
from .io_utils import atomic_write_json
from .manifest import load_and_validate
from .executor import ProfileExecutor
from .report import build_execution_report, write_report
from .diagnostics import classify_exception, classify_problem_records


MODEL_STRUCTURE_METHODS = (
    "components", "geometries", "selections", "physics", "materials",
    "meshes", "studies", "solutions", "datasets", "plots", "exports"
)


def _model_structure(model) -> dict[str, list[str]]:
    structure = {}
    for method_name in MODEL_STRUCTURE_METHODS:
        method = getattr(model, method_name, None)
        if callable(method):
            structure[method_name] = sorted(str(item) for item in method())
    return structure


def _verify_saved_model_reload(client, model, model_path: Path) -> tuple[Any, dict[str, Any]]:
    path = model_path.resolve()
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"Saved MPH model is missing or empty: {path}")
    before = _model_structure(model)
    client.remove(model)
    reloaded = client.load(str(path))
    after = _model_structure(reloaded)
    mismatches = {
        key: {"before": before.get(key, []), "after": after.get(key, [])}
        for key in sorted(set(before) | set(after))
        if before.get(key, []) != after.get(key, [])
    }
    names = list(client.names())
    files = [str(Path(item).resolve()) for item in client.files()]
    if str(path) not in files:
        mismatches["loaded_file_path"] = {"expected": str(path), "actual": files}
    if mismatches:
        raise RuntimeError(f"Saved MPH reload structure verification failed: {mismatches}")
    return reloaded, {
        "model_path": str(path),
        "file_size_bytes": path.stat().st_size,
        "model_names_after_reload": names,
        "file_paths_after_reload": files,
        "structure_before_save": before,
        "structure_after_reload": after,
        "structure_match": True
    }


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
    if cleanup.get("cleanup_errors"):
        raise RuntimeError(f"COMSOL session cleanup reported errors: {cleanup['cleanup_errors']}")
    return evidence


def run_manifest(manifest_path: Path, output_dir: Path) -> dict[str, Any]:
    manifest, validation = load_and_validate(manifest_path)
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

        # Collect all model-dependent live gate evidence before releasing the
        # original Java handles during the checkpoint reload test.
        live_evidence = executor.collect_live_gate_evidence()
        release_xmesh = getattr(executor, "release_xmesh_info", None)
        xmesh_cleanup = release_xmesh() if callable(release_xmesh) else {"released": [], "errors": []}
        pre_solve_problems = executor.collect_comsol_problems()
        pre_solve_problem_diagnostics = classify_problem_records(pre_solve_problems)
        diagnostics_check = {
            "name": "COMSOL model diagnostics are empty",
            "passed": len(pre_solve_problems) == 0,
            "problem_count": len(pre_solve_problems),
            "problems": pre_solve_problems,
            "source": "MPh Model.problems()"
        }
        live_evidence.setdefault("E", {"checks": []})["checks"].append(diagnostics_check)
        gate_report = evaluate_pre_solve_gates(manifest["validation"]["required_gates"], live_evidence)
        atomic_write_json(output_dir / "pre_solve_gate_report.json", gate_report)

        executor.model, pre_solve_reload = _verify_saved_model_reload(
            session.client, executor.model, Path(build["checkpoint"])
        )

        numerical_success = False
        physical_validation = None
        reproduction_success = None
        output_evidence = None
        benchmark = None
        conservation = None
        image_exports = []
        post_solve_problems: list[Any] = []
        solved_model_path = None
        solved_reload = None
        source_integrity = executor.verify_source_unchanged()
        status = "BUILD_ONLY_PRE_SOLVE_GATES_REPORTED"

        if manifest["study"].get("run", False):
            if not gate_report["solve_allowed"]:
                status = "PRE_SOLVE_BLOCKED"
            else:
                executor.execute_study()
                numerical_success = True
                output_evidence = executor.extract_outputs()
                image_exports = executor.run_image_exports()
                benchmark = executor.compare_benchmark(output_evidence["results"])
                conservation = executor.evaluate_conservation_checks()
                physical_validation = None if conservation is None else bool(conservation["passed"])
                if benchmark is not None:
                    atomic_write_json(output_dir / "benchmark_report.json", benchmark)
                    reproduction_success = bool(benchmark["passed"])
                if conservation is not None:
                    atomic_write_json(output_dir / "conservation_report.json", conservation)
                post_solve_problems = executor.collect_comsol_problems()
                post_solve_problem_diagnostics = classify_problem_records(post_solve_problems)
                solved_model_path = (output_dir / "solved_model.mph").resolve()
                if solved_model_path.exists():
                    raise RuntimeError(f"Refusing to overwrite solved model: {solved_model_path}")
                executor.model.save(str(solved_model_path))
                executor.model, solved_reload = _verify_saved_model_reload(
                    session.client, executor.model, solved_model_path
                )
                source_integrity = executor.verify_source_unchanged()
                target_values = {
                    name: item["value"]
                    for name, item in (output_evidence.get("results") or {}).items()
                    if isinstance(item.get("value"), (int, float)) and not isinstance(item.get("value"), bool)
                }
                metrics_payload = {"target_values": target_values}
                mesh_h_key = executor.profile.get("mesh_characteristic_size_result")
                if mesh_h_key:
                    mesh_h_item = output_evidence.get("results", {}).get(str(mesh_h_key))
                    if not isinstance(mesh_h_item, dict):
                        raise RuntimeError(
                            f"Profile mesh_characteristic_size_result {mesh_h_key!r} "
                            "was not found in the extracted scalar results"
                        )
                    mesh_h = mesh_h_item.get("value")
                    if (
                        isinstance(mesh_h, bool)
                        or not isinstance(mesh_h, (int, float))
                        or not math.isfinite(float(mesh_h))
                        or float(mesh_h) <= 0
                    ):
                        raise RuntimeError("Profile mesh characteristic size must be a finite positive scalar")
                    metrics_payload["mesh_characteristic_size"] = float(mesh_h)
                    metrics_payload["mesh_characteristic_size_result"] = str(mesh_h_key)
                atomic_write_json(output_dir / "metrics.json", metrics_payload)
                if physical_validation is False:
                    status = "NUMERICAL_SUCCESS_PHYSICAL_CHECK_FAILED"
                elif reproduction_success is False:
                    status = "NUMERICAL_SUCCESS_REPRODUCTION_FAILED"
                elif reproduction_success is True:
                    status = "NUMERICAL_SUCCESS_REPRODUCTION_CHECKED"
                else:
                    status = "NUMERICAL_SUCCESS_VALIDATION_PENDING"

        evidence = {
            "manifest_validation": validation,
            "mode": manifest["metadata"]["mode"],
            "profile_id": manifest["metadata"]["profile_id"],
            "licensed_modules": getattr(executor, "licensed_modules", []),
            "completed_actions": build["completed_actions"],
            "pre_solve_checkpoint": build["checkpoint"],
            "pre_solve_reload": pre_solve_reload,
            "source_integrity": source_integrity,
            "pre_solve_gate_report": gate_report,
            "xmesh_cleanup": xmesh_cleanup,
            "pre_solve_comsol_problems": pre_solve_problems,
            "pre_solve_problem_diagnostics": pre_solve_problem_diagnostics,
            "output_evidence": output_evidence,
            "image_exports": image_exports,
            "benchmark": benchmark,
            "conservation": conservation,
            "post_solve_comsol_problems": post_solve_problems,
            "post_solve_problem_diagnostics": (
                post_solve_problem_diagnostics if manifest["study"].get("run", False) else []
            ),
            "solved_model_path": str(solved_model_path) if solved_model_path else None,
            "solved_model_reload": solved_reload,
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
            "pre_solve_reload": pre_solve_reload,
            "source_integrity": source_integrity,
            "gate_report": gate_report,
            "pre_solve_comsol_problems": pre_solve_problems,
            "pre_solve_problem_diagnostics": pre_solve_problem_diagnostics,
            "output_evidence": output_evidence,
            "image_exports": image_exports,
            "benchmark": benchmark,
            "conservation": conservation,
            "post_solve_comsol_problems": post_solve_problems,
            "post_solve_problem_diagnostics": (
                post_solve_problem_diagnostics if manifest["study"].get("run", False) else []
            ),
            "solved_model_path": str(solved_model_path) if solved_model_path else None,
            "solved_model_reload": solved_reload,
            "server_pid": session.server_pid,
            "evidence": evidence
        }
    finally:
        session.close()


def run_profile_probe(manifest_path: Path, output_dir: Path) -> dict[str, Any]:
    """Probe a discovered COMSOL 6.4 API profile without executing a Study solve."""
    manifest, validation = load_and_validate(manifest_path)
    if manifest["metadata"]["mode"] != "build":
        raise RuntimeError("Profile probe supports build mode only")
    if manifest["study"].get("run", False):
        raise RuntimeError("Profile probe cannot solve; set study.run=false")

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    session = ComsolSession(
        cores=int(manifest["metadata"].get("execution_limits", {}).get("cores", 1)),
        version="6.4",
        startup_timeout=120
    )
    result: dict[str, Any] | None = None
    try:
        session.start()
        executor = ProfileExecutor(
            session.client,
            manifest,
            output_dir,
            require_validated_profile=False
        )
        build = executor.run()

        # Capture live evidence before releasing the current model handle.
        live_evidence = executor.collect_live_gate_evidence()
        release_xmesh = getattr(executor, "release_xmesh_info", None)
        xmesh_cleanup = release_xmesh() if callable(release_xmesh) else {"released": [], "errors": []}
        problems = executor.collect_comsol_problems()
        live_evidence.setdefault("E", {"checks": []})["checks"].append({
            "name": "COMSOL model diagnostics are empty",
            "passed": len(problems) == 0,
            "problem_count": len(problems),
            "problems": problems,
            "source": "MPh Model.problems()"
        })
        gate_report = evaluate_pre_solve_gates(
            manifest["validation"]["required_gates"],
            live_evidence
        )
        executor.model, reload_evidence = _verify_saved_model_reload(
            session.client,
            executor.model,
            Path(build["checkpoint"])
        )

        verification = executor.profile.get("verification", {})
        current_state = verification.get("state", "discovered")
        probe_passed = bool(gate_report["solve_allowed"] and not problems)
        evidence = {
            "manifest_validation": validation,
            "profile_id": executor.profile["profile_id"],
            "profile_verification_state_before": current_state,
            "profile_verification_state_after": current_state,
            "suggested_next_state": (
                "probe_passed"
                if probe_passed and current_state == "discovered"
                else current_state
            ),
            "licensed_modules": getattr(executor, "licensed_modules", []),
            "completed_actions": build["completed_actions"],
            "pre_solve_checkpoint": build["checkpoint"],
            "save_reload": reload_evidence,
            "live_gate_evidence": live_evidence,
            "gate_report": gate_report,
            "xmesh_cleanup": xmesh_cleanup,
            "comsol_problems": problems,
            "server_pid": session.server_pid,
            "server_port": session.server_port,
            "solve_executed": False,
            "numerical_success": False,
            "physical_validation": None,
            "reproduction_success": None
        }
        result = {
            "status": "PROFILE_PROBE_PASSED" if probe_passed else "PROFILE_PROBE_BLOCKED",
            "task_id": manifest["metadata"]["task_id"],
            "api_success": True,
            "numerical_success": False,
            "physical_validation": None,
            "reproduction_success": None,
            "evidence": evidence
        }
    finally:
        cleanup = session.close()
        if result is not None:
            result["evidence"]["cleanup"] = cleanup
            cleanup_verified = (
                isinstance(cleanup, dict)
                and cleanup.get("cleanup_requested") is True
                and not cleanup.get("cleanup_errors")
            )
            result["evidence"]["cleanup_verified"] = cleanup_verified
            if not cleanup_verified:
                result["status"] = "PROFILE_PROBE_FAILED"
            atomic_write_json(output_dir / "profile_probe_report.json", result)
    if result is None:
        raise RuntimeError("Profile probe did not produce an execution result")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--m0", action="store_true")
    parser.add_argument("--manifest")
    parser.add_argument("--profile-probe", action="store_true")
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
        elif args.profile_probe and args.manifest:
            result = run_profile_probe(Path(args.manifest).resolve(), out)
            report = build_execution_report(
                task_id=result["task_id"], job_id=result["task_id"], output_dir=out,
                api_success=result.get("api_success", False),
                numerical_success=False,
                physical_validation=None,
                reproduction_success=None,
                status=result["status"], evidence=result.get("evidence", result)
            )
            write_report(out, report)
        elif args.manifest and not args.profile_probe:
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
            raise ValueError("Specify --m0, --manifest, or --profile-probe --manifest")
        atomic_write_json(result_path, result)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0 if result.get("status") in {
            "PASS",
            "BUILD_ONLY_PRE_SOLVE_GATES_REPORTED",
            "PRE_SOLVE_BLOCKED",
            "PROFILE_PROBE_PASSED",
            "PROFILE_PROBE_BLOCKED"
        } or str(result.get("status", "")).startswith("NUMERICAL_SUCCESS_") else 2
    except Exception as exc:
        original_traceback = traceback.format_exc()
        diagnostic = classify_exception(exc, original_traceback)
        result = {
            "status": "FAIL",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": original_traceback,
            "diagnostic": diagnostic
        }
        atomic_write_json(out / "diagnostic_report.json", diagnostic)
        atomic_write_json(result_path, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
