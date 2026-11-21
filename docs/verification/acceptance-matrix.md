# AC-01…AC-37 implementation and evidence matrix

Governing contract: TASK_PLAN.md Revision 1.2. This matrix records evidence without changing the frozen acceptance criteria.

State meanings:

- **CI/code verified** — implementation or a bounded software behavior is covered by repository tests and the latest passing CI.
- **Framework only / local evidence pending** — code path exists, but COMSOL-specific behavior has not been proven on the actual COMSOL 6.4 installation/license.
- **Pending** — the criterion needs a real COMSOL 6.4 run, an end-to-end Agent acceptance, or an additional implementation/test not yet available.

| AC | Criterion (condensed) | Current implementation/evidence | State |
|---|---|---|---|
| AC-01 | Agent recognizes COMSOL task and loads Skill | Installable Skill metadata and explicit workflow instructions exist; automatic Agent invocation is not end-to-end tested. | Framework only / end-to-end pending |
| AC-02 | Skill independent of repo governance/tests | Installable Skill is isolated under skills/comsol-6.4/; tests/docs remain outside it. | CI/code verified |
| AC-03 | Natural language to valid Manifest | Skill workflow instructs an Agent to draft and validate the nine-domain Manifest; no deterministic natural-language parser is claimed. | Framework only / Agent acceptance pending |
| AC-04 | Nine domain sections and version/mode metadata | JSON Schema and Manifest validator cover the required structure and COMSOL version. | CI/code verified |
| AC-05 | Build and controlled patch modes | Patch mode copies the source MPH, hashes source/copy and only loads the copy; no real COMSOL patch fixture has been exercised. | Framework only / local evidence pending |
| AC-06 | Scientific summary and Manifest before execution | Skill instructions require review before execution; no autonomous end-to-end interaction acceptance has been run. | Framework only / Agent acceptance pending |
| AC-07 | No silent invention of scientific assumptions | Skill rules and Manifest validation avoid inferred physical inputs; user-facing Agent behavior still needs acceptance. | Framework only / Agent acceptance pending |
| AC-08 | Detect actual COMSOL 6.4 and Python environment | doctor/environment discovery code and M0 output report exist; user's installation has not been probed. | Framework only / local evidence pending |
| AC-09 | Real COMSOL 6.4 Client–Server connection | MPh Server/Client adapter and M0 probe exist; no connection to the user's licensed COMSOL 6.4 instance has been run. | Pending |
| AC-10 | Isolated Worker per task | Worker is a separate process assigned to a Windows Job Object; Windows CI process-tree acceptance passed on Python 3.11–3.13. | CI/code verified |
| AC-11 | Reliable Worker/owned COMSOL process tracking | Worker PID, Job Object PID list and cleanup results are captured; actual COMSOL Server PID tracking remains part of local M0. | Framework only / local evidence pending |
| AC-12 | Graceful cancellation and safe process-tree termination | Controller attempts graceful console cancellation then hard Job Object termination; CI proves hard descendant termination, not graceful cancellation of a real COMSOL solve. | Framework only / local evidence pending |
| AC-13 | Unrelated/user-owned processes unaffected | Windows CI starts an out-of-job sentinel and confirms it survives Job Object termination; user's existing COMSOL Desktop/Server sessions have not been involved. | CI/code verified for isolation boundary; local coexistence pending |
| AC-14 | Create/save/reload/inspect MPH in COMSOL 6.4 | M0 and Worker save/reload structure verification are implemented; no actual COMSOL 6.4 model round-trip has been run on the user's machine. | Pending |
| AC-15 | Basic model via verified geometry/material/physics/selection/mesh APIs | Restricted profile action engine exists, but no production profile is marked validated and no complete COMSOL 6.4 physics model has passed. | Pending |
| AC-16 | Validate selections by dimension/count/location | Profile-defined live read-only Gate probes support checks; no real COMSOL 6.4 selection profile/evidence exists. | Framework only / local evidence pending |
| AC-17 | Avoid unverified naked entity indices | Manifest/profile model emphasizes semantic selections and post-geometry checks; each eventual profile still needs review for index use. | Framework only / profile review pending |
| AC-18 | Explicit units and dimensional checks | Pint-backed quantity/expression checks and conservation-term dimension checks are covered by tests. | CI/code verified |
| AC-19 | Generate default solver sequence before custom settings | Executor has an explicit create_auto_sequences operation and blocks custom solver settings before it. COMSOL 6.4 API behavior still needs the local profile probe. | Framework only / local evidence pending |
| AC-20 | Pre-Solve gate blocks invalid/incomplete models | Missing or failed live Gate A–H evidence blocks solve; tests cover missing evidence and read-only probe restrictions. | CI/code verified |
| AC-21 | Mesh element count and quality in report | Generic profile probe template and Gate evidence pipeline can report count/quality; no COMSOL 6.4 mesh profile has been validated. | Framework only / local evidence pending |
| AC-22 | Actual DOF or explicit resource estimate vs limits | Profile template supports a live DOF probe and Manifest budget reference; no verified COMSOL 6.4 DOF API/evidence exists yet. | Framework only / local evidence pending |
| AC-23 | Real COMSOL 6.4 numerical solve | No validated physics profile or actual licensed solve has been run. | Pending |
| AC-24 | Independent analytic/quantitative benchmark passes | Benchmark comparison code exists, but there is no actual COMSOL 6.4 case/result against an independent reference. | Pending |
| AC-25 | Separate API/numerical/physical/reproduction outcomes | Worker/report schema preserves four separate states and does not infer physical validity from solver success. | CI/code verified |
| AC-26 | Optional mesh convergence on controlled test case | Child Manifest orchestration, measured-h GCI guard and algorithm tests exist; no controlled COMSOL mesh study has run. | Framework only / local evidence pending |
| AC-27 | Optional transient time-step sensitivity | Child Manifest orchestration and sensitivity algorithm tests exist; no controlled COMSOL transient case has run. | Framework only / local evidence pending |
| AC-28 | Reproducible configured conservation checks | Unit compatibility and user-declared signed balance evaluation exist; no physics-specific COMSOL conservation case has been validated. | Framework only / local evidence pending |
| AC-29 | Unit warnings/diagnostics block unapproved execution | Unit validation and Model.problems() blocking are implemented; raw COMSOL 6.4 warning behavior still needs local evidence. | Framework only / local evidence pending |
| AC-30 | Unsupported API never silently treated as verified | Production profiles must be validated; action operations are allowlisted; non-solving profile-probe generates evidence but never auto-promotes a profile. | CI/code verified |
| AC-31 | Export usable numerical data and images | Scalar JSON/CSV and profile-declared image export are implemented; actual COMSOL 6.4 exports remain untested. | Framework only / local evidence pending |
| AC-32 | Reload MPH and inspect structures/results | Structure comparison is implemented for pre-solve and solved MPH files; actual COMSOL 6.4 behavior remains pending. | Framework only / local evidence pending |
| AC-33 | Reproducible execution/scientific report | Manifest hash, execution report, evidence files and output directory are generated; real scientific report awaits a real model run. | Framework only / local evidence pending |
| AC-34 | Protect source MPH | Patch works on a SHA-256 verified copy and checks source hash before/after; source-copy unit tests pass. | CI/code verified for file protection; real MPH patch pending |
| AC-35 | Preserve COMSOL messages and provide actionable diagnostics | Original exception text/traceback and Model.problems() records are retained; heuristic categories never replace originals; classifier tests added. | CI/code verified for bounded diagnostic behavior |
| AC-36 | Regression tests for verified API/execution behavior | Cross-platform regression suite and Windows Job Object acceptance pass; COMSOL API regression awaits the first validated 6.4 profile. | Framework only / local API regression pending |
| AC-37 | No test-specific science assumptions or machine paths in production Skill | Skill/profile templates are generic and repository-relative; continue reviewing every new profile before promotion. | CI/code verified by structure/review; ongoing constraint |

## Verified automated CI evidence

Latest CI run: GitHub Actions workflow Python tests, run 44919509366, commit 8b60a10d7c32be6580ce7ded4881c6202f326646 — success across all six OS/Python combinations. Its result is authoritative for repository tests only, not for COMSOL installation or license acceptance.

Windows Job Object process-tree acceptance was independently enabled on Windows runners for all supported Python matrix versions. It checks worker/descendant termination and survival of a process outside the Job Object.

## Full V1 release boundary

Full V1 remains NOT ACCEPTED until every AC-01 through AC-37 is passed with the required evidence. In particular, actual COMSOL 6.4 Server connection, MPH round-trip, a validated physics model, one numerical solve, and an independent benchmark are prerequisites that cannot be replaced by CI.
