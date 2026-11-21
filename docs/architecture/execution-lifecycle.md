# Execution lifecycle

## Ownership

The Task Controller owns task identities, immutable parent/child manifests, scheduling, timeouts and output aggregation.

A Worker owns one task Manifest and one independent COMSOL session. A Worker does not reuse its in-memory model for another task.

## Windows process tree

The Controller creates a Windows Job Object with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, starts the Worker suspended, assigns it to the Job Object, and resumes it only after the assignment succeeds.

The Worker starts MPh Server. MPh Server starts comsolmphserver.exe as a child process. The Server therefore remains within the Worker Job Object unless it deliberately requests breakaway (which this project does not do).

At timeout:

1. the Controller writes a cancellation marker;
2. the Controller attempts graceful console cancellation;
3. it waits for the configured grace period;
4. it terminates the Job Object if the Worker remains active;
5. it closes the Job Object;
6. it verifies recorded Job Object PIDs have exited.

A timeout is not a successful cancellation. The final report distinguishes graceful cancellation, hard termination and verified cleanup.

When Manifest metadata.execution_limits.max_memory_gb is set, the Controller applies JOB_OBJECT_LIMIT_JOB_MEMORY to the task Job Object. The limit covers the Worker and owned COMSOL Server process tree. If the operating system terminates the task for exceeding this cap, the Worker result is incomplete and the Controller reports failure rather than numerical success.

## MPh integration

The implementation pins MPh 1.4.x and uses its public Server and Client classes. MPh dynamically discovers the local COMSOL installation, starts a Server on a selected port and reads its standard output to discover the actual port.

MPh Server defaults to COMSOL automatic login. When %USERPROFILE%\.comsol\v64\login.properties already exists, this project appends -login never to avoid resetting it. If no v64 login file exists, automatic first-run initialization is allowed. Existing file SHA-256 is checked after the M0 connection attempt.

Do not append -silent to the MPh Server invocation: MPh's graceful shutdown sends close to standard input, and COMSOL silent mode stops listening to stdin.

## File paths

All paths passed to COMSOL model save/load/evaluation/export operations are resolved to absolute paths before crossing the Python-to-Java boundary. The Worker current directory and COMSOL Server working directory are not assumed to be identical.

## Profile execution and safety

Profiles are version-scoped and must be in validated state before production execution. They contain a restricted construction action sequence plus read-only live pre-solve probes.

The profile action vocabulary does not contain a solve action. The Worker evaluates live Gate A–H evidence and only then invokes the MPh model solve method.

Gate probes can call only the read-only method allowlist in ProfileExecutor. Missing, failing or unsupported probes block solving.
