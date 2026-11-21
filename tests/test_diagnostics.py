from __future__ import annotations

from comsol_agent.diagnostics import (
    classify_exception,
    classify_message,
    classify_problem_records
)


def test_license_error_is_classified_and_original_message_is_preserved():
    message = "License checkout failed for AC/DC Module (COMSOL server message 42)"
    result = classify_message(message)
    assert result["category"] == "license_or_module"
    assert result["raw_message"] == message
    assert result["classification_confidence"] == "heuristic"
    assert result["suggested_checks"]


def test_unknown_message_is_not_given_a_fabricated_category():
    message = "Unexpected COMSOL internal exception code 987654"
    result = classify_message(message)
    assert result["category"] == "unclassified"
    assert result["classification_confidence"] == "none"
    assert result["raw_message"] == message


def test_exception_keeps_exact_message_and_traceback():
    error = RuntimeError("Unknown property 'rho_user' for material")
    trace = "Traceback line 1\nOriginal COMSOL Java exception"
    result = classify_exception(error, trace)
    assert result["exception_type"] == "RuntimeError"
    assert result["raw_message"] == str(error)
    assert result["raw_traceback"] == trace
    assert result["category"] == "api_property_or_method"


def test_comsol_problem_records_are_preserved_verbatim():
    records = [
        "Mesh failed to create elements for domain 2",
        {"message": "Singular matrix in stationary solver", "tag": "sol1"}
    ]
    result = classify_problem_records(records)
    assert [item["original_record"] for item in result] == records
    assert result[0]["category"] == "mesh"
    assert result[1]["category"] == "solver_or_numerical"
    assert result[1]["raw_message"] == str(records[1])
