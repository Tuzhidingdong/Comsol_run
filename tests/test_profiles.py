from __future__ import annotations

import json
from pathlib import Path

import pytest

from comsol_agent.profiles import ProfileError, load_profile, list_profiles


def test_unvalidated_profile_is_rejected_for_production(tmp_path: Path):
    profile = {
        "profile_id": "example",
        "comsol_version": "6.4",
        "verification": {"state": "discovered"},
        "actions": []
    }
    (tmp_path / "example.json").write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(ProfileError, match="not validated"):
        load_profile("example", root=tmp_path, require_validated=True)


def test_discovered_profile_can_be_inspected_without_promotion(tmp_path: Path):
    profile = {
        "profile_id": "example",
        "comsol_version": "6.4",
        "verification": {"state": "discovered"},
        "actions": []
    }
    (tmp_path / "example.json").write_text(json.dumps(profile), encoding="utf-8")
    loaded = load_profile("example", root=tmp_path, require_validated=False)
    assert loaded["verification"]["state"] == "discovered"


def test_profile_version_mismatch_is_rejected(tmp_path: Path):
    profile = {
        "profile_id": "example",
        "comsol_version": "6.3",
        "verification": {"state": "discovered"},
        "actions": []
    }
    (tmp_path / "example.json").write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(ProfileError, match="COMSOL 6.4"):
        load_profile("example", root=tmp_path, require_validated=False)


def test_initial_profile_inventory_has_no_claimed_validated_physics():
    profiles = list_profiles()
    assert all(item.get("state") != "validated" for item in profiles)



def test_profile_required_modules_are_not_silently_ignored(monkeypatch, tmp_path: Path):
    from types import SimpleNamespace

    import comsol_agent.executor as executor_module
    from comsol_agent.executor import ExecutionError, ProfileExecutor

    class Client:
        def __init__(self):
            self.create_called = False

        def modules(self):
            return ["COMSOL Multiphysics", "AC/DC Module"]

        def create(self, name):
            self.create_called = True
            raise AssertionError("Model creation must not start without the required licensed module")

    monkeypatch.setattr(
        executor_module,
        "load_profile",
        lambda *args, **kwargs: {
            "profile_id": "test-profile",
            "comsol_version": "6.4",
            "verification": {"state": "validated", "test_id": "M0-test", "evidence_files": ["evidence.json"]},
            "required_modules": ["CFD Module"],
            "actions": [{"op": "create_component", "args": {"tag": "comp1"}}]
        }
    )
    client = Client()
    executor = ProfileExecutor(
        client,
        {"metadata": {"profile_id": "test-profile", "task_id": "case-001", "mode": "build"}},
        tmp_path
    )
    with pytest.raises(ExecutionError, match="required profile modules"):
        executor.run()
    assert client.create_called is False
