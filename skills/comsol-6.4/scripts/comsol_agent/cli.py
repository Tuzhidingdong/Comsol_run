from __future__ import annotations

import argparse
import json
import sys

from .comsol import environment_report
from .controller import TaskController
from .convergence import aggregate_scalar_metrics, write_convergence_plan
from .manifest import load_and_validate
from .profiles import list_profiles


def _print(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="comsol-agent", description="COMSOL 6.4 Agent Skill controller")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="Inspect local Python and COMSOL installation without starting COMSOL")
    doctor.add_argument("--home")

    validate = sub.add_parser("validate", help="Validate a task Manifest and explicit units")
    validate.add_argument("manifest")

    m0 = sub.add_parser("m0", help="Run the local COMSOL 6.4 feasibility smoke test")
    m0.add_argument("--output", default="runs/m0")
    m0.add_argument("--timeout", type=int, default=300)

    run = sub.add_parser("run", help="Run one approved Manifest in an isolated Worker")
    run.add_argument("manifest")
    run.add_argument("--output", default="runs")
    run.add_argument("--timeout", type=int)

    sub.add_parser("profiles", help="List available COMSOL 6.4 API profiles")

    plan = sub.add_parser("convergence-plan", help="Derive independent child Manifests for a convergence audit")
    plan.add_argument("manifest")
    plan.add_argument("--kind", choices=["mesh", "time"], required=True)
    plan.add_argument("--levels", nargs="+", type=float, required=True)
    plan.add_argument("--output", required=True)

    execute = sub.add_parser("convergence-run", help="Run/resume all independent child tasks in a convergence plan")
    execute.add_argument("plan_dir")
    execute.add_argument("--metric", default="target")
    execute.add_argument("--timeout", type=int)

    aggregate = sub.add_parser("convergence-aggregate", help="Aggregate scalar metrics from completed child runs")
    aggregate.add_argument("parent_dir")
    aggregate.add_argument("--metric", default="target")

    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            report = environment_report(args.home)
            _print(report)
            return 0 if report.get("ready_for_managed_windows_run") else 1
        if args.command == "validate":
            _, report = load_and_validate(args.manifest)
            report["profile_inventory"] = list_profiles()
            _print(report)
            return 0
        if args.command == "m0":
            result = TaskController().run_m0(args.output, args.timeout)
            _print(result)
            return 0 if result["status"] == "PASS" else 2
        if args.command == "run":
            result = TaskController().run_manifest(args.manifest, args.output, args.timeout)
            _print(result)
            return 0 if result["status"] == "PASS" else 2
        if args.command == "profiles":
            _print(list_profiles())
            return 0
        if args.command == "convergence-plan":
            manifest, _ = load_and_validate(args.manifest)
            out = write_convergence_plan(manifest, args.kind, args.levels, args.output)
            print(str(out))
            return 0
        if args.command == "convergence-run":
            result = TaskController().run_convergence_plan(args.plan_dir, args.metric, args.timeout)
            _print(result)
            return 0 if result["status"] == "PASS" else 2
        if args.command == "convergence-aggregate":
            result = aggregate_scalar_metrics(args.parent_dir, args.metric)
            _print(result)
            return 0 if result["status"] == "READY_FOR_CONVERGENCE_ANALYSIS" else 2
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
