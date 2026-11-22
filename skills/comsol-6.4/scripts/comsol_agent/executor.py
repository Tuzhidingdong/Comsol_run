from __future__ import annotations

import csv
import json
import math
import shutil
from pathlib import Path
from typing import Any

from .io_utils import sha256_file
from .profiles import load_profile
from .units import to_comsol_expression


class ExecutionError(RuntimeError):
    pass


READ_ONLY_METHODS = {
    "isEmpty", "isComplete", "getNumElem", "getMinQuality", "getAverageQuality",
    "getNEntities", "entities", "tags", "hasProduct", "isBuilt", "getType",
    "getString", "getStringArray", "getDouble", "getDoubleArray", "getInt",
    "getIntArray", "getBoolean", "getValue", "xmeshInfo", "nDofs", "getNDOF"
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
    """Execute a restricted, profile-declared COMSOL Java API action sequence."""

    ALLOWED = {
        "set_parameter", "create_component", "create_geometry",
        "create_geometry_feature", "bind_existing_node", "set_node_property",
        "run_geometry", "create_selection", "create_material",
        "set_material_property", "create_physics", "create_physics_feature",
        "create_mesh", "create_mesh_feature", "set_mesh_auto_size", "run_mesh",
        "create_study", "create_study_step", "create_auto_sequences",
        "create_plot_group", "create_plot_feature"
    }

    def __init__(
        self,
        client: Any,
        manifest: dict[str, Any],
        output_dir: str | Path,
        *,
        require_validated_profile: bool = True
    ):
        self.client = client
        self.manifest = manifest
        self.output_dir = Path(output_dir).resolve()
        self.require_validated_profile = bool(require_validated_profile)
        self.nodes: dict[str, Any] = {}
        self.model = None
        self.profile: dict[str, Any] | None = None
        self._loop_item: Any = None
        self.solver_sequence_created = False
        self.source_model: Path | None = None
        self.source_model_sha256: str | None = None
        self.source_copy: Path | None = None

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

    @staticmethod
    def _safe_model_tag(task_id: str) -> str:
        import re

        tag = re.sub(r"[^A-Za-z0-9_]", "_", str(task_id))
        if not tag or not tag[0].isalpha():
            tag = "model_" + tag
        return tag[:31]

    def _target(self, name: str) -> Any:
        if name == "model":
            return self.model.java
        if name == "client":
            return self.client.java
        if name not in self.nodes:
            raise ExecutionError(f"Unknown model-node handle: {name}")
        return self.nodes[name]

    def _bind_existing_node(self, args: dict[str, Any]) -> None:
        m = self.model.java
        node_type = args["node_type"]
        tag = args["tag"]
        component = args.get("component")
        parent_tag = args.get("parent_tag")
        if node_type == "component":
            node = m.component(tag)
        elif node_type == "geometry":
            node = m.component(component).geom(tag)
        elif node_type == "geometry_feature":
            node = m.component(component).geom(parent_tag).feature(tag)
        elif node_type == "selection":
            node = m.component(component).selection(tag)
        elif node_type == "material":
            node = m.component(component).material(tag)
        elif node_type == "physics":
            node = m.component(component).physics(tag)
        elif node_type == "physics_feature":
            node = m.component(component).physics(parent_tag).feature(tag)
        elif node_type == "mesh":
            node = m.component(component).mesh(tag)
        elif node_type == "mesh_feature":
            node = m.component(component).mesh(parent_tag).feature(tag)
        elif node_type == "study":
            node = m.study(tag)
        elif node_type == "solver":
            node = m.sol(tag)
        elif node_type == "plot_group":
            node = m.result(tag)
        elif node_type == "plot_feature":
            node = m.result(parent_tag).feature(tag)
        else:
            raise ExecutionError(f"Unsupported existing-node type: {node_type}")
        self.nodes[str(args["handle"])] = node

    def _load_patch_source(self) -> None:
        source = Path(self.manifest["metadata"]["source_model"]).expanduser().resolve()
        if not source.is_file() or source.suffix.lower() != ".mph":
            raise ExecutionError(f"Patch source must be an existing .mph file: {source}")
        self.source_model = source
        self.source_model_sha256 = sha256_file(source)
        copy_path = (self.output_dir / "source_model_copy.mph").resolve()
        if copy_path.exists():
            raise ExecutionError(f"Refusing to overwrite source model copy: {copy_path}")
        shutil.copy2(source, copy_path)
        if sha256_file(copy_path) != self.source_model_sha256:
            raise ExecutionError("Patch source copy failed SHA-256 integrity check")
        self.source_copy = copy_path
        self.model = self.client.load(str(copy_path))
        existing_solver_tags = list(self.model.java.sol().tags())
        if existing_solver_tags:
            self.solver_sequence_created = True
            for solver_tag in existing_solver_tags:
                self.nodes[f"solver:{solver_tag}"] = self.model.java.sol(solver_tag)

    def verify_source_unchanged(self) -> dict[str, Any] | None:
        if self.source_model is None:
            return None
        current_hash = sha256_file(self.source_model)
        result = {
            "source_model": str(self.source_model),
            "source_sha256_before": self.source_model_sha256,
            "source_sha256_after": current_hash,
            "source_unchanged": current_hash == self.source_model_sha256,
            "working_copy": str(self.source_copy) if self.source_copy else None
        }
        if not result["source_unchanged"]:
            raise ExecutionError("Original patch source MPH changed during execution")
        return result

    def run(self) -> dict[str, Any]:
        self.profile = load_profile(
            self.manifest["metadata"]["profile_id"],
            require_validated=self.require_validated_profile
        )
        required_modules = [str(value) for value in self.profile.get("required_modules", [])]
        available_modules = [str(value) for value in self.client.modules()]
        available_module_keys = {value.casefold() for value in available_modules}
        missing_modules = [
            module for module in required_modules
            if module.casefold() not in available_module_keys
        ]
        if missing_modules:
            raise ExecutionError(
                "The active COMSOL license does not report required profile modules: "
                + ", ".join(missing_modules)
            )
        self.licensed_modules = available_modules
        actions = self.profile.get("actions")
        if not isinstance(actions, list) or not actions:
            raise ExecutionError("Validated profile has no action sequence")
        invalid = [item.get("op") for item in actions if item.get("op") not in self.ALLOWED]
        if invalid:
            raise ExecutionError(f"Profile contains unsupported or unsafe actions: {invalid}")
        if self.manifest["metadata"]["mode"] == "patch":
            self._load_patch_source()
        else:
            self.model = self.client.create(
                self._safe_model_tag(self.manifest["metadata"]["task_id"])
            )
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
        source_integrity = self.verify_source_unchanged()
        return {
            "model": self.model, "profile": self.profile,
            "completed_actions": completed, "checkpoint": str(checkpoint),
            "source_integrity": source_integrity
        }

    def _execute(self, op: str, args: dict[str, Any]) -> None:
        m = self.model.java
        if op == "set_parameter":
            if "description" in args:
                m.param().set(args["name"], args["value"], args["description"])
            else:
                m.param().set(args["name"], args["value"])
        elif op == "bind_existing_node":
            self._bind_existing_node(args)
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
            target_name = str(args["target"])
            if target_name.startswith("solver:") and not self.solver_sequence_created:
                raise ExecutionError("Default solver sequence must be created before custom solver settings")
            self._target(target_name).set(args["property"], args["value"])
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
            # COMSOL 6.4 PhysicsFeatureListClient.create() overloads are
            # (String, String) and (String, String, int) -- never a String
            # dimension. Verified against the local 6.4 Server.
            node = parent.feature().create(args["tag"], args["api_type"], int(args["entity_dimension"]))
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
            study = self._target(args["study_handle"])
            study.createAutoSequences("all")
            self.solver_sequence_created = True
            for solver_tag in list(m.sol().tags()):
                self.nodes[f"solver:{solver_tag}"] = m.sol(solver_tag)
        elif op == "create_plot_group":
            tag = args["tag"]
            node = m.result().create(tag, args["api_type"])
            self.nodes[f"plot_group:{tag}"] = node
        elif op == "create_plot_feature":
            parent = self._target(args["plot_group_handle"])
            node = parent.feature().create(args["tag"], args["api_type"])
            for key, value in args.get("properties", {}).items():
                node.set(key, value)
            self.nodes[f"plot_feature:{args['tag']}"] = node
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
                expected = (
                    self._path_get(self.manifest, str(probe["expected_ref"]))
                    if "expected_ref" in probe else probe.get("expected")
                )
                passed = _compare(actual_plain, str(probe["operator"]), expected)
                check = {
                    "name": name, "passed": bool(passed), "actual": actual_plain,
                    "operator": probe["operator"], "expected": expected,
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

    def collect_comsol_problems(self) -> list[Any]:
        if self.model is None:
            raise ExecutionError("No active model")
        return _plain(self.model.problems()) or []

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
        if self.manifest.get("outputs", {}).get("export_csv", True) and scalar_rows:
            with results_path.with_suffix(".csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["name", "expression", "value", "unit"])
                writer.writerows(scalar_rows)
        return {"results": results, "results_json": str(results_path)}

    def run_image_exports(self) -> list[dict[str, Any]]:
        if not self.manifest.get("outputs", {}).get("export_images", False):
            return []
        exports = list((self.profile or {}).get("image_exports", []))
        if not exports:
            raise ExecutionError("Manifest requests image exports, but the validated profile declares no image_exports")
        image_root = (self.output_dir / "results" / "images").resolve()
        image_root.mkdir(parents=True, exist_ok=True)
        completed = []
        for item in exports:
            tag = str(item["tag"])
            filename = Path(str(item["filename"]))
            path = filename.resolve() if filename.is_absolute() else (image_root / filename).resolve()
            if image_root not in path.parents:
                raise ExecutionError(f"Image export path escapes its task output directory: {path}")
            if path.exists():
                raise ExecutionError(f"Refusing to overwrite image export: {path}")
            node = self.model.java.result().export().create(tag, str(item.get("api_type", "Image")))
            node.set("filename", str(path))
            if item.get("plotgroup"):
                node.set("plotgroup", str(item["plotgroup"]))
            for key, value in item.get("properties", {}).items():
                node.set(key, self._resolve(value))
            node.run()
            if not path.is_file() or path.stat().st_size == 0:
                raise ExecutionError(f"COMSOL image export did not create a non-empty file: {path}")
            completed.append({"tag": tag, "path": str(path), "size_bytes": path.stat().st_size})
        return completed

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

    def evaluate_conservation_checks(self) -> dict[str, Any] | None:
        checks = self.manifest.get("validation", {}).get("conservation_checks", [])
        if not checks:
            return None
        results = []
        for check in checks:
            term_values = []
            for term in check["terms"]:
                expression = str(term["expression"])
                scalar = _plain(self.model.evaluate(expression, term["expected_unit"]))
                if not isinstance(scalar, (int, float)) or not math.isfinite(float(scalar)):
                    raise ExecutionError(f"Conservation term {check['name']} returned non-finite/non-scalar data")
                coefficient = float(term.get("coefficient", 1.0))
                term_values.append({
                    "expression": expression, "value": float(scalar),
                    "coefficient": coefficient, "signed_value": coefficient * float(scalar),
                    "unit": term["expected_unit"]
                })
            balance = sum(item["signed_value"] for item in term_values)
            scale = sum(abs(item["signed_value"]) for item in term_values)
            residual = abs(balance) / max(scale, 1e-30)
            tolerance = float(check["relative_tolerance"])
            results.append({
                "name": check["name"], "balance": balance, "scale": scale,
                "relative_residual": residual, "relative_tolerance": tolerance,
                "passed": residual <= tolerance, "terms": term_values,
                "interpretation": "Signs and control-volume terms are supplied by the user-approved Manifest."
            })
        return {"passed": all(item["passed"] for item in results), "checks": results}
