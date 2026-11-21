from comsol_agent.gates import evaluate_pre_solve_gates, require_solve_permission


def test_missing_gate_evidence_blocks_solve():
    result = evaluate_pre_solve_gates(["A", "B"], {"A": {"checks": [{"name": "geometry", "passed": True}]}})
    assert result["status"] == "BLOCKED"
    assert result["solve_allowed"] is False
    assert result["gates"]["B"]["status"] == "BLOCKED"


def test_failed_check_blocks_solve():
    evidence = {"A": {"checks": [{"name": "geometry-build", "passed": False}]}}
    result = evaluate_pre_solve_gates(["A"], evidence)
    assert result["status"] == "BLOCKED"
    assert result["solve_allowed"] is False


def test_approval_gate_does_not_pass_automatically():
    evidence = {"A": {"requires_approval": True, "checks": [{"name": "budget-override", "passed": True}]}}
    result = evaluate_pre_solve_gates(["A"], evidence)
    assert result["status"] == "REQUIRES_APPROVAL"
    assert result["solve_allowed"] is False


def test_all_explicit_checks_pass():
    evidence = {
        key: {"checks": [{"name": f"{key}-check", "passed": True, "evidence": "unit-test"}]}
        for key in "ABCDEFGH"
    }
    result = evaluate_pre_solve_gates(list("ABCDEFGH"), evidence)
    assert result["status"] == "PASS"
    assert result["solve_allowed"] is True
    require_solve_permission(result)
