from __future__ import annotations

import os
from pathlib import Path

import pytest

from comsol_agent.process_manager import verify_job_object_process_tree


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object test")
@pytest.mark.skipif(os.environ.get("COMSOL_AGENT_RUN_JOB_TESTS") != "1", reason="Set COMSOL_AGENT_RUN_JOB_TESTS=1 to run process containment test")
def test_job_object_kills_worker_and_descendant(tmp_path: Path):
    result = verify_job_object_process_tree(tmp_path / "job-probe", timeout_seconds=2)
    assert result["status"] == "PASS"
    assert result["all_owned_processes_terminated"] is True
    assert result["unrelated_process_survived_job_termination"] is True
