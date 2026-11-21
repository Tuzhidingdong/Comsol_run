from __future__ import annotations

from types import SimpleNamespace

from comsol_agent.executor import ProfileExecutor
from comsol_agent.gates import evaluate_pre_solve_gates


class ProbeNode:
    def isComplete(self):
        return True

    def getNumElem(self):
        return 12

    def getMinQuality(self):
        return 0.35

    def getNEntities(self, dim):
        return 2 if dim == 2 else 0

    def run(self):
        raise AssertionError("Gate probes must never invoke mutating methods")


def make_executor(probes):
    executor = ProfileExecutor(client=SimpleNamespace(java=object()), manifest={}, output_dir=".")
    executor.model = SimpleNamespace(java=object())
    executor.profile = {"gate_probes": probes}
    executor.nodes = {"mesh:mesh1": ProbeNode(), "geometry:comp1/geom1": ProbeNode()}
    return executor


def test_live_read_only_gate_probes_generate_evidence():
    probes = [
        {"gate": "A", "name": "domain-count", "target": "geometry:comp1/geom1",
         "method_chain": [{"method": "getNEntities", "args": [2]}], "operator": "positive"},
        {"gate": "G", "name": "mesh-complete", "target": "mesh:mesh1",
         "method_chain": [{"method": "isComplete"}], "operator": "is_true"},
        {"gate": "G", "name": "element-count", "target": "mesh:mesh1",
         "method_chain": [{"method": "getNumElem"}], "operator": "gte", "expected": 1},
        {"gate": "G", "name": "mesh-quality", "target": "mesh:mesh1",
         "method_chain": [{"method": "getMinQuality"}], "operator": "gte", "expected": 0.2}
    ]
    evidence = make_executor(probes).collect_live_gate_evidence()
    assert evidence["A"]["checks"][0]["passed"] is True
    assert evidence["G"]["checks"][1]["actual"] == 12


def test_unknown_or_mutating_gate_method_fails_closed():
    probes = [
        {"gate": "A", "name": "attempt-mutation", "target": "mesh:mesh1",
         "method_chain": [{"method": "run"}], "operator": "is_true"}
    ]
    evidence = make_executor(probes).collect_live_gate_evidence()
    assert evidence["A"]["checks"][0]["passed"] is False
    assert "read-only allowlist" in evidence["A"]["checks"][0]["error"]


def test_missing_live_gate_probes_block_solve():
    required = list("ABCDEFGH")
    evidence = make_executor([
        {"gate": "A", "name": "count", "target": "geometry:comp1/geom1",
         "method_chain": [{"method": "getNEntities", "args": [2]}], "operator": "positive"}
    ]).collect_live_gate_evidence()
    report = evaluate_pre_solve_gates(required, evidence)
    assert report["status"] == "BLOCKED"
    assert report["solve_allowed"] is False
