from __future__ import annotations

import json
from pathlib import Path

from comsol_agent.io_utils import atomic_write_json, canonical_json_sha256, safe_task_id
from comsol_agent.report import build_execution_report, write_report


def test_atomic_json_write(tmp_path: Path):
    path = atomic_write_json(tmp_path / "nested" / "data.json", {"b": 2, "a": 1})
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1, "b": 2}


def test_canonical_hash_is_order_independent():
    assert canonical_json_sha256({"a": 1, "b": 2}) == canonical_json_sha256({"b": 2, "a": 1})


def test_task_id_rejects_path_traversal():
    import pytest
    with pytest.raises(ValueError):
        safe_task_id("../unsafe")


def test_execution_report_keeps_independent_null_states(tmp_path: Path):
    report = build_execution_report(
        task_id="case-001", job_id="job-001", output_dir=tmp_path,
        api_success=True, numerical_success=True,
        physical_validation=None, reproduction_success=None,
        status="NUMERICAL_ONLY"
    )
    write_report(tmp_path, report)
    restored = json.loads((tmp_path / "execution_report.json").read_text(encoding="utf-8"))
    assert restored["api_success"] is True
    assert restored["numerical_success"] is True
    assert restored["physical_validation"] is None
    assert restored["reproduction_success"] is None
