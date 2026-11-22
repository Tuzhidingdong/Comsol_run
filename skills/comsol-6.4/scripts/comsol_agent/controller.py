from __future__ import annotations

import json
import shutil
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .convergence import aggregate_scalar_metrics
from .io_utils import atomic_write_json, canonical_json_sha256, safe_task_id
from .manifest import load_and_validate
from .profiles import load_profile
from .process_manager import run_managed_worker, verify_job_object_process_tree


class ControllerError(RuntimeError):
    pass


class TaskController:
    def __init__(self, repository_root: str | Path | None = None):
        self.repository_root = Path(repository_root or Path.cwd()).resolve()

    @staticmethod
    def _create_task_dir(root: Path, task_id: str) -> Path:
        safe_task_id(task_id)
        target = (root / task_id).resolve()
        if target.exists():
            raise ControllerError(f"Refusing to reuse or overwrite task output directory: {target}")
        target.mkdir(parents=True, exist_ok=False)
        return target

    def run_m0(self, output_dir: str | Path, timeout_seconds: int = 300) -> dict[str, Any]:
        root = Path(output_dir).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        task_id = f"m0-{time.strftime('%Y%m%d-%H%M%S')}-{int(time.time() * 1000) % 1000:03d}"
        task_dir = self._create_task_dir(root, task_id)

        process_tree = verify_job_object_process_tree(task_dir / "job_object_probe")
        atomic_write_json(task_dir / "job_object_probe_result.json", process_tree)
        if process_tree.get("status") != "PASS":
            result = {
                "task_id": task_id, "output_dir": str(task_dir),
                "process_tree_probe": process_tree, "worker_result": None,
                "status": "FAIL", "blocked_before_comsol_start": True
            }
            atomic_write_json(task_dir / "controller_result.json", result)
            self._write_acceptance_summary(root, result)
            return result

        command = [sys.executable, "-m", "comsol_agent.worker", "--m0", "--output-dir", str(task_dir)]
        managed = run_managed_worker(
            command, cwd=self.repository_root, timeout_seconds=timeout_seconds,
            graceful_cancel_seconds=10, cancel_file=task_dir / "cancel.request"
        )
        worker_result_path = task_dir / "worker_result.json"
        worker_result = json.loads(worker_result_path.read_text(encoding="utf-8")) if worker_result_path.exists() else None
        result = {
            "task_id": task_id, "output_dir": str(task_dir),
            "process_tree_probe": process_tree, "managed_process": asdict(managed),
            "worker_result": worker_result,
            "status": "PASS" if (
                managed.exit_code == 0 and not managed.timed_out and managed.cleanup_verified
                and worker_result and worker_result.get("status") == "PASS"
            ) else "FAIL"
        }
        atomic_write_json(task_dir / "controller_result.json", result)
        self._write_acceptance_summary(root, result)
        return result

    @staticmethod
    def _write_acceptance_summary(root: Path, result: dict[str, Any]) -> None:
        process_result = result.get("managed_process", {})
        lines = [
            "# Local COMSOL 6.4 acceptance result", "",
            f"- Overall M0 status: **{result.get('status')}**",
            f"- Task ID: {result.get('task_id')}",
            f"- Evidence directory: {result.get('output_dir')}",
            f"- Windows Job Object process-tree probe: {result.get('process_tree_probe', {}).get('status', 'NOT_RUN')}",
            f"- COMSOL Worker exit code: {process_result.get('exit_code', 'NOT_STARTED')}",
            f"- COMSOL Worker timeout: {process_result.get('timed_out', False)}",
            f"- All recorded Job Object PIDs terminated: {process_result.get('cleanup_verified', False)}",
            "",
            "## Interpretation", "",
            "PASS means the local M0 smoke checks in this report passed. It does not by itself mean that M1/M2 or all 37 task-plan acceptance criteria have passed.",
            "",
            "Inspect controller_result.json, worker_result.json, environment_report.json and verification_report.md for detailed evidence.",
            ""
        ]
        (root / "acceptance_report.md").write_text("\n".join(lines), encoding="utf-8")

    def run_manifest(
        self, manifest_path: str | Path, output_root: str | Path,
        timeout_seconds: int | None = None
    ) -> dict[str, Any]:
        source = Path(manifest_path).expanduser().resolve()
        manifest, validation = load_and_validate(source)
        metadata = manifest["metadata"]
        task_id = safe_task_id(metadata["task_id"])
        root = Path(output_root).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        task_dir = self._create_task_dir(root, task_id)
        copied_manifest = task_dir / "manifest.json"
        shutil.copy2(source, copied_manifest)
        copied_data = json.loads(copied_manifest.read_text(encoding="utf-8"))
        copy_integrity = canonical_json_sha256(copied_data) == validation["manifest_sha256"]
        if not copy_integrity:
            raise ControllerError("Manifest changed during copy; refusing to launch Worker")
        limit = timeout_seconds or metadata.get("execution_limits", {}).get("timeout_seconds", 3600)
        command = [
            sys.executable, "-m", "comsol_agent.worker",
            "--manifest", str(copied_manifest), "--output-dir", str(task_dir)
        ]
        managed = run_managed_worker(
            command, cwd=self.repository_root, timeout_seconds=float(limit),
            graceful_cancel_seconds=float(metadata.get("execution_limits", {}).get("graceful_cancel_seconds", 15)),
            cancel_file=task_dir / "cancel.request",
            max_memory_gb=metadata.get("execution_limits", {}).get("max_memory_gb")
        )
        worker_result_path = task_dir / "worker_result.json"
        worker_result = json.loads(worker_result_path.read_text(encoding="utf-8")) if worker_result_path.exists() else None
        worker_status = worker_result.get("status") if worker_result else None
        worker_ok = bool(worker_status in {
            "BUILD_ONLY_PRE_SOLVE_GATES_REPORTED",
            "PRE_SOLVE_BLOCKED",
            "NUMERICAL_SUCCESS_VALIDATION_PENDING",
            "NUMERICAL_SUCCESS_REPRODUCTION_CHECKED"
        } or (isinstance(worker_status, str) and worker_status.startswith("NUMERICAL_SUCCESS_")))
        run_state = "BLOCKED" if worker_status == "PRE_SOLVE_BLOCKED" else (
            "PASS" if managed.exit_code == 0 and not managed.timed_out and managed.cleanup_verified and worker_ok else "FAIL"
        )
        result = {
            "task_id": task_id,
            "manifest_sha256": validation["manifest_sha256"],
            "copied_manifest_sha256": canonical_json_sha256(copied_data),
            "manifest_copy_integrity": copy_integrity,
            "output_dir": str(task_dir),
            "managed_process": asdict(managed),
            "worker_result": worker_result,
            "status": run_state
        }
        atomic_write_json(task_dir / "controller_result.json", result)
        return result

    @staticmethod
    def _verify_probe_evidence(
        probe_report: str | Path, manifest: dict[str, Any], validation: dict[str, Any]
    ) -> dict[str, Any]:
        """Bind a real, non-solving profile-probe report to the current inputs."""
        path = Path(probe_report).expanduser().resolve()
        if not path.is_file():
            raise ControllerError(f"Profile-probe report not found: {path}")
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ControllerError(f"Profile-probe report is not readable JSON: {exc}") from exc
        evidence = report.get("evidence") or {}
        gate_report = evidence.get("gate_report") or {}
        if report.get("status") != "PROFILE_PROBE_PASSED":
            raise ControllerError("Profile-probe report is not PROFILE_PROBE_PASSED")
        if evidence.get("solve_executed") is not False or evidence.get("numerical_success") is not False:
            raise ControllerError("Profile-probe report must be non-solving")
        if gate_report.get("status") != "PASS" or gate_report.get("solve_allowed") is not True:
            raise ControllerError("Profile-probe gates are not all PASS")
        gates = gate_report.get("gates") or {}
        if sorted(gates) != list("ABCDEFGH") or any(
            gate.get("status") != "PASS" for gate in gates.values()
        ):
            raise ControllerError("Profile-probe must contain PASS evidence for all gates A-H")
        if (evidence.get("manifest_validation") or {}).get("valid") is not True:
            raise ControllerError("Profile-probe manifest validation evidence is missing")
        # The integration Manifest differs from the probed draft only in
        # study.run (probe mode requires false, integration requires true).
        # Normalize that one field before binding, so every other input remains
        # hash-bound to the real probe report.
        normalized = dict(manifest)
        normalized["study"] = dict(manifest.get("study", {}), run=False)
        normalized_hash = canonical_json_sha256(normalized)
        probe_manifest_hash = evidence.get("manifest_sha256")
        if probe_manifest_hash is None:
            probe_manifest_hash = (evidence.get("manifest_validation") or {}).get("manifest_sha256")
        if probe_manifest_hash != normalized_hash:
            raise ControllerError(
                "Profile-probe report does not match the current Manifest "
                "(normalized with study.run=false)"
            )
        if evidence.get("profile_id") != manifest["metadata"].get("profile_id"):
            raise ControllerError("Profile-probe report does not match the current Profile")
        if (evidence.get("save_reload") or {}).get("structure_match") is not True:
            raise ControllerError("Profile-probe save/reload evidence is missing")
        if evidence.get("comsol_problems"):
            raise ControllerError("Profile-probe reported COMSOL model problems")
        return {
            "path": str(path), "profile_id": evidence["profile_id"],
            "probe_manifest_sha256": probe_manifest_hash,
            "integration_manifest_sha256": validation.get("manifest_sha256"),
            "normalized_manifest_sha256": normalized_hash,
            "gate_status": gate_report["status"], "gates": sorted(gates),
            "solve_executed": False, "numerical_success": False,
        }

    def run_integration_test(
        self,
        manifest_path: str | Path,
        output_root: str | Path,
        probe_report: str | Path,
        *,
        confirm_solve: bool = False,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        """Controlled, audited real solve for a not-yet-validated Profile.

        This path is deliberately separate from production ``run``: it requires
        a matching real profile-probe report and an explicit --confirm-solve.
        It never changes the Profile state.
        """
        source = Path(manifest_path).expanduser().resolve()
        manifest, validation = load_and_validate(source)
        metadata = manifest["metadata"]
        profile_id = metadata["profile_id"]
        # Validate Profile structure without granting production privileges.
        profile = load_profile(profile_id, require_validated=False)
        if not confirm_solve:
            raise ControllerError(
                "Integration test requires explicit --confirm-solve authorization for a real solve"
            )
        probe_binding = self._verify_probe_evidence(probe_report, manifest, validation)

        task_id = safe_task_id(metadata["task_id"])
        root = Path(output_root).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        task_dir = self._create_task_dir(root, f"it-{task_id}")
        copied_manifest = task_dir / "manifest.json"
        shutil.copy2(source, copied_manifest)
        copied_data = json.loads(copied_manifest.read_text(encoding="utf-8"))
        copy_integrity = canonical_json_sha256(copied_data) == validation["manifest_sha256"]
        if not copy_integrity:
            raise ControllerError("Manifest changed during integration-test copy")
        limit = timeout_seconds or metadata.get("execution_limits", {}).get("timeout_seconds", 1800)
        command = [
            sys.executable, "-m", "comsol_agent.worker", "--integration-test",
            "--manifest", str(copied_manifest), "--output-dir", str(task_dir),
        ]
        managed = run_managed_worker(
            command, cwd=self.repository_root, timeout_seconds=float(limit),
            graceful_cancel_seconds=float(
                metadata.get("execution_limits", {}).get("graceful_cancel_seconds", 15)
            ),
            cancel_file=task_dir / "cancel.request",
            max_memory_gb=metadata.get("execution_limits", {}).get("max_memory_gb"),
        )
        worker_path = task_dir / "worker_result.json"
        worker_result = json.loads(worker_path.read_text(encoding="utf-8")) if worker_path.is_file() else None
        worker_status = worker_result.get("status") if worker_result else None
        worker_ok = bool(worker_status in {
            "BUILD_ONLY_PRE_SOLVE_GATES_REPORTED", "PRE_SOLVE_BLOCKED",
            "NUMERICAL_SUCCESS_VALIDATION_PENDING", "NUMERICAL_SUCCESS_REPRODUCTION_CHECKED",
        } or (isinstance(worker_status, str) and worker_status.startswith("NUMERICAL_SUCCESS_")))
        managed_ok = managed.exit_code == 0 and not managed.timed_out and managed.cleanup_verified
        status = "PASS" if managed_ok and worker_ok else "FAIL"
        after = load_profile(profile_id, require_validated=False)
        result = {
            "task_id": task_id,
            "execution_mode": "integration_test",
            "profile_id": profile_id,
            "profile_state_before": profile.get("verification", {}).get("state"),
            "profile_state_after": after.get("verification", {}).get("state"),
            "manifest_sha256": validation["manifest_sha256"],
            "manifest_copy_integrity": copy_integrity,
            "probe_evidence": probe_binding,
            "output_dir": str(task_dir),
            "managed_process": asdict(managed),
            "worker_result": worker_result,
            "status": status,
        }
        atomic_write_json(task_dir / "integration_test_result.json", result)
        return result

    def run_profile_probe(
        self,
        manifest_path: str | Path,
        output_root: str | Path,
        timeout_seconds: int | None = None
    ) -> dict[str, Any]:
        source = Path(manifest_path).expanduser().resolve()
        manifest, validation = load_and_validate(source)
        metadata = manifest["metadata"]
        if metadata["mode"] != "build":
            raise ControllerError("Profile probe supports build mode only")
        if manifest["study"].get("run", False):
            raise ControllerError("Profile probe is non-solving; set study.run=false")

        root = Path(output_root).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        task_id = safe_task_id(metadata["task_id"])
        probe_id = safe_task_id(
            f"probe-{validation['manifest_sha256'][:16]}-{int(time.time() * 1000)}"
        )
        task_dir = self._create_task_dir(root, probe_id)
        copied_manifest = task_dir / "manifest.json"
        shutil.copy2(source, copied_manifest)
        copied_data = json.loads(copied_manifest.read_text(encoding="utf-8"))
        copied_sha = canonical_json_sha256(copied_data)
        copy_integrity = copied_sha == validation["manifest_sha256"]
        if not copy_integrity:
            raise ControllerError("Manifest changed during profile-probe copy; refusing to launch Worker")

        limit = timeout_seconds or metadata.get("execution_limits", {}).get("timeout_seconds", 1800)
        command = [
            sys.executable,
            "-m",
            "comsol_agent.worker",
            "--profile-probe",
            "--manifest",
            str(copied_manifest),
            "--output-dir",
            str(task_dir)
        ]
        managed = run_managed_worker(
            command,
            cwd=self.repository_root,
            timeout_seconds=float(limit),
            graceful_cancel_seconds=float(
                metadata.get("execution_limits", {}).get("graceful_cancel_seconds", 15)
            ),
            cancel_file=task_dir / "cancel.request",
            max_memory_gb=metadata.get("execution_limits", {}).get("max_memory_gb")
        )
        worker_path = task_dir / "worker_result.json"
        worker_result = (
            json.loads(worker_path.read_text(encoding="utf-8"))
            if worker_path.is_file() else None
        )
        worker_status = worker_result.get("status") if worker_result else None
        managed_ok = (
            managed.exit_code == 0
            and not managed.timed_out
            and managed.cleanup_verified
        )
        if worker_status == "PROFILE_PROBE_PASSED":
            run_status = "PASS" if managed_ok else "FAIL"
        elif worker_status == "PROFILE_PROBE_BLOCKED":
            run_status = "BLOCKED" if managed_ok else "FAIL"
        else:
            run_status = "FAIL"

        result = {
            "task_id": task_id,
            "profile_probe_id": probe_id,
            "manifest_sha256": validation["manifest_sha256"],
            "copied_manifest_sha256": copied_sha,
            "manifest_copy_integrity": copy_integrity,
            "output_dir": str(task_dir),
            "managed_process": asdict(managed),
            "worker_result": worker_result,
            "status": run_status
        }
        atomic_write_json(task_dir / "controller_result.json", result)
        return result

    def run_convergence_plan(
        self, plan_dir: str | Path, metric_name: str = "target",
        timeout_seconds: int | None = None
    ) -> dict[str, Any]:
        root = Path(plan_dir).expanduser().resolve()
        plan_path = root / "child_tasks.json"
        if not plan_path.is_file():
            raise ControllerError(f"Convergence plan index not found: {plan_path}")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        child_results = []
        for child in plan.get("children", []):
            child_id = safe_task_id(child["task_id"])
            existing_output = child.get("output_dir")
            if child.get("status") == "PASS" and existing_output:
                controller_file = Path(existing_output) / "controller_result.json"
                if controller_file.is_file():
                    previous = json.loads(controller_file.read_text(encoding="utf-8"))
                    if previous.get("status") == "PASS":
                        child_results.append({"task_id": child_id, "status": "SKIPPED_ALREADY_PASSED", "output_dir": existing_output})
                        continue

            output_root = Path(child["output_root"]).resolve()
            attempt = 1
            while (output_root / child_id).exists():
                attempt += 1
                output_root = output_root.parent / f"run_attempt_{attempt:02d}"
            manifest_path = Path(child["manifest"]).resolve()
            result = self.run_manifest(manifest_path, output_root, timeout_seconds)
            child["output_dir"] = result["output_dir"]
            child["status"] = result["status"]
            child["attempt"] = attempt
            atomic_write_json(plan_path, plan)
            child_results.append({
                "task_id": child_id, "status": result["status"],
                "attempt": attempt, "output_dir": result["output_dir"]
            })

        aggregate = aggregate_scalar_metrics(root, metric_name)
        result = {
            "parent_task_id": plan.get("parent_task_id"),
            "kind": plan.get("kind"),
            "child_results": child_results,
            "aggregation": aggregate,
            "status": "PASS" if all(item["status"] in {"PASS", "SKIPPED_ALREADY_PASSED"} for item in child_results) else "PARTIAL_FAILURE"
        }
        atomic_write_json(root / "convergence_execution_report.json", result)
        return result
