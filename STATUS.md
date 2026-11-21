# Project Status — Comsol_run

> Governing contract: TASK_PLAN.md (Revision 1.2). This file records implementation progress and evidence. It does not override the frozen task plan.

## Overall status

- Delivery: initial COMSOL 6.4 Agent Skill framework implemented and committed.
- Current stage: M0 — local COMSOL 6.4 feasibility acceptance.
- Repository unit tests: CI status is tracked by GitHub Actions; see the latest run on the main branch.
- User-machine COMSOL 6.4 M0 acceptance: **NOT YET RUN**.
- Production-ready physics profiles: **NONE**. Profile verification remains at discovered until a real COMSOL 6.4 probe and independent scientific benchmark pass.
- Full V1 acceptance (AC-01 through AC-37): **NOT CLAIMED**.

The user's COMSOL installation, license, existing login file and machine-specific configuration have not been accessed or modified by this development session.

## Implemented repository capabilities

- [x] Revision 1.2 TASK_PLAN.md frozen and preserved.
- [x] Project status and ignore rules.
- [x] Installable Skill directory and entry point.
- [x] Nine-section typed Manifest schema (metadata plus the nine domain sections).
- [x] JSON Schema validation, explicit quantity/expression units and Pint dimensional checks.
- [x] Conservation-term dimensional compatibility checks.
- [x] Build execution path and protected patch-copy path.
- [x] Patch source SHA-256 checks; source MPH is never the write target.
- [x] Profile verification states; unvalidated profiles cannot run as production profiles.
- [x] Non-solving profile-probe path to collect live API/Gate A-H/save-reload evidence before profile promotion.
- [x] Restricted profile action vocabulary and read-only live Gate A-H probes.
- [x] Mandatory solver auto-sequence action before custom solver settings.
- [x] Strict Pre-Solve gate evaluation and COMSOL diagnostic blocking.
- [x] Separate API, numerical, physical-validation and reproduction states.
- [x] Result quantity extraction, CSV export and profile-declared image-export path.
- [x] Explicit user-defined conservation-balance evaluator.
- [x] Mesh/time convergence child-manifest derivation and controller orchestration.
- [x] Guarded GCI and time-step sensitivity aggregation; GCI requires measured characteristic mesh sizes.
- [x] Worker/Controller isolation, Windows Job Object process-tree containment and optional hard Job memory limits.
- [x] MPh Server/Client COMSOL 6.4 adapter and M0 smoke probe.
- [x] MPH save/reload structure comparison in M0 and normal task execution.
- [x] Unit tests and Windows one-click local acceptance launcher.
- [ ] Actual COMSOL 6.4 Server startup/authentication proved on the user's PC.
- [ ] Actual Windows Job Object cleanup proved on the user's PC.
- [ ] Actual MPH save/reload proved on the user's PC.
- [ ] At least one physics profile passed against COMSOL 6.4 and an independent scientific benchmark.
- [ ] profile-probe executed successfully against the user's COMSOL 6.4 installation.
- [ ] AC-01 through AC-37 all accepted.

## M0 — Feasibility Spike

### Implemented

- Version and executable discovery.
- Python/MPh/pywin32 diagnostics.
- Dynamic port Server startup and Client connection.
- Existing COMSOL v64 login-file preservation strategy.
- Harmless Worker + child-process Job Object kill test, run before COMSOL Server startup.
- Minimal model creation, save, remove, reload and inspection.
- Server cleanup and process-exit evidence.
- One-click launcher at RUN_ACCEPTANCE.bat.

### Required evidence on the user's Windows machine

- [ ] 64-bit supported Python is selected.
- [ ] COMSOL 6.4 comsolmphserver.exe is discovered.
- [ ] MPh 1.4.x connects to the actual COMSOL 6.4 installation.
- [ ] Login succeeds without overwriting the existing v64 login file.
- [ ] Job Object test kills the Worker and its spawned child.
- [ ] MPh Client connects to the owned Server.
- [ ] Minimal MPH file is saved, removed from memory, reloaded and structurally inspected.
- [ ] Owned Server exits after disconnect.
- [ ] Unrelated COMSOL Desktop/Server processes remain untouched.

**M0 result: PENDING USER-MACHINE EXECUTION.**

## M1 — Core Closed-Loop MVP

### Implemented framework

- Manifest, typed values, profile engine, build/patch scaffolding.
- Live Gate A-H probes, COMSOL problem diagnostics and strict solve blocking.
- Parameterized actions, selection/material/physics/mesh/Study hooks.
- Output and report infrastructure.
- MPH checkpoint/reload and source protection.

### Still required

- [ ] A COMSOL 6.4 profile with exact supported geometry/material/physics/mesh/Study calls.
- [ ] Live gate probes for a real model, including mesh statistics and a valid DOF/resource evaluation.
- [ ] One real, licensed COMSOL 6.4 physics computation.
- [ ] One independent analytical or quantitative benchmark pass.
- [ ] Real-world result/image export and reloaded solved-model inspection.

No physics profile is shipped as validated; the Worker correctly refuses to run a profile that has not passed these steps. Consequently, the current repository can execute its M0 acceptance probe, but it must not yet be advertised as ready to run research simulations.

## M2 — Advanced Capabilities

### Implemented framework

- Independent child Manifests and output directories.
- Sequential convergence orchestration, preservation of successful siblings, and failed-child retry in a new attempt directory.
- GCI calculation guarded by monotonic convergence, approximately equal refinement ratios and measured characteristic mesh sizes.
- Time-step sensitivity calculation with explicit user tolerance.
- User-defined conservation-balance calculation with unit compatibility enforcement.
- Patch-copy source preservation and integrity checks.

### Still required

- [ ] Real COMSOL 6.4 mesh convergence run.
- [ ] Real COMSOL 6.4 transient time-step sensitivity run.
- [ ] Physics-specific conservation checks validated on a physical case.
- [ ] Real patch-mode integration test against a source MPH.
- [ ] Full COMSOL-specific error regression and AC-35/AC-36 evidence.

## Technical constraints and known limitations

1. The execution environment used for repository development does not have access to the user's Windows desktop, COMSOL license, local COMSOL installation or local credentials. It cannot execute the real M0 COMSOL probe.
2. MPh's public integration documentation states that COMSOL 6.0+ is expected, but its published successful test range currently stops at 6.3. The 6.4 combination must therefore be treated as unverified until M0 passes on the user's installation.
3. No physics API is marked supported solely because its API type/property name appears in a template or external example.
4. DOF inspection is a profile-specific live probe. If no non-solving, COMSOL-6.4-tested route is available, the report must say so; it must not invent a DOF count.
5. Model.problems() diagnostics are conservatively blocking until a profile declares a reviewed policy for any non-blocking warnings.
6. Graceful cancellation of a synchronous COMSOL solve is backend-dependent. Hard Job Object termination is separately recorded and is not reported as graceful cancellation.
7. GCI is not calculated from user-selected refinement multipliers. A profile must extract actual characteristic mesh size h for every child run.

## User-side acceptance entry point

Double-click RUN_ACCEPTANCE.bat on the Windows machine with COMSOL 6.4 installed. It installs the Python project into a local .venv, runs unit tests and diagnostics, then asks before starting the licensed COMSOL Server test.

Inspect runs/acceptance/acceptance_report.md and its JSON evidence. A passing M0 probe is the prerequisite for starting the next real COMSOL physics-profile benchmark; it is not the full V1 acceptance.
