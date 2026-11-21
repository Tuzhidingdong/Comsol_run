from __future__ import annotations

import os

import pytest

from comsol_agent.controller import TaskController


@pytest.mark.skipif(os.name != "nt", reason="COMSOL 6.4 local acceptance requires Windows")
@pytest.mark.skipif(os.environ.get("COMSOL_AGENT_RUN_M0") != "1", reason="Set COMSOL_AGENT_RUN_M0=1 to launch local COMSOL Server")
def test_local_comsol_m0(tmp_path):
    result = TaskController().run_m0(tmp_path / "m0", timeout_seconds=300)
    assert result["status"] == "PASS"
