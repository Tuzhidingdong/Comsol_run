"""Focused tests for declarative conservation checks and status independence."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from comsol_agent.executor import ExecutionError, ProfileExecutor
from comsol_agent.manifest import load_and_validate
from comsol_agent.report import build_execution_report


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


def test_manifest_schema_accepts_declarative_terms(tmp_path):
    # Use the real fixture manifest from the project to exercise schema + units.
    from pathlib import Path
    path = Path("runs/acceptance/physical_validation/manifest_conservation_probe.json")
    manifest, validation = load_and_validate(path)
    checks = manifest["validation"]["conservation_checks"]
    assert checks[0]["terms"][0]["expected_unit"] == "W/m"
    assert checks[0]["terms"][0]["region"]
    assert validation["valid"] is True


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
