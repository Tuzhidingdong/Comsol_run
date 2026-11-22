from __future__ import annotations

from types import SimpleNamespace

from comsol_agent.executor import ProfileExecutor


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
    assert "read-only probe allowlist" in evidence["A"]["checks"][0]["error"]


def test_gate_expected_reference_uses_manifest_values():
    executor = ProfileExecutor(client=SimpleNamespace(java=object()), manifest={
        "metadata": {"execution_limits": {"max_dofs": 1000}}
    }, output_dir=".")
    executor.model = SimpleNamespace(java=object())
    executor.profile = {"gate_probes": [{
        "gate": "H", "name": "dof-budget", "target": "solver:sol1",
        "method_chain": [{"method": "nDofs"}],
        "operator": "lte", "expected_ref": "metadata.execution_limits.max_dofs"
    }]}
    class DofNode:
        def nDofs(self):
            return 850
    executor.nodes = {"solver:sol1": DofNode()}
    evidence = executor.collect_live_gate_evidence()
    assert evidence["H"]["checks"][0]["passed"] is True
    assert evidence["H"]["checks"][0]["expected"] == 1000


class FakeDofFeature:
    def __init__(self):
        self.clear_count = 0

    def xmeshInfo(self):
        return self

    def nDofs(self):
        return 763

    def fieldNames(self):
        return ["comp1.T"]

    def fieldNDofs(self):
        return [763]

    def clearXmesh(self):
        self.clear_count += 1


def make_solver_executor():
    feature = FakeDofFeature()

    class Study:
        def createAutoSequences(self, value):
            assert value == "all"

    class SolverList:
        def tags(self):
            return ["sol1"]

    class Solver:
        def feature(self, tag=None):
            if tag is None:
                return SimpleNamespace(tags=lambda: ["st1", "v1"])
            assert tag == "st1"
            return feature

    class JavaModel:
        def sol(self, tag=None):
            return Solver() if tag else SolverList()

    model = SimpleNamespace(java=JavaModel())
    executor = ProfileExecutor(client=SimpleNamespace(java=object()), manifest={
        "metadata": {"execution_limits": {"max_dofs": 1000}}
    }, output_dir=".")
    executor.model = model
    executor.nodes = {"study:std1": Study()}
    return executor, feature


def test_auto_sequences_bind_study_step_feature_for_gate_h():
    executor, feature = make_solver_executor()
    executor._execute("create_auto_sequences", {"study_handle": "study:std1"})
    assert "solver:sol1" in executor.nodes
    assert "solver_feature:sol1/st1" in executor.nodes

    executor.profile = {"gate_probes": [{
        "gate": "H", "name": "dof-budget", "target": "solver_feature:sol1/st1",
        "method_chain": [{"method": "xmeshInfo"}, {"method": "nDofs"}],
        "operator": "lte", "expected_ref": "metadata.execution_limits.max_dofs"
    }]}
    evidence = executor.collect_live_gate_evidence()
    check = evidence["H"]["checks"][0]
    assert check["passed"] is True
    assert check["actual"] == 763
    assert check["expected"] == 1000

    cleanup = executor.release_xmesh_info()
    assert "solver_feature:sol1/st1" in cleanup["released"]
    assert cleanup["errors"] == []
    assert feature.clear_count == 1


def test_missing_live_gate_probes_block_solve():
    from comsol_agent.gates import evaluate_pre_solve_gates
    required = list("ABCDEFGH")
    evidence = make_executor([
        {"gate": "A", "name": "count", "target": "geometry:comp1/geom1",
         "method_chain": [{"method": "getNEntities", "args": [2]}], "operator": "positive"}
    ]).collect_live_gate_evidence()
    report = evaluate_pre_solve_gates(required, evidence)
    assert report["status"] == "BLOCKED"
    assert report["solve_allowed"] is False
