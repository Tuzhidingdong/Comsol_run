from __future__ import annotations

from pathlib import Path

import pytest

from comsol_agent import worker
from comsol_agent.executor import ProfileExecutor


class FakeParameterNode:
    def __init__(self):
        self.values = []

    def set(self, *args):
        self.values.append(args)


class FakeJavaModel:
    def __init__(self):
        self.parameter = FakeParameterNode()

    def param(self):
        return self.parameter


class FakeModel:
    def __init__(self):
        self.java = FakeJavaModel()

    def save(self, path):
        Path(path).write_bytes(b"fake-mph")


class FakeClient:
    def __init__(self):
        self.created = []
        self.model = FakeModel()

    def modules(self):
        return ["COMSOL Multiphysics"]

    def create(self, name):
        self.created.append(name)
        return self.model


def test_discovered_profile_can_be_loaded_only_when_probe_mode_is_explicit(monkeypatch, tmp_path: Path):
    import comsol_agent.executor as executor_module

    seen = []
    profile = {
        "profile_id": "profile-alpha",
        "comsol_version": "6.4",
        "verification": {"state": "discovered"},
        "required_modules": [],
        "actions": [{"op": "set_parameter", "args": {"name": "L", "value": "1[mm]"}}],
        "gate_probes": [],
        "result_evaluations": [],
        "image_exports": []
    }

    def fake_load_profile(profile_id, require_validated=True):
        seen.append((profile_id, require_validated))
        if require_validated:
            raise AssertionError("Production execution must reject a discovered profile")
        return profile

    monkeypatch.setattr(executor_module, "load_profile", fake_load_profile)
    client = FakeClient()
    manifest = {
        "metadata": {"profile_id": "profile-alpha", "task_id": "probe-case.01", "mode": "build"},
        "parameters": {}
    }
    executor = ProfileExecutor(
        client,
        manifest,
        tmp_path,
        require_validated_profile=False
    )
    result = executor.run()

    assert seen == [("profile-alpha", False)]
    assert client.created == ["probe_case_01"]
    assert Path(result["checkpoint"]).is_file()
    assert client.model.java.parameter.values == [("L", "1[mm]")]


def test_profile_executor_defaults_to_validated_only():
    import inspect

    parameter = inspect.signature(ProfileExecutor.__init__).parameters["require_validated_profile"]
    assert parameter.default is True


def test_profile_probe_runs_live_gates_and_never_solves(monkeypatch, tmp_path: Path):
    manifest = {
        "metadata": {
            "mode": "build",
            "task_id": "probe-task-001",
            "execution_limits": {"cores": 1}
        },
        "study": {"run": False},
        "validation": {"required_gates": list("ABCDEFGH")}
    }
    validation = {"valid": True, "manifest_sha256": "a" * 64}
    checkpoint = tmp_path / "pre_solve_model.mph"
    checkpoint.write_bytes(b"checkpoint")

    class Session:
        client = object()
        server_pid = 1234
        server_port = 2036

        def __init__(self, **kwargs):
            self.started = False
            self.closed = False

        def start(self):
            self.started = True

        def close(self):
            self.closed = True
            return {"cleanup_requested": True, "cleanup_errors": []}

    model = object()

    class Executor:
        def __init__(self, client, supplied_manifest, output_dir, require_validated_profile=True):
            assert require_validated_profile is False
            self.profile = {
                "profile_id": "discovered-profile",
                "verification": {"state": "discovered"}
            }
            self.licensed_modules = ["COMSOL Multiphysics"]
            self.model = model
            self.solved = False

        def run(self):
            return {
                "completed_actions": [{"op": "create_component", "status": "completed"}],
                "checkpoint": str(checkpoint)
            }

        def collect_live_gate_evidence(self):
            return {
                gate: {"checks": [{"name": f"{gate}-check", "passed": True}]}
                for gate in "ABCDEFGH"
            }

        def collect_comsol_problems(self):
            return []

        def execute_study(self):
            self.solved = True
            raise AssertionError("A profile probe must never execute Study.solve")

    monkeypatch.setattr(worker, "load_and_validate", lambda path: (manifest, validation))
    monkeypatch.setattr(worker, "ComsolSession", Session)
    monkeypatch.setattr(worker, "ProfileExecutor", Executor)
    monkeypatch.setattr(
        worker,
        "_verify_saved_model_reload",
        lambda client, current_model, path: (current_model, {"structure_match": True})
    )

    result = worker.run_profile_probe(tmp_path / "manifest.json", tmp_path / "probe-output")

    assert result["status"] == "PROFILE_PROBE_PASSED"
    assert result["evidence"]["solve_executed"] is False
    assert result["evidence"]["profile_verification_state_before"] == "discovered"
    assert result["evidence"]["profile_verification_state_after"] == "discovered"
    assert result["evidence"]["suggested_next_state"] == "probe_passed"
    assert result["evidence"]["save_reload"]["structure_match"] is True
    assert result["evidence"]["cleanup_verified"] is True
    assert (tmp_path / "probe-output" / "profile_probe_report.json").is_file()


def test_profile_probe_rejects_manifest_requesting_a_solve(monkeypatch, tmp_path: Path):
    manifest = {
        "metadata": {"mode": "build"},
        "study": {"run": True}
    }
    monkeypatch.setattr(worker, "load_and_validate", lambda path: (manifest, {}))

    class MustNotStartSession:
        def __init__(self, **kwargs):
            raise AssertionError("COMSOL Server must not start for a solving profile-probe Manifest")

    monkeypatch.setattr(worker, "ComsolSession", MustNotStartSession)
    with pytest.raises(RuntimeError, match="cannot solve"):
        worker.run_profile_probe(tmp_path / "manifest.json", tmp_path / "output")



def test_task_id_is_normalized_to_comsol_safe_model_tag():
    assert ProfileExecutor._safe_model_tag("case-001.mesh_L2") == "case_001_mesh_L2"
    assert ProfileExecutor._safe_model_tag("123-leading") == "model_123_leading"
    assert len(ProfileExecutor._safe_model_tag("x" * 80)) == 31
