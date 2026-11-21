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
8. Add the exact product/module names returned by MPh Client.modules() to required_modules. The Worker checks these against the connected COMSOL license before creating or patching a model.
9. For mesh GCI, set mesh_characteristic_size_result to the name of an extracted scalar result that measures the physical characteristic mesh size h in a declared unit. A mesh refinement multiplier is not an h measurement.

The ProfileExecutor rejects profiles that are not in validated state. Profiles cannot invoke Study.solve as an action. The Task Worker invokes Study.solve only after evaluating all live pre-solve gates.
