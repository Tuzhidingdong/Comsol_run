from __future__ import annotations

import math
from typing import Any, Iterator


class UnitValidationError(ValueError):
    pass


def _registry():
    try:
        import pint
    except ImportError as exc:
        raise UnitValidationError("Pint is required for dimensional validation. Install the project dependencies.") from exc
    return pint.UnitRegistry(autoconvert_offset_to_baseunit=True)


def validate_quantity(node: dict[str, Any], path: str = "quantity") -> dict[str, str]:
    if "value" not in node or "unit" not in node:
        raise UnitValidationError(f"{path}: dimensional values require both value and unit")
    value = node["value"]
    unit = node["unit"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise UnitValidationError(f"{path}: value must be a finite number")
    if not isinstance(unit, str) or not unit.strip():
        raise UnitValidationError(f"{path}: unit must be a non-empty string")
    registry = _registry()
    try:
        quantity = registry.Quantity(float(value), unit)
        _ = quantity.to_base_units()
        if node.get("expected_unit"):
            expected = registry.Unit(node["expected_unit"])
            if quantity.dimensionality != expected.dimensionality:
                raise UnitValidationError(
                    f"{path}: {unit!r} has dimensionality {quantity.dimensionality}, "
                    f"expected {node['expected_unit']!r} ({expected.dimensionality})"
                )
    except UnitValidationError:
        raise
    except Exception as exc:
        raise UnitValidationError(f"{path}: invalid or unsupported unit {unit!r}: {exc}") from exc
    return {"unit": unit, "dimensionality": str(quantity.dimensionality)}


def validate_expression(node: dict[str, Any], path: str = "expression") -> dict[str, str]:
    expression = node.get("expression")
    expected_unit = node.get("expected_unit")
    if not isinstance(expression, str) or not expression.strip():
        raise UnitValidationError(f"{path}: expression must be a non-empty string")
    if not isinstance(expected_unit, str) or not expected_unit.strip():
        raise UnitValidationError(f"{path}: expected_unit is required")
    try:
        expected = _registry().Unit(expected_unit)
    except Exception as exc:
        raise UnitValidationError(f"{path}: invalid expected_unit {expected_unit!r}: {exc}") from exc
    return {"expected_unit": expected_unit, "dimensionality": str(expected.dimensionality)}


def validate_compatible_units(units: list[str], path: str) -> str:
    if not units:
        raise UnitValidationError(f"{path}: at least one unit is required")
    registry = _registry()
    try:
        dimensions = [registry.Unit(unit).dimensionality for unit in units]
    except Exception as exc:
        raise UnitValidationError(f"{path}: invalid unit in {units!r}: {exc}") from exc
    if any(item != dimensions[0] for item in dimensions[1:]):
        raise UnitValidationError(f"{path}: terms must have compatible dimensions; got {dimensions}")
    return str(dimensions[0])


def iter_typed_values(value: Any, path: str = "$") -> Iterator[tuple[str, dict[str, Any]]]:
    if isinstance(value, dict):
        if "value" in value and "unit" in value:
            yield path, value
            return
        if "expression" in value and "expected_unit" in value:
            yield path, value
            return
        for key, child in value.items():
            yield from iter_typed_values(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_typed_values(child, f"{path}[{index}]")


def validate_manifest_units(manifest: dict[str, Any]) -> list[dict[str, str]]:
    evidence: list[dict[str, str]] = []
    errors: list[str] = []
    for path, node in iter_typed_values(manifest):
        try:
            if "value" in node:
                result = validate_quantity(node, path)
            else:
                result = validate_expression(node, path)
            evidence.append({"path": path, **result})
        except UnitValidationError as exc:
            errors.append(str(exc))

    for index, check in enumerate(manifest.get("validation", {}).get("conservation_checks", [])):
        try:
            dimensions = validate_compatible_units(
                [str(term["expected_unit"]) for term in check["terms"]],
                f"validation.conservation_checks[{index}].terms"
            )
            evidence.append({
                "path": f"validation.conservation_checks[{index}]",
                "dimensionality": dimensions
            })
        except (KeyError, TypeError, UnitValidationError) as exc:
            errors.append(str(exc))

    if errors:
        raise UnitValidationError("; ".join(errors))
    return evidence


def to_comsol_expression(node: dict[str, Any]) -> str:
    if "value" in node:
        validate_quantity(node)
        return f"{node['value']}[{node['unit']}]"
    if "expression" in node:
        validate_expression(node)
        return str(node["expression"])
    raise UnitValidationError("Expected a typed quantity or expression")
