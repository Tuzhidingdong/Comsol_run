# COMSOL 6.4 reference index

All API claims are version-scoped. Do not reuse a 6.2/6.3 API verification record as COMSOL 6.4 evidence.

## Verification states

- discovered: documentation or reflection identified the symbol.
- probe_passed: a minimal call succeeded in a disposable COMSOL 6.4 model.
- integration_tested: the feature passed a reusable integration test.
- validated: the feature passed a numerical/physical benchmark.

Only validated profiles may be described as production-validated.

## Runtime baseline

The package uses MPh's public Server and Client APIs. Server owns a local COMSOL Server process and exposes its process handle, selected port and stop method. A Worker is launched inside a Windows Job Object so its child Server inherits task containment. Actual behavior must be verified by the local M0 probe.

## API notes to verify on 6.4

- Study auto-sequence: study.createAutoSequences("all").
- Compile Equations statistics: inspect the generated solver tree and its Compile Equations node; obtain DOF only through a tested 6.4 mechanism.
- Mesh quality: use the metric appropriate to the element type and physics. Never enforce one global quality threshold for all models.
- Selections: persist semantic definitions and validate dimensions, counts and geometric signatures after geometry finalization.
- File paths: use normalized absolute paths in all Java API save/export/import calls.

## Figure output

Load `figure_output_standard.md` before any formal image export. It defines the reusable publication presets, verified COMSOL 6.4 export properties, DPI/metadata QC, and the explicit list of unsupported vector formats. Preview PNGs go to `results/images/preview/`, publication TIFFs to `results/images/publication/`, and every export is recorded in `figure_export_report.json`.

## Profiles

No physics profile is promoted to validated by this initial repository scaffold. Add one only with a COMSOL 6.4 test ID, exact API type/property evidence, test output and scientific benchmark.
