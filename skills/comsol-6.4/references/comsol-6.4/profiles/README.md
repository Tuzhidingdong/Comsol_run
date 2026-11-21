# COMSOL 6.4 API Profiles

This directory intentionally contains no profile marked production-validated.

Copy the generic profile template from skills/comsol-6.4/profile-template.json or create a JSON profile here. Keep the verification state at discovered until the exact feature types, property names and execution sequence have been tested on COMSOL 6.4.

Promotion requirements:

1. Minimal COMSOL 6.4 probe passed.
2. Reusable integration test passed.
3. Physics, selection and material semantics reviewed.
4. All live Gate A-H probes tested. These probes must call only methods on the executor's read-only allowlist.
5. Independent analytical, numerical or experimental validation evidence attached.
6. test_id and evidence_files recorded in the profile.
7. At runtime, every gate must produce live COMSOL evidence; missing probes are a blocking failure.

The ProfileExecutor rejects profiles that are not in validated state. Profiles cannot invoke Study.run as an action. The Task Worker invokes Study.run only after evaluating all live pre-solve gates.


## Mesh characteristic size for GCI

For a mesh convergence audit, set the profile field mesh_characteristic_size_result to the name of one result evaluation that returns a finite positive scalar physical characteristic mesh size h with an explicit unit. The Worker records this measured h in metrics.json for each child run.

A mesh refinement multiplier is only an input scale. It is not an actual mesh-size measurement and is never substituted for h in a GCI calculation. When h is absent for any child, aggregation records GCI as NOT_APPLICABLE with the reason.
