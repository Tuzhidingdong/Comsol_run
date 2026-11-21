from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from .profiles import load_profile
from .units import to_comsol_expression


class ExecutionError(RuntimeError):
    pass


READ_ONLY_METHODS = {
    "isEmpty", "isComplete", "getNumElem", "getMinQuality", "getAverageQuality",
    "getNEntities", "entities", "tags", "hasProduct", "isBuilt", "getType",
    "getString", "getStringArray", "getDouble", "getDoubleArray", "getInt",
    "getIntArray", "getBoolean", "getValue"
}


def _plain(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "tolist"):
        return _plain(value.tolist())
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    try:
        return float(value)
    except Exception:
        return str(value)


def _compare(actual: Any, operator: str, expected: Any = None) -> bool:
    if operator == "equals":
        return actual == expected
    if operator == "is_true":
        return actual is True or str(actual).lower() == "true"
    if operator == "non_empty":
        try:
            return len(actual) > 0
        except TypeError:
            return actual is not None
    if operator == "positive":
        return float(actual) > 0
    if operator == "gte":
        return float(actual) >= float(expected)
    if operator == "lte":
        return float(actual) <= float(expected)
    if operator == "contains":
        return expected in actual
    raise ExecutionError(f"Unsupported gate comparison operator: {operator}")


class ProfileExecutor:
    """Execute a restricted, profile-declared COMSOL Java action sequence."""

    ALLOWED = {
        "set_parameter", "create_component", "create_geometry",
        "create_geometry_feature", "set_node_property", "run_geometry",
        "create_selection", "create_material", "set_material_property",
        "create_physics", "create_physics_feature", "create_mesh",
        "create_mesh_feature", "set_mesh_auto_size", "run_mesh",
        "create_study", "create_study_step", "create_auto_sequences"
    }

    def __init__(self, client: Any, manifest: dict[str, Any], output_dir: str | Path):
        self.client = client
        self.manifest = manifest
        self.output_dir = Path(output_dir).resolve()
        self.nodes: dict[str, Any] = {}
        self.model = None
        self.profile: dict[str, Any] | None = None
        self._loop_item: Any = None

    @staticmethod
    def _path_get(root: Any, dotted: str) -> Any:
        current = root
        for part in dotted.split("."):
            current = current[int(part)] if isinstance(current, list) else current[part]
        return current

    def _resolve(self, value: Any) -> Any:
        if isinstance(value, dict):
            if set(value) == {"manifest_ref"}:
                return self._resolve(self._path_get(self.manifest, str(value["manifest_ref"])))
            if set(value) == {"item_ref"}:
                if self._loop_item is None:
                    raise ExecutionError("item_ref can only be used inside a for_each profile action")
                return self._resolve(self._path_get(self._loop_item, str(value["item_ref"])))
            if set(value) == {"parameter_ref"}:
                return to_comsol_expression(self.manifest["parameters"][str(value["parameter_ref"])])
            if set(value) == {"quantity"}:
                return to_comsol_expression(value["quantity"])
            if "value" in value and "unit" in value:
                return to_comsol_expression(value)
            if "expression" in value and "expected_unit" in value:
                return str(value["expression"])
            return {key: self._resolve(child) for key, child in value.items()}
        if isinstance(value, list):
            return [self._resolve(child) for child in value]
        return value

    def _target(self, name: str) -> Any:
        if name == "model":
            return self.model.java
        if name == "client":
            return self.client.java
        if name not in self.nodes:
            raise ExecutionError(f"Unknown model-node handle: {name}")
        return self.nodes[name]

    def run(self) -> dict[str, Any]:
        self.profile = load_profile(self.manifest["metadata"]["profile_id"], require_validated=True)
        actions = self.profile.get("actions")
        if not isinstance(actions, list) or not actions:
            raise ExecutionError("Validated profile has no action sequence")
        invalid = [item.get("op") for item in actions if item.get("op") not in self.ALLOWED]
        if invalid:
            raise ExecutionError(f"Profile contains unsupported or unsafe actions: {invalid}")
        if self.manifest["metadata"]["mode"] != "build":
            raise ExecutionError("Patch mode is not enabled in this implementation")
        self.model = self.client.create(self.manifest["metadata"]["task_id"][:31])
        completed = []
        for index, action in enumerate(actions):
            if "for_each" in action:
                iterable = self._path_get(self.manifest, str(action["for_each"]))
                if not isinstance(iterable, list):
                    raise ExecutionError(f"Profile for_each target is not a list: {action['for_each']}")
                for item_index, item in enumerate(iterable):
                    self._loop_item = item
                    self._execute(action["op"], self._resolve(action.get("args", {})))
                    completed.append({"index": index, "item_index": item_index, "op": action["op"], "status": "completed"})
                self._loop_item = None
            else:
                self._execute(action["op"], self._resolve(action.get("args", {})))
                completed.append({"index": index, "op": action["op"], "status": "completed"})
        checkpoint = (self.output_dir / "pre_solve_model.mph").resolve()
        if checkpoint.exists():
            raise ExecutionError(f"Refusing to overwrite checkpoint: {checkpoint}")
        self.model.save(str(checkpoint))
        if not checkpoint.is_file() or checkpoint.stat().st_size == 0:
            raise ExecutionError("Pre-solve MPH checkpoint was not created or is empty")
        return {"model": self.model, "profile": self.profile, "completed_actions": completed, "checkpoint": str(checkpoint)}

    def _execute(self, op: str, args: dict[str, Any]) -> None:
        m = self.model.java
        if op == "set_parameter":
            if "description" in args:
                m.param().set(args["name"], args["value"], args["description"])
            else:
                m.param().set(args["name"], args["value"])
        elif op == "create_component":
            tag = args["tag"]
            m.component().create(tag, bool(args.get("create_geometry", True)))
            self.nodes[f"component:{tag}"] = m.component(tag)
        elif op == "create_geometry":
            comp, tag = args["component"], args["tag"]
            self.nodes[f"geometry:{comp}/{tag}"] = m.component(comp).geom().create(tag, int(args["dimension"]))
        elif op == "create_geometry_feature":
            parent = self._target(args["geometry_handle"])
            node = parent.feature().create(args["tag"], args["api_type"])
            self.nodes[f"geometry_feature:{args['tag']}"] = node
            for key, value in args.get("properties", {}).items():
                node.set(key, value)
        elif op == "set_node_property":
            self._target(args["target"]).set(args["property"], args["value"])
        elif op == "run_geometry":
            self._target(args["target"]).run()
        elif op == "create_selection":
            comp, tag = args["component"], args["tag"]
            node = m.component(comp).selection().create(tag, args["selection_type"])
            node.geom(args["geometry"], int(args["entity_dimension"]))
            for key, value in args.get("properties", {}).items():
                node.set(key, value)
            self.nodes[f"selection:{tag}"] = node
        elif op == "create_material":
            comp, tag = args["component"], args["tag"]
            node = m.component(comp).material().create(tag, args.get("material_type", "Common"))
            if args.get("selection"):
                node.selection().named(args["selection"])
            self.nodes[f"material:{tag}"] = node
        elif op == "set_material_property":
            self._target(args["target"]).propertyGroup(args.get("group", "def")).set(args["property"], args["value"])
        elif op == "create_physics":
            comp, tag = args["component"], args["tag"]
            node = m.component(comp).physics().create(tag, args["api_type"], args["geometry"])
            if args.get("selection"):
                node.selection().named(args["selection"])
            self.nodes[f"physics:{tag}"] = node
        elif op == "create_physics_feature":
            parent = self._target(args["physics_handle"])
            node = parent.feature().create(args["tag"], args["api_type"], str(args["entity_dimension"]))
            if args.get("selection"):
                node.selection().named(args["selection"])
            for key, value in args.get("properties", {}).items():
                node.set(key, value)
            self.nodes[f"physics_feature:{args['tag']}"] = node
        elif op == "create_mesh":
            comp, tag = args["component"], args["tag"]
            self.nodes[f"mesh:{tag}"] = m.component(comp).mesh().create(tag, args["geometry"])
        elif op == "create_mesh_feature":
            parent = self._target(args["mesh_handle"])
            node = parent.feature().create(args["tag"], args["api_type"])
            for key, value in args.get("properties", {}).items():
                node.set(key, value)
            self.nodes[f"mesh_feature:{args['tag']}"] = node
        elif op == "set_mesh_auto_size":
            self._target(args["target"]).autoMeshSize(int(args["size"]))
        elif op == "run_mesh":
            self._target(args["target"]).run()
        elif op == "create_study":
            tag = args["tag"]
            self.nodes[f"study:{tag}"] = m.study().create(tag)
        elif op == "create_study_step":
            parent = self._target(args["study_handle"])
            self.nodes[f"study_step:{args['tag']}"] = parent.create(args["tag"], args["api_type"])
        elif op == "create_auto_sequences":
            self._target(args["study_handle"]).createAutoSequences("all")
        else:
            raise ExecutionError(f"Unimplemented operation: {op}")

    def collect_live_gate_evidence(self) -> dict[str, Any]:
        if self.profile is None or self.model is None:
            raise ExecutionError("Model and validated profile are required before gate collection")
        grouped: dict[str, list[dict[str, Any]]] = {}
        probes = self.profile.get("gate_probes", [])
        if not isinstance(probes, list):
            raise ExecutionError("Profile gate_probes must be an array")
        for index, probe in enumerate(probes):
            gate = str(probe.get("gate", ""))
            name = str(probe.get("name", f"probe-{index + 1}"))
            try:
                actual = self._target(str(probe["target"]))
                chain = probe.get("method_chain", [])
                if not isinstance(chain, list) or not chain:
                    raise ExecutionError("method_chain must contain at least one read-only method")
                for step in chain:
                    method_name = str(step.get("method", ""))
                    if method_name not in READ_ONLY_METHODS:
                        raise ExecutionError(f"Method {method_name!r} is not on the read-only probe allowlist")
                    method = getattr(actual, method_name)
                    if not callable(method):
                        raise ExecutionError(f"Probe attribute {method_name!r} is not callable")
                    actual = method(*step.get("args", []))
                actual_plain = _plain(actual)
                passed = _compare(actual_plain, str(probe["operator"]), probe.get("expected"))
                check = {
                    "name": name, "passed": bool(passed), "actual": actual_plain,
                    "operator": probe["operator"], "expected": probe.get("expected"),
                    "source": "live_comsol_6.4_api_probe"
                }
            except Exception as exc:
                check = {
                    "name": name, "passed": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "source": "live_comsol_6.4_api_probe"
                }
            grouped.setdefault(gate, []).append(check)
        return {gate: {"checks": checks} for gate, checks in grouped.items()}

    def execute_study(self) -> None:
        self.model.solve(self.manifest["study"]["tag"])

    def extract_outputs(self) -> dict[str, Any]:
        if self.profile is None or self.model is None:
            raise ExecutionError("No active model/profile")
        evaluations = list(self.profile.get("result_evaluations", []))
        evaluations.extend(self.manifest.get("outputs", {}).get("quantities", []))
        results: dict[str, Any] = {}
        for item in evaluations:
            name = str(item["name"])
            expression = str(item["expression"])
            unit = item.get("expected_unit")
            raw = self.model.evaluate(expression, unit) if unit else self.model.evaluate(expression)
            value = _plain(raw)
            results[name] = {"expression": expression, "value": value, "expected_unit": unit}
        results_path = (self.output_dir / "results" / "quantities.json").resolve()
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_path.write_text(json.dumps(results, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        scalar_rows = []
        for name, item in results.items():
            value = item["value"]
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                scalar_rows.append((name, item["expression"], value, item.get("expected_unit") or ""))
        if scalar_rows:
            with results_path.with_suffix(".csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["name", "expression", "value", "unit"])
                writer.writerows(scalar_rows)
        return {"results": results, "results_json": str(results_path)}

    def compare_benchmark(self, results: dict[str, Any]) -> dict[str, Any] | None:
        baseline = self.manifest.get("validation", {}).get("baseline", {})
        if not baseline:
            return None
        checks = []
        for name, specification in baseline.items():
            if name not in results:
                checks.append({"name": name, "passed": False, "error": "Result not extracted"})
                continue
            actual = results[name]["value"]
            reference = float(specification["reference_value"])
            tolerance = float(specification["relative_tolerance"])
            if not isinstance(actual, (int, float)) or not math.isfinite(float(actual)):
                passed, relative_error = False, None
            else:
                relative_error = abs(float(actual) - reference) / max(abs(reference), 1e-30)
                passed = relative_error <= tolerance
            checks.append({
                "name": name, "actual": actual, "reference_value": reference,
                "relative_error": relative_error, "relative_tolerance": tolerance, "passed": passed
            })
        return {"passed": all(check["passed"] for check in checks), "checks": checks}
