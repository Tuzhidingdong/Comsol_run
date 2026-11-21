from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from comsol_agent.convergence import (
    ConvergenceError,
    compute_gci,
    derive_child_manifests,
    write_convergence_plan
)


def base_manifest():
    return {
        "metadata": {
            "schema_version": "1.0.0",
            "comsol_version": "6.4",
            "mode": "build",
            "task_id": "diffusion-study",
            "profile_id": "test-profile"
        },
        "parameters": {},
        "geometry": {"component_tag": "comp1", "geometry_tag": "geom1", "dimension": 1, "features": []},
        "selections": [],
        "materials": [],
        "physics": [],
        "mesh": {"tag": "mesh1", "component_tag": "comp1", "geometry_tag": "geom1", "profile_id": "test-profile"},
        "study": {"tag": "std1", "profile_id": "test-profile", "steps": [{"tag": "time", "api_type": "Transient"}]},
        "outputs": {"quantities": []},
        "validation": {"required_gates": list("ABCDEFGH")}
    }


def test_mesh_children_are_independent_and_parent_unchanged():
    parent = base_manifest()
    frozen = copy.deepcopy(parent)
    children = derive_child_manifests(parent, "mesh", [1.0, 0.7, 0.49])
    assert parent == frozen
    assert len({child["metadata"]["task_id"] for child in children}) == 3
    assert [item["mesh"]["refinement_factor"] for item in children] == [1.0, 0.7, 0.49]
    assert all(item["metadata"]["parent_task_id"] == "diffusion-study" for item in children)


def test_time_children_change_only_declared_time_scale():
    parent = base_manifest()
    children = derive_child_manifests(parent, "time", [1.0, 0.5, 0.25])
    assert [item["study"]["time_step_scale"] for item in children] == [1.0, 0.5, 0.25]
    assert all(item["mesh"] == parent["mesh"] for item in children)


def test_invalid_convergence_kind_fails():
    with pytest.raises(ConvergenceError):
        derive_child_manifests(base_manifest(), "parameter", [1.0, 0.5])


def test_gci_for_monotonic_equal_ratio_sequence():
    result = compute_gci([2.0, 1.25, 1.0625], [4.0, 2.0, 1.0])
    assert result["status"] == "CALCULATED"
    assert result["observed_order"] == pytest.approx(2.0)
    assert result["gci_fine_percent"] > 0


def test_gci_refuses_oscillatory_sequence():
    with pytest.raises(ConvergenceError, match="monotonically"):
        compute_gci([1.2, 0.9, 1.05], [4.0, 2.0, 1.0])


def test_gci_refuses_two_levels():
    with pytest.raises(ConvergenceError):
        compute_gci([2.0, 1.0], [2.0, 1.0])


def test_convergence_plan_writes_child_manifests(tmp_path: Path):
    out = write_convergence_plan(base_manifest(), "mesh", [1.0, 0.7, 0.49], tmp_path / "plan")
    index = json.loads((out / "child_tasks.json").read_text(encoding="utf-8"))
    assert len(index["children"]) == 3
    for child in index["children"]:
        assert Path(child["manifest"]).is_file()
