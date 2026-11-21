# Verification evidence and acceptance states

## Four independent outcomes

Every run reports:

- api_success: requested COMSOL API operations were accepted.
- numerical_success: the designated solve completed and valid outputs were extracted.
- physical_validation: declared physical checks passed. null means no qualifying physical checks were performed.
- reproduction_success: a declared analytical/reference benchmark met its predeclared tolerance. null means no baseline was configured.

Do not infer a higher-level success from a lower-level status.

## Profile promotion

Profile states:

1. discovered
2. probe_passed
3. integration_tested
4. validated

A discovered profile can be run only through the non-solving profile-probe command. It requires build mode and study.run=false, runs restricted construction actions and read-only live Gate A-H probes, checks COMSOL diagnostics, and verifies a saved/reloaded MPH checkpoint. It does not call Study.solve and does not modify the profile verification state. A passing report suggests probe_passed; promotion remains an explicit reviewed action.

A production profile requires a COMSOL 6.4 test ID and evidence file paths. It must also have live probes for all required Gate A-H conditions. The presence of a profile JSON file is not evidence that its API calls work.

MPh documents Windows Server and Client integration, but its published successful test range currently stops at COMSOL 6.3. COMSOL 6.4 must be accepted through the local M0 probe before a profile can be promoted.

## Pre-solve evidence

Each required gate must contain one or more explicit live checks. A check passes only when its read-only COMSOL API probe ran successfully and its comparison passed. A missing probe is a failure, not an implicit pass.

The schema requires all eight gates. The profile must provide live evidence for every gate in the specific model. COMSOL model warnings/errors returned by MPh Model.problems() are blocking unless a reviewed profile policy is introduced.

## Convergence audits

The Controller creates one child Manifest per mesh or time-step variant. Each child gets its own Worker process and output directory.

The Controller:

- runs children sequentially by default;
- records each attempt separately;
- skips children already marked passed;
- retries failed children in a new attempt directory;
- keeps successful child artifacts after sibling failure;
- aggregates only compatible numeric outputs.

GCI is calculated only for three mesh levels when the selected scalar results are finite, monotonic and the characteristic refinement ratios are approximately equal. The characteristic mesh size h must be measured and exported by the validated profile for each child. A refinement multiplier is not a substitute for actual h.

Time-step sensitivity requires a declared relative tolerance in the Manifest. The report compares successive levels ordered from coarse to fine.

Conservation checks require user-provided terms, signs, expected units and tolerance. The tool does not infer control volumes, flux direction, sources or sinks.

## M0 is not full V1 acceptance

M0 verifies the Windows execution backend and a minimal COMSOL model's save/reload lifecycle. It does not prove that a physics interface is correctly configured or that all 37 task-plan acceptance criteria have passed.

M1 and M2 evidence is tracked separately in STATUS.md.


## Error diagnostics

The Worker writes the original exception message and full Python traceback to worker_result.json and diagnostic_report.json. COMSOL Model.problems() records remain present in their original form; an additional heuristic classification suggests likely areas to inspect.

Categories are advisory only. The classifier does not replace, rewrite or suppress the original COMSOL message, and unknown messages remain unclassified. It does not apply corrective changes or infer scientific modifications from an error string.
