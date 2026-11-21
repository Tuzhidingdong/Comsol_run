from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from comsol_agent.manifest import ManifestError, load_and_validate, validate_manifest
from comsol_agent.units import UnitValidationError


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "examples" / "manifests" / "manifest-template.json"


def load_template():
    return json.loads(TEMPLATE.read_text(encoding="utf-8"))


def test_manifest_template_is_schema_valid():
    manifest, report = load_and_validate(TEMPLATE)
    assert report["valid"] is True
    assert report["comsol_version"] == "6.4"
    assert report["typed_values_checked"] >= 2
    assert manifest["metadata"]["mode"] == "build"


def test_wrong_comsol_version_is_rejected():
    manifest = load_template()
    manifest["metadata"]["comsol_version"] = "6.3"
    with pytest.raises(ManifestError):
        validate_manifest(manifest)


def test_patch_requires_absolute_source_path():
    manifest = load_template()
    manifest["metadata"]["mode"] = "patch"
    manifest["metadata"]["source_model"] = "relative/source.mph"
    with pytest.raises(ManifestError, match="absolute path"):
        validate_manifest(manifest)


def test_invalid_unit_is_rejected():
    manifest = load_template()
    manifest["parameters"]["length"]["unit"] = "not_a_real_unit_abc"
    with pytest.raises(UnitValidationError):
        validate_manifest(manifest)


def test_dimensional_mismatch_is_rejected():
    manifest = load_template()
    manifest["parameters"]["length"]["expected_unit"] = "s"
    with pytest.raises(UnitValidationError, match="dimensionality"):
        validate_manifest(manifest)


def test_non_finite_quantity_is_rejected():
    manifest = load_template()
    manifest["parameters"]["length"]["value"] = float("inf")
    with pytest.raises(UnitValidationError):
        validate_manifest(manifest)


def test_manifest_hash_is_stable():
    first = load_template()
    second = copy.deepcopy(first)
    assert validate_manifest(first)["manifest_sha256"] == validate_manifest(second)["manifest_sha256"]


def test_all_eight_pre_solve_gates_are_mandatory():
    manifest = load_template()
    manifest["validation"]["required_gates"] = ["A", "B"]
    with pytest.raises(ManifestError):
        validate_manifest(manifest)
