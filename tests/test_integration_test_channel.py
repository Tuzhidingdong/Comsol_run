"""Focused tests for the Study adapter, scalar observables and integration-test channel."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from comsol_agent import cli, controller
from comsol_agent.executor import ExecutionError, ProfileExecutor
from comsol_agent.profiles import ProfileError


class JavaStudy:
    def __init__(self, label):
        self._label = label

    def label(self):
        return self._label


class JavaStudyList:
    """Doubles both StudyList (tags()) and study(tag) lookup of COMSOL Java."""

    def __init__(self, studies):
        self._studies = studies

    def tags(self):
        return list(self._studies)

    def __call__(self, tag=None):
        if tag is None:
            return self
        return JavaStudy(self._studies[tag])


def make_executor(studies=None, model=None):
    executor = ProfileExecutor(client=SimpleNamespace(java=object()), manifest={
        "study": {"tag": "std1", "label": "stationary"},
        "validation": {"baseline": {"T_mean": {
            "reference_value": 50.0, "relative_tolerance": 0.02,
        }}},
    }, output_dir=".")
    studies = studies or {"std1": "stationary"}
    model = model or SimpleNamespace(
        java=SimpleNamespace(study=JavaStudyList(studies),
                             sol=lambda tag=None: None),
        solve=lambda label: None,
    )
    executor.model = model
    return executor


def test_resolve_study_by_tag_or_label():
    ex = make_executor()
    assert ex.resolve_study("std1") == {"tag": "std1", "label": "stationary"}
    assert ex.resolve_study("stationary") == {"tag": "std1", "label": "stationary"}


def test_resolve_study_missing_or_ambiguous_fails_closed():
    ex = make_executor()
    with pytest.raises(ExecutionError, match="not found"):
        ex.resolve_study("missing")
    ambiguous = make_executor({"std1": "same", "std2": "same"})
    with pytest.raises(ExecutionError, match="ambiguous"):
        ambiguous.resolve_study("same")


def test_execute_study_uses_label_and_records_status():
    calls = []

    class Model:
        java = SimpleNamespace(
            study=JavaStudyList({"std1": "stationary"}),
            sol=lambda tag=None: None,
        )

        def solve(self, label):
            calls.append(label)

    ex = make_executor(model=Model())
    record = ex.execute_study()
    assert calls == ["stationary"]
    assert record["solve_status"] == "SOLVED"
    assert record["tag"] == "std1" and record["label"] == "stationary"


def test_execute_study_records_failure():
    class Model:
        java = SimpleNamespace(
            study=JavaStudyList({"std1": "stationary"}),
            sol=lambda tag=None: None,
        )

        def solve(self, label):
            raise RuntimeError("solve failed")

    ex = make_executor(model=Model())
    with pytest.raises(RuntimeError, match="solve failed"):
        ex.execute_study()
    assert ex.study_execution["solve_status"] == "FAILED"
    assert "solve failed" in ex.study_execution["error"]


def test_average_coupling_action_binds_handle():
    created = {}

    class Cpl:
        def create(self, tag, kind):
            created["tag"], created["kind"] = tag, kind
            return SimpleNamespace(selection=lambda: SimpleNamespace(all=lambda: None))

    java = SimpleNamespace(component=lambda tag: SimpleNamespace(cpl=lambda: Cpl()))
    ex = make_executor(model=SimpleNamespace(java=java))
    ex._execute("create_average_coupling", {"component": "comp1", "tag": "aveop1"})
    assert created == {"tag": "aveop1", "kind": "Average"}
    assert "coupling:aveop1" in ex.nodes


def test_extract_outputs_keeps_definition_and_rejects_nonfinite():
    ex = make_executor()
    ex.profile = {"result_evaluations": [], "outputs": {"quantities": []}}
    ex.output_dir = Path(".")
    ex.manifest = {"outputs": {"quantities": [{
        "name": "T_mean", "expression": "aveop1(T)", "expected_unit": "degC",
        "definition": {"kind": "domain_average", "operator": "aveop1"},
    }]}}
    ex.model = SimpleNamespace(
        evaluate=lambda expr, unit: 50.0,
        java=SimpleNamespace(study=lambda: JavaStudyList({"std1": "stationary"})),
    )
    ex.output_dir = Path(".")
    out = ex.extract_outputs()
    assert out["results"]["T_mean"]["definition"]["kind"] == "domain_average"
    assert out["results"]["T_mean"]["value_kind"] == "scalar"
    with pytest.raises(ExecutionError, match="non-finite"):
        ex.model = SimpleNamespace(evaluate=lambda expr, unit: float("nan"))
        ex.extract_outputs()


def test_compare_benchmark_requires_scalar_observable():
    ex = make_executor()
    with pytest.raises(ExecutionError, match="finite scalar"):
        ex.compare_benchmark({"T_mean": {
            "value": [1.0, 2.0], "expression": "T", "value_kind": "field_array",
        }})
    result = ex.compare_benchmark({"T_mean": {
        "value": 50.01, "expression": "aveop1(T)", "value_kind": "scalar",
        "definition": None, "expected_unit": "degC",
    }})
    assert result["passed"] is True
    assert result["checks"][0]["relative_error"] < 0.001


def _valid_probe(tmp_path, manifest_hash, profile_id="example_heat2d_discovered"):
    gates = {g: {"status": "PASS"} for g in "ABCDEFGH"}
    report = {
        "status": "PROFILE_PROBE_PASSED",
        "evidence": {
            "solve_executed": False, "numerical_success": False,
            "gate_report": {"status": "PASS", "solve_allowed": True, "gates": gates},
            "manifest_validation": {"valid": True, "manifest_sha256": manifest_hash},
            "profile_id": profile_id,
            "save_reload": {"structure_match": True}, "comsol_problems": [],
        },
    }
    path = tmp_path / "probe.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def _manifest(profile_id="example_heat2d_discovered"):
    return {
        "metadata": {"profile_id": profile_id, "task_id": "it-case",
                     "execution_limits": {"timeout_seconds": 60}},
        "study": {"tag": "std1", "label": "stationary", "run": True},
    }


def test_probe_binding_accepts_normalized_manifest_hash(tmp_path):
    m = _manifest()
    normalized = dict(m)
    normalized["study"] = dict(m["study"], run=False)
    probe_hash = controller.canonical_json_sha256(normalized)
    bound = controller.TaskController._verify_probe_evidence(
        _valid_probe(tmp_path, probe_hash), m, {"manifest_sha256": "raw"}
    )
    assert bound["gates"] == list("ABCDEFGH")
    assert bound["solve_executed"] is False


def test_probe_binding_rejects_wrong_hash_and_solving_report(tmp_path):
    m = _manifest()
    with pytest.raises(controller.ControllerError, match="Manifest"):
        controller.TaskController._verify_probe_evidence(
            _valid_probe(tmp_path, "wrong"), m, {"manifest_sha256": "raw"}
        )
    probe = _valid_probe(tmp_path, controller.canonical_json_sha256(dict(
        m, study=dict(m["study"], run=False)
    )))
    data = json.loads(probe.read_text(encoding="utf-8"))
    data["evidence"]["solve_executed"] = True
    probe.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(controller.ControllerError, match="non-solving"):
        controller.TaskController._verify_probe_evidence(probe, m, {"manifest_sha256": "raw"})


def test_integration_test_requires_confirm_solve(tmp_path, monkeypatch):
    m = _manifest()
    monkeypatch.setattr(controller, "load_and_validate", lambda path: (m, {"manifest_sha256": "raw"}))
    monkeypatch.setattr(controller, "load_profile", lambda pid, require_validated: {
        "verification": {"state": "discovered"}})
    with pytest.raises(controller.ControllerError, match="confirm-solve"):
        controller.TaskController().run_integration_test(
            tmp_path / "manifest.json", tmp_path / "out", tmp_path / "probe.json",
            confirm_solve=False,
        )


def test_cli_dispatches_integration_test(monkeypatch):
    seen = {}

    def fake(self, manifest, output, probe_report, **kwargs):
        seen.update(manifest=manifest, output=output, probe=probe_report, **kwargs)
        return {"status": "PASS"}

    monkeypatch.setattr(controller.TaskController, "run_integration_test", fake)
    assert cli.main([
        "integration-test", "manifest.json", "--output", "runs/it",
        "--probe-report", "probe.json", "--confirm-solve",
    ]) == 0
    assert seen["probe"] == "probe.json" and seen["confirm_solve"] is True


def test_production_run_still_rejects_unvalidated_profile(tmp_path):
    profile = tmp_path / "example.json"
    profile.write_text(json.dumps({
        "profile_id": "example", "comsol_version": "6.4",
        "verification": {"state": "discovered"},
    }), encoding="utf-8")
    with pytest.raises(ProfileError, match="not validated"):
        controller.load_profile("example", root=tmp_path, require_validated=True)
