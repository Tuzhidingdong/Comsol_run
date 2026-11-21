# COMSOL Agent Skill — COMSOL 6.4

A Windows-first, agent-oriented COMSOL automation framework with a reviewed task manifest, isolated Worker execution, live pre-solve gates and scientific result reporting.

Target: COMSOL Multiphysics 6.4, Windows 64-bit, Python 3.10–3.13, MPh 1.4.x.

> Current delivery status is recorded in STATUS.md. Repository code and unit tests do not prove local COMSOL compatibility. Run the local acceptance procedure before using this against research models.

## Quick start

1. Install COMSOL Multiphysics 6.4 and confirm that the local license permits the physics interface you intend to use.
2. Install 64-bit Python 3.10–3.13.
3. Clone this repository.
4. Double-click RUN_ACCEPTANCE.bat.
5. Inspect runs/acceptance/acceptance_report.md and the JSON evidence.
6. Only after M0 passes, add or select a COMSOL 6.4 physics profile that has been probed and scientifically validated.

The acceptance launcher creates a local .venv, installs the package and runs offline unit tests before asking permission to start COMSOL Server. It does not modify COMSOL installation files or existing COMSOL login configuration.

## Commands

    python -m pip install -e ".[dev,windows]"
    python -m comsol_agent.cli doctor
    python -m comsol_agent.cli validate examples/manifests/manifest-template.json
    python -m comsol_agent.cli m0 --output runs/m0
    python -m comsol_agent.cli run <approved-manifest.json> --output runs

Create and execute an independent mesh convergence plan:

    python -m comsol_agent.cli convergence-plan <approved-manifest.json> --kind mesh --levels 1.0 0.7 0.49 --output runs/convergence
    python -m comsol_agent.cli convergence-run runs/convergence
    python -m comsol_agent.cli convergence-aggregate runs/convergence --metric target

On Windows, managed execution requires pywin32 Job Object containment. If Job Object setup fails, the controller fails closed rather than silently falling back to unsafe process launch.

## Architecture

- Installable Skill: skills/comsol-6.4/
- Python package: skills/comsol-6.4/scripts/comsol_agent/
- Controller: validates Manifests, creates immutable task workspaces and supervises Worker processes.
- Worker: performs one task Manifest and one designated solve in one independent output directory.
- COMSOL backend: uses MPh 1.4 Server and Client APIs with explicit COMSOL 6.4 selection.
- Validation: typed quantities, live read-only pre-solve probes, four-level success reporting and optional convergence aggregation.

## Important operating rules

- Never overwrite a source MPH file.
- Use absolute paths for all COMSOL file operations.
- Do not persist raw entity indices across geometry rebuilds.
- Do not assume a physics API is supported until its COMSOL 6.4 profile has passed an actual probe and benchmark.
- A solver success does not establish physical correctness.
- Long or expensive runs require an approved resource budget.
- Worker timeout cleanup is not called successful until every recorded Job Object process has exited.
- No secret, COMSOL login file, license file, local API cache or simulation result belongs in Git.
- A profile may not call Study.run as an ordinary action; the Worker enforces live Gate A-H evidence first.

## Local acceptance outputs

The acceptance launcher writes to runs/acceptance/:

- environment report
- Python dependency report
- unit test report
- Job Object process-tree test
- COMSOL Server startup/connection report
- minimal MPH save/reload evidence
- process cleanup evidence
- consolidated acceptance report

## Frozen requirements

The authoritative requirements are in TASK_PLAN.md, Revision 1.2. Progress and unresolved local evidence are in STATUS.md.
