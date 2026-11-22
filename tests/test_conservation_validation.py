"""Focused tests for declarative conservation checks and status independence."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from comsol_agent.executor import ExecutionError, ProfileExecutor
from comsol_agent.manifest import load_and_validate
from comsol_agent.report import build_execution_report
from comsol_agent.units import UnitValidationError


def make_executor(values):
    ex = ProfileExecutor(client=SimpleNamespace(java=object()), manifest={
        "validation": {"conservation_checks": []}
    }, output_dir=".")
    ex.profile = {}
    ex.model = SimpleNamespace(evaluate=lambda expr, unit: values[expr])
    return ex


def balance_manifest(coefficient_cold=1.0, tolerance=0.001):
    return {
        "name": "energy",
        "equation": "sum outward heat flux = 0",
        "terms": [
            {"expression": "int_hot(ht.ndflux)", "expected_unit": "W/m",
             "coefficient": 1.0, "region": "hot"},
            {"expression": "int_cold(ht.ndflux)", "expected_unit": "W/m",
             "coefficient": coefficient_cold, "region": "cold"},
        ],
        "relative_tolerance": tolerance,
    }


def test_signed_terms_and_residual():
    ex = make_executor({"int_hot(ht.ndflux)": -50.0, "int_cold(ht.ndflux)": 50.0})
    ex.manifest["validation"]["conservation_checks"] = [balance_manifest()]
    out = ex.evaluate_conservation_checks()
    check = out["checks"][0]
    assert check["passed"] is True
    assert check["balance"] == pytest.approx(0.0)
    assert check["scale"] == pytest.approx(100.0)
    assert check["relative_residual"] == pytest.approx(0.0)
    assert [t["signed_value"] for t in check["terms"]] == [-50.0, 50.0]
    assert check["terms"][1]["region"] == "cold"


def test_wrong_sign_coefficient_fails():
    ex = make_executor({"int_hot(ht.ndflux)": -50.0, "int_cold(ht.ndflux)": 50.0})
    ex.manifest["validation"]["conservation_checks"] = [balance_manifest(coefficient_cold=-1.0)]
    check = ex.evaluate_conservation_checks()["checks"][0]
    assert check["relative_residual"] == pytest.approx(1.0)
    assert check["passed"] is False


def test_zero_scale_and_nan_are_blocking():
    ex = make_executor({"int_hot(ht.ndflux)": 0.0, "int_cold(ht.ndflux)": 0.0})
    ex.manifest["validation"]["conservation_checks"] = [balance_manifest()]
    with pytest.raises(ExecutionError, match="zero or invalid power scale"):
        ex.evaluate_conservation_checks()
    ex.model = SimpleNamespace(evaluate=lambda expr, unit: float("nan"))
    with pytest.raises(ExecutionError, match="non-finite"):
        ex.evaluate_conservation_checks()


def declarative_manifest_fixture():
    """A complete, schema-valid Manifest built in memory (no runs/ dependency)."""
    return {
        "metadata": {
            "schema_version": "1.0.0", "comsol_version": "6.4",
            "mode": "build", "task_id": "fixture-conservation",
            "profile_id": "fixture-profile",
        },
        "parameters": {"k": {"value": 1.0, "unit": "W/(m*K)"}},
        "geometry": {
            "component_tag": "comp1", "geometry_tag": "geom1",
            "dimension": 2, "features": [],
        },
        "selections": [],
        "materials": [],
        "physics": [],
        "mesh": {
            "tag": "mesh1", "component_tag": "comp1",
            "geometry_tag": "geom1", "profile_id": "fixture-profile",
        },
        "study": {
            "tag": "std1", "profile_id": "fixture-profile",
            "steps": [{"tag": "stat", "api_type": "Stationary"}],
        },
        "outputs": {"quantities": []},
        "validation": {
            "required_gates": list("ABCDEFGH"),
            "conservation_checks": [balance_manifest()],
        },
    }


def _write_manifest(tmp_path, data, name="manifest.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_manifest_schema_accepts_declarative_terms(tmp_path):
    # Built in the test's own temporary directory: works in CI where runs/
    # is gitignored and absent.
    path = _write_manifest(tmp_path, declarative_manifest_fixture())
    manifest, validation = load_and_validate(path)
    checks = manifest["validation"]["conservation_checks"]
    assert checks[0]["terms"][0]["expected_unit"] == "W/m"
    assert checks[0]["terms"][0]["region"]
    assert validation["valid"] is True
    # Pint unit validation really ran on the typed parameter, not just schema.
    assert validation["typed_values_checked"] >= 1
    assert any(
        evidence["unit"] == "W/(m*K)" for evidence in validation["unit_evidence"]
    )


def test_manifest_rejects_invalid_conservation_unit(tmp_path):
    data = declarative_manifest_fixture()
    data["validation"]["conservation_checks"][0]["terms"][0]["expected_unit"] = "not-a-unit"
    path = _write_manifest(tmp_path, data, "invalid-unit.json")
    with pytest.raises(UnitValidationError, match="invalid expected_unit"):
        load_and_validate(path)


def test_report_keeps_four_states_independent(tmp_path):
    report = build_execution_report(
        task_id="t", job_id="t", output_dir=tmp_path,
        api_success=True, numerical_success=False,
        physical_validation=True, reproduction_success=None,
        status="NUMERICAL_SUCCESS_VALIDATION_PENDING", evidence={},
    )
    assert report["api_success"] is True
    assert report["numerical_success"] is False
    assert report["physical_validation"] is True
    assert report["reproduction_success"] is None
