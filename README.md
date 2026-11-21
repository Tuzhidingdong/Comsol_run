# COMSOL Agent Skill — COMSOL 6.4

A Windows-first framework for an Agent to turn an approved scientific model specification into a controlled COMSOL build/patch execution, pre-solve evidence, numerical outputs and validation report.

Target environment: COMSOL Multiphysics 6.4, Windows 64-bit, Python 3.10–3.13, MPh 1.4.x.

**Important:** MPh's published integration tests currently list COMSOL through 6.3. This repository targets 6.4, but does not claim the COMSOL 6.4 integration has passed until the local M0 acceptance probe succeeds. No physics profile is shipped as production-validated.

## First step

1. Install COMSOL Multiphysics 6.4 and ensure your license includes the physics interface you intend to use.
2. Install 64-bit Python 3.10–3.13.
3. Clone this repository.
4. Double-click RUN_ACCEPTANCE.bat.
5. Inspect runs/acceptance/acceptance_report.md.
6. After M0 passes, add a COMSOL 6.4 physics profile and scientific benchmark, then promote it through discovered → probe_passed → integration_tested → validated.

The launcher creates a repository-local .venv, runs the unit tests and environment diagnostics, then asks before starting the local COMSOL Server. It does not install COMSOL or modify the installation directory. An existing %USERPROFILE%\.comsol\v64\login.properties is preserved and checked.

## Commands

    python -m pip install -e ".[dev,windows]"
    python -m comsol_agent.cli doctor
    python -m comsol_agent.cli profiles
    python -m comsol_agent.cli validate examples/manifests/manifest-template.json
    python -m comsol_agent.cli m0 --output runs/m0
    python -m comsol_agent.cli run <approved-manifest.json> --output runs

Mesh convergence:

    python -m comsol_agent.cli convergence-plan <approved-manifest.json> --kind mesh --levels 1.0 0.7 0.49 --output runs/convergence
    python -m comsol_agent.cli convergence-run runs/convergence --metric target
    python -m comsol_agent.cli convergence-aggregate runs/convergence --metric target

Time-step sensitivity:

    python -m comsol_agent.cli convergence-plan <approved-manifest.json> --kind time --levels 1.0 0.5 0.25 --output runs/time-audit
    python -m comsol_agent.cli convergence-run runs/time-audit --metric target

## Architecture

- Skill: skills/comsol-6.4/
- Task Controller: immutable task workspaces, retry/resume, timeout and aggregation.
- Worker: one Manifest, one managed COMSOL session, one solve, one output directory.
- Backend: MPh Server and Client with explicit COMSOL 6.4 targeting.
- Profiles: version-scoped API recipes. Only validated profiles can be executed.
- Validation: units, live Gate A–H evidence, COMSOL diagnostics, analytic baseline, conservation, numerical result export and convergence checks.

## Safety invariants

- Never overwrite a source MPH file; patch mode works on a verified copy.
- All paths passed to COMSOL are absolute.
- Do not persist raw geometry entity indices through geometry rebuilds.
- Do not silently invent scientific assumptions, boundary conditions or material data.
- Missing live gate evidence blocks solving.
- Profile actions cannot directly invoke Study.solve; the Worker controls solve after all gates pass.
- A numerical solve is not proof of physical correctness or reproducibility.
- GCI requires measured physical mesh sizes, not refinement multipliers.
- On Windows, managed execution fails closed if Job Object containment is unavailable.
- No login file, credentials, license file, local configuration or generated model/result belongs in Git.

## Local acceptance evidence

RUN_ACCEPTANCE.bat writes to runs/acceptance/. It records Python/COMSOL discovery, dependency tests, Windows Job Object descendant cleanup, COMSOL Server connection, licensed modules, MPH save/reload structure and Server shutdown.

## Authoritative requirements

TASK_PLAN.md Revision 1.2 is the frozen development contract. STATUS.md distinguishes implemented code from evidence still required on the actual COMSOL 6.4 machine.
