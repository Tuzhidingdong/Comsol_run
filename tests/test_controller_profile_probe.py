from __future__ import annotations

import json
from pathlib import Path

import pytest

from comsol_agent.controller import ControllerError, TaskController
from comsol_agent.io_utils import canonical_json_sha256
from comsol_agent.process_manager import ManagedProcessResult


def _managed_success():
    return ManagedProcessResult(
        worker_pid=1001,
        exit_code=0,
        timed_out=False,
        job_object_used=True,
        graceful_cancel_requested=False,
        hard_termination_used=False,
        cleanup_verified=True,
        process_ids_in_job=[1001, 1002],
        remaining_process_ids=[],
        details={"cleanup_verified_for_all_tracked_pids": True}
    )


def test_controller_runs_profile_probe_in_isolated_directory(monkeypatch, tmp_path: Path):
    import comsol_agent.controller as controller_module

    manifest = {
        "metadata": {
            "mode": "build",
            "task_id": "profile-probe-case",
            "execution_limits": {"timeout_seconds": 120, "cores": 1}
        },
        "study": {"run": False}
    }
    validation = {"manifest_sha256": canonical_json_sha256(manifest)}
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    seen = {}

    def fake_run_managed_worker(command, **kwargs):
        seen["command"] = command
        seen["kwargs"] = kwargs
        output_dir = Path(command[command.index("--output-dir") + 1])
        (output_dir / "worker_result.json").write_text(json.dumps({
            "status": "PROFILE_PROBE_PASSED",
            "task_id": "profile-probe-case",
            "evidence": {"solve_executed": False}
        }), encoding="utf-8")
        return _managed_success()

    monkeypatch.setattr(controller_module, "load_and_validate", lambda path: (manifest, validation))
    monkeypatch.setattr(controller_module, "run_managed_worker", fake_run_managed_worker)

    result = TaskController(tmp_path).run_profile_probe(
        manifest_path,
        tmp_path / "runs"
    )

    assert result["status"] == "PASS"
    assert result["manifest_copy_integrity"] is True
    assert "--profile-probe" in seen["command"]
    assert "--manifest" in seen["command"]
    assert result["worker_result"]["evidence"]["solve_executed"] is False
    assert Path(result["output_dir"], "controller_result.json").is_file()


def test_controller_refuses_probe_manifest_that_requests_solve(monkeypatch, tmp_path: Path):
    import comsol_agent.controller as controller_module

    manifest = {
        "metadata": {"mode": "build", "task_id": "profile-probe-case"},
        "study": {"run": True}
    }
    monkeypatch.setattr(controller_module, "load_and_validate", lambda path: (manifest, {}))

    def must_not_start(*args, **kwargs):
        raise AssertionError("Managed Worker must not start")

    monkeypatch.setattr(controller_module, "run_managed_worker", must_not_start)
    with pytest.raises(ControllerError, match="non-solving"):
        TaskController(tmp_path).run_profile_probe(
            tmp_path / "manifest.json",
            tmp_path / "runs"
        )
