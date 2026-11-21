from __future__ import annotations

from comsol_agent import cli


def test_profile_probe_cli_dispatches_to_controller(monkeypatch, capsys):
    seen = {}

    class FakeController:
        def run_profile_probe(self, manifest, output, timeout):
            seen.update({"manifest": manifest, "output": output, "timeout": timeout})
            return {"status": "PASS", "task_id": "case-001"}

    monkeypatch.setattr(cli, "TaskController", FakeController)
    exit_code = cli.main([
        "profile-probe", "manifest.json",
        "--output", "runs/profile-probes",
        "--timeout", "321"
    ])
    assert exit_code == 0
    assert seen == {
        "manifest": "manifest.json",
        "output": "runs/profile-probes",
        "timeout": 321
    }
    assert '"status": "PASS"' in capsys.readouterr().out


def test_profile_probe_cli_returns_nonzero_when_probe_is_blocked(monkeypatch):
    class FakeController:
        def run_profile_probe(self, manifest, output, timeout):
            return {"status": "BLOCKED"}

    monkeypatch.setattr(cli, "TaskController", FakeController)
    exit_code = cli.main(["profile-probe", "manifest.json"])
    assert exit_code == 2
