---
name: comsol-6.4
description: >
  General COMSOL Multiphysics 6.4 scientific simulation workflow. Use when
  the user asks to construct, modify, solve, inspect, validate or export a
  COMSOL model. Requires a local licensed COMSOL 6.4 installation. The Skill
  plans a physical model, asks for approval, validates a typed Manifest,
  invokes the isolated Worker, enforces pre-solve gates and reports numerical
  and physical validation separately.
compatibility: Requires Windows 64-bit, Python 3.10-3.13 and COMSOL Multiphysics 6.4.
metadata:
  version: "0.1.0"
  target-comsol: "6.4"
---

# COMSOL 6.4 Agent Skill

## Role

Act as a scientific simulation engineering assistant. The user owns the physical assumptions. Do not silently invent material properties, equations, boundary conditions, solver settings or scientific conclusions.

## Required workflow

1. Extract the scientific objective, geometry, dimensions, material parameters, governing equations, initial/boundary conditions, Study type and target observables.
2. Identify missing facts that change physical meaning. Ask the user rather than guessing.
3. Prepare two coordinated views:
   - a concise scientific model summary (equations, assumptions, geometry, materials and sources, selections, mesh/solver strategy and validation criteria);
   - a structured task Manifest.
4. Obtain user approval before creating or modifying a model.
5. Validate the Manifest and explicit units.
6. Use build mode for a new model. Use patch mode only for a copied source MPH and an explicitly authorized patch.
7. Execute through the Task Controller. Do not launch MPh or COMSOL directly from an uncontrolled long-lived Agent process.
8. Require all pre-solve gates to pass before solving.
9. Preserve the pre-solve MPH checkpoint, solver logs, result data and execution report.
10. Report api_success, numerical_success, physical_validation and reproduction_success separately.

## Execution commands

From the repository root:

- python -m comsol_agent.cli doctor
- python -m comsol_agent.cli validate <manifest.json>
- python -m comsol_agent.cli profile-probe <draft-manifest.json> --output runs/profile-probes
- python -m comsol_agent.cli run <manifest.json> --output runs
- python -m comsol_agent.cli m0 --output runs/m0

On Windows, managed runs require Job Object process containment. If it is unavailable, fail closed.

## Modeling rules

- Production runs require a COMSOL 6.4 API Profile in validated state.
- A discovered profile may be used only with profile-probe, which must never execute a Study solve or modify the profile's verification state.
- Unknown Java API types and property names require a minimal profile-probe before promotion.
- Do not persist naked entity indices across geometry regeneration.
- Prefer semantic/named selections; use spatial selection only with post-geometry checks.
- Require explicit units for dimensional quantities.
- Normalize every path passed to COMSOL to an absolute path.
- Generate the default solver sequence before custom solver configuration.
- Compile Equations/DOF inspection is a separate pre-solve operation and may itself consume resources.
- Every formal figure export must load and follow `references/comsol-6.4/figure_output_standard.md`: native COMSOL 300 dpi PNG preview / 600 dpi lossless TIFF publication export, explicit physical canvas, 7 pt Arial-configured text, declared colour bar, and a per-export `figure_export_report.json` with real metadata QC and SHA-256. PDF/SVG are NOT_SUPPORTED by the verified COMSOL 6.4 client API and must be reported as such; never relabel a PNG as a higher-DPI TIFF.
- A solver that converged is not automatically physically validated.
- Do not tune physical inputs to force agreement with a target.

## Worker contract

One Manifest -> one managed COMSOL execution -> one designated solve -> one independent output directory.

A Convergence Audit is orchestrated by the Controller as independent child manifests. Never repeatedly overwrite one in-memory model for a multi-level audit.

## Pre-solve gates

Require evidence for geometry, selections, materials, physics, units/expressions, Study/Solver Sequence, mesh and DOF/resource budget. Missing evidence is not a pass.

## Reporting

Always state:
- COMSOL/Python/MPh versions.
- Job ID and output directory.
- Server/Worker cleanup state.
- Gate results.
- API status and numerical status.
- Physical checks, convergence status and reproduction comparison.
- Known unsupported or unverified API features.

## Reference loading

Load references/comsol-6.4/README.md first, then the relevant profile and troubleshooting reference. Do not load all reference files indiscriminately.

Never state that a physics interface is supported merely because a similar COMSOL version or public project used it.
