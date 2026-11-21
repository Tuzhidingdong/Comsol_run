from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .io_utils import canonical_json_sha256, safe_task_id
from .units import validate_manifest_units

SKILL_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = SKILL_ROOT / "schemas" / "task-manifest.schema.json"


class ManifestError(ValueError):
    pass


def load_schema(path: str | Path | None = None) -> dict[str, Any]:
    schema_path = Path(path).resolve() if path else SCHEMA_PATH
    with schema_path.open("r", encoding="utf-8") as stream:
        schema = json.load(stream)
    Draft202012Validator.check_schema(schema)
    return schema


def validate_manifest(data: dict[str, Any], schema_path: str | Path | None = None) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ManifestError("Manifest root must be a JSON object")
    schema = load_schema(schema_path)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(data),
        key=lambda error: tuple(str(part) for part in error.absolute_path)
    )
    if errors:
        details = []
        for error in errors[:20]:
            location = "$" + "".join(
                f"[{part}]" if isinstance(part, int) else f".{part}"
                for part in error.absolute_path
            )
            details.append(f"{location}: {error.message}")
        raise ManifestError("Manifest schema validation failed:\n- " + "\n- ".join(details))
    try:
        safe_task_id(data["metadata"]["task_id"])
        if data["metadata"]["comsol_version"] != "6.4":
            raise ManifestError("Only COMSOL 6.4 is supported by this initial release")
        if data["metadata"]["mode"] == "patch":
            source = Path(data["metadata"]["source_model"]).expanduser()
            if not source.is_absolute():
                raise ManifestError("patch mode source_model must be an absolute path")
    except (KeyError, TypeError) as exc:
        raise ManifestError(f"Invalid manifest metadata: {exc}") from exc
    unit_evidence = validate_manifest_units(data)
    return {
        "valid": True,
        "task_id": data["metadata"]["task_id"],
        "mode": data["metadata"]["mode"],
        "comsol_version": data["metadata"]["comsol_version"],
        "manifest_sha256": canonical_json_sha256(data),
        "typed_values_checked": len(unit_evidence),
        "unit_evidence": unit_evidence,
        "profile_validation": "NOT_CHECKED_BY_SCHEMA"
    }


def load_and_validate(path: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    source = Path(path).expanduser().resolve()
    with source.open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    return data, validate_manifest(data)
