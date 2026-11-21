# Verification evidence and acceptance states

## Four independent outcomes

Every run reports:

- api_success: requested COMSOL API operations were accepted.
- numerical_success: the designated solve completed and valid outputs were extracted.
- physical_validation: declared physical checks passed. null means no qualifying physical checks were performed.
- reproduction_success: a declared analytical/reference benchmark met its predeclared tolerance. null means no baseline was configured.

Do not infer a higher-level success from a lower-level status.

## Profile promotion

Profile verification states are:

1. discovered
2. probe_passed
3. integration_tested
4. validated

A production profile requires a COMSOL 6.4 test ID and evidence file paths. It must also have live probes for all required Gate A–H conditions. The presence of a profile JSON file is not evidence that its API calls work.

## Pre-solve evidence

Each required gate must contain one or more explicit live checks. A check is passed only when its read-only COMSOL API probe ran successfully and its comparison passed. A missing probe is a failure, not an implicit pass.

The schema requires all eight gates. The profile must provide live evidence for every gate in the specific model.

## Convergence audits

The Controller creates one child Manifest per mesh or time-step variant. Each child gets its own Worker process and output directory.

The Controller:

- runs children sequentially by default;
- records each attempt separately;
- skips children already marked passed;
- retries failed children in a new attempt directory;
- keeps successful child artifacts after sibling failure;
- aggregates only compatible numeric outputs.

GCI is calculated only for three mesh levels when the selected scalar results are finite, monotonic, and the characteristic refinement ratios are approximately equal. Otherwise the report marks GCI as not applicable with the reason.

## M0 is not full V1 acceptance

M0 verifies the Windows execution backend and a minimal COMSOL model's save/reload lifecycle. It does not prove that a physics interface is correctly configured or that all 37 AC items have passed.

M1 and M2 evidence is recorded separately in STATUS.md.
