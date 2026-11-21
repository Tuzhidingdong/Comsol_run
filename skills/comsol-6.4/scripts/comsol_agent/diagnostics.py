from __future__ import annotations

import re
from typing import Any


_RULES = [
    (
        "license_or_module",
        ("license", "licence", "checkout", "licensed module", "module is not available"),
        "COMSOL could not grant access to a required license feature or module.",
        [
            "Check the connected Client.modules() inventory.",
            "Confirm that the installed license includes the required COMSOL product/module.",
            "Do not remove required physics or substitute a different interface without scientific approval."
        ]
    ),
    (
        "unit_or_dimension",
        ("unit", "dimensionality", "dimension mismatch", "inconsistent dimensions"),
        "A quantity or expression may have incompatible or unsupported units.",
        [
            "Check the source quantity, declared unit and expected unit.",
            "Check expression dimensions and unit conversions before changing model settings."
        ]
    ),
    (
        "api_property_or_method",
        ("unknown property", "unknown method", "undefined property", "no such method", "method not found"),
        "A COMSOL API property or method name may not match the installed 6.4 API.",
        [
            "Keep the original COMSOL message and inspect the exact node type and property/method name.",
            "Run a minimal non-solving profile probe against COMSOL 6.4 before promoting the API call.",
            "Do not assume an API name from another COMSOL version is compatible."
        ]
    ),
    (
        "api_feature_or_type",
        ("unknown feature", "unknown type", "not a valid feature", "not supported for this feature"),
        "A COMSOL feature or API type may be unsupported for this node or version.",
        [
            "Inspect the parent node type and the exact feature/type expected by COMSOL 6.4.",
            "Use a minimal profile probe and retain the full server output."
        ]
    ),
    (
        "geometry_or_selection",
        ("geometry", "selection", "boundary entity", "domain entity", "geometric entity"),
        "The model geometry or entity selection may be incomplete or inconsistent.",
        [
            "Inspect the geometry build messages and the selected entity dimension/count.",
            "Recheck semantic selections after geometry regeneration.",
            "Do not persist or guess naked entity indices."
        ]
    ),
    (
        "mesh",
        ("mesh", "meshing", "element quality", "failed to create elements"),
        "The mesh operation or mesh statistics reported a problem.",
        [
            "Inspect the exact geometry and selection passed to the mesh sequence.",
            "Review mesh element count and quality evidence before changing mesh controls.",
            "Check whether the requested mesh operation is supported by the validated profile."
        ]
    ),
    (
        "solver_or_numerical",
        ("singular matrix", "nonlinear solver", "failed to find a solution", "no convergence", "convergence failure"),
        "The numerical solver did not complete or reported a convergence problem.",
        [
            "Inspect the original solver log, Study configuration and dependent-variable scaling.",
            "Review boundary/initial conditions and material parameters against the approved scientific specification.",
            "Do not tune physical inputs solely to force a solver or benchmark pass."
        ]
    ),
    (
        "memory_or_resource",
        ("out of memory", "memory limit", "insufficient memory", "not enough memory", "resource limit"),
        "The task may have exceeded its configured or available computational resources.",
        [
            "Inspect the Worker Job Object memory limit, system memory and model DOF/element evidence.",
            "Reduce resource demand only through an approved mesh/model plan; do not silently change the scientific problem."
        ]
    ),
    (
        "timeout_or_cancellation",
        ("timed out", "timeout", "cancelled", "canceled", "terminated"),
        "The operation may have exceeded its time budget or been cancelled.",
        [
            "Inspect the Controller timeout, graceful-cancel attempt and hard-termination fields.",
            "Check whether the Worker/Server process tree cleanup was verified before retrying."
        ]
    ),
    (
        "file_or_path",
        ("no such file", "file not found", "cannot open", "permission denied", "access is denied", "path"),
        "A file path, access permission or output location may be invalid.",
        [
            "Check the resolved absolute path and file permissions.",
            "Confirm that the output file does not already exist and that the source MPH remains unchanged."
        ]
    )
]


def classify_message(message: str) -> dict[str, Any]:
    """Classify common COMSOL/Python failures while preserving the original text."""
    raw = str(message)
    folded = raw.casefold()
    for category, needles, summary, checks in _RULES:
        if any(needle in folded for needle in needles):
            return {
                "category": category,
                "summary": summary,
                "suggested_checks": list(checks),
                "classification_confidence": "heuristic",
                "raw_message": raw
            }
    return {
        "category": "unclassified",
        "summary": "No reliable category could be inferred from this message.",
        "suggested_checks": [
            "Inspect the complete original COMSOL message and Python traceback.",
            "Inspect the task's pre-solve gate report, COMSOL problem list and Worker/Server logs.",
            "Do not apply an automated corrective change until the cause is established."
        ],
        "classification_confidence": "none",
        "raw_message": raw
    }


def classify_exception(
    exception: BaseException,
    traceback_text: str | None = None
) -> dict[str, Any]:
    message = str(exception)
    result = classify_message(message)
    result.update({
        "source": "worker_exception",
        "exception_type": type(exception).__name__,
        "raw_traceback": traceback_text
    })
    return result


def classify_problem_records(records: list[Any]) -> list[dict[str, Any]]:
    classified = []
    for index, original in enumerate(records):
        entry = classify_message(str(original))
        entry.update({
            "source": "comsol_model_problem",
            "index": index,
            "original_record": original
        })
        classified.append(entry)
    return classified
