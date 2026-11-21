# User Task Plan — comsol-agent-skill-v1

> Revision: 1.2 — Second-round engineering hardening  
> Status: Frozen development contract after user approval.  
> The user owns this document. Antigravity and workers must preserve the original objective, constraints, scope and acceptance criteria. Execution progress belongs in the sibling STATUS.md.

## 1. Objective

Develop a general-purpose, reproducible and scientifically verifiable COMSOL Multiphysics Agent Skill, initially targeting the user's local COMSOL Multiphysics 6.4 environment.

The Agent must translate natural-language scientific simulation requirements into reviewed physical specifications, construct and execute COMSOL models, inspect and validate numerical results, and deliver reusable simulation artifacts.

The system must support a complete simulation lifecycle:

1. Understand the scientific problem and extract physical requirements.
2. Formulate a physically meaningful model specification.
3. Present a human-readable modeling plan and a structured machine-readable specification for user review.
4. Construct or modify a COMSOL model through controlled programmatic interfaces.
5. Perform mandatory pre-solve validation.
6. Execute and supervise COMSOL computations with reliable process isolation, timeout handling and cleanup.
7. Extract, analyze and visualize numerical results.
8. Perform numerical and physical validation, including optional mesh and time-step convergence audits.
9. Save, reload and verify the model and its results.
10. Deliver an auditable record of the model, configuration, computation and validation evidence.

The Skill is a general scientific simulation tool, not a domain-specific application.

The human user, or a physical specification explicitly approved by the user, owns the scientific assumptions. The Agent is responsible for faithfully implementing and verifying those assumptions, not for silently inventing scientific facts.

The core quality principle is:

**A successful API call is not proof of a successful numerical solution; a converged numerical solution is not proof of a physically correct model; and a plausible result is not proof of successful reproduction.**

## 2. Current state

### Repository

- GitHub: https://github.com/Tuzhidingdong/Comsol_run
- Default branch: main.
- The repository was empty before this plan was committed.
- No existing production code or implementation architecture needs to be preserved.
- No implementation has been approved yet.

### Local simulation environment

- COMSOL Multiphysics: 6.4.
- Primary target platform: Windows 64-bit.
- Python and MPh compatibility must be verified on the actual machine.
- Required COMSOL modules and license availability must be detected rather than assumed.

### Existing projects investigated

The following projects are reference materials, not automatically approved dependencies.

1. 2p1c/comsol-skills
   - MIT-licensed.
   - Reusable Agent Skill structure.
   - Python MPh and COMSOL Java API integration.
   - Published compatibility claims cover COMSOL 6.0–6.3, with primary testing on 6.2.
   - Useful for general Skill design and API practices.

2. N1j1k4/Ai-Comsol
   - COMSOL 6.4-oriented OpenCode Skill.
   - Contains MPh connection scripts, example cases and verification guidance.
   - Useful for investigating COMSOL 6.4 connection and execution behavior.
   - Do not copy source code unless its applicable reuse license is verified.

3. talos888/xjc
   - Manifest-driven COMSOL execution and verification architecture.
   - Useful concepts include supervised execution, guarded modification of existing models, quantitative validation, solver-result checks and save/reload verification.
   - No repository license was declared in the inspected version. Use as an architectural reference, not as a source-code dependency.

4. wjc9011/COMSOL_Multiphysics_MCP
   - Large COMSOL MCP tool collection.
   - Useful for examining reusable model, physics, mesh, solver and result interfaces.
   - Some documented interfaces were verified against COMSOL 6.3, not 6.4.

5. Suzy-Sa/COMSOL-Multiphysics-MCP
   - Hybrid MPh, COMSOL Desktop and MCP architecture.
   - Useful for workflow management, local documentation retrieval and validation design.

### Technical baseline

- MPh supports Client-Server and Stand-alone execution modes.
- Current MPh documentation describes Client-Server as the default backend mode, but the actual mode and lifecycle must be verified in the pinned installation.
- MPh Client with an explicit port connects to an already running COMSOL server; it must not be assumed to launch and manage an independently started comsolmphserver.exe.
- COMSOL 6.4 provides server startup options including -login, -port, -portfile and -silent.
- COMSOL login behavior and MPh authentication compatibility must be tested together.
- COMSOL model save and external file resolution can depend on server-side paths and the server's working directory.
- COMSOL provides Compile Equations functionality and DOF inspection interfaces, but the exact non-solving API sequence must be verified.
- No actual COMSOL 6.4 local compatibility test has been completed for this repository.

All published support claims must be backed by evidence obtained against COMSOL 6.4.

## 3. Required outcome

Deliver a usable COMSOL 6.4 Agent Skill with a controlled execution engine and independent scientific validation layer.

### 3.1 Standard user workflow

**Step 1 — Understand the simulation task**

Extract:

- Scientific objective and target observables.
- Spatial dimensions and coordinate system.
- Geometry and geometric relationships.
- Material definitions and parameter sources.
- Governing physical equations.
- Physics interfaces and multiphysics couplings.
- Initial and boundary conditions.
- Study type and simulation time or parameter range.
- Required numerical outputs and visualizations.
- Validation criteria and acceptable errors.

Identify missing information that changes physical meaning.

Do not fabricate values or silently replace missing scientific assumptions.

**Step 2 — Prepare dual-view modeling specification**

Before execution, provide two coordinated views.

A. Human-readable scientific model summary:

- Governing equations and selected physics.
- Geometric dimensions and coordinate definitions.
- Material properties and their sources.
- Simplifying assumptions.
- Boundary and initial conditions.
- Geometric selection descriptions.
- Mesh and solver strategy.
- Estimated computational requirements.
- Expected physical quantities and validation methods.

B. Machine-readable Manifest:

A validated JSON specification containing parameters, geometry, selections, materials, physics, mesh, study, outputs and validation requirements.

The user should not need to inspect hundreds of lines of JSON to understand the scientific model.

**Step 3 — User approval**

The user reviews the scientific summary and important assumptions before construction.

Missing physical information must be clarified.

The Agent may propose implementation alternatives but cannot silently change the scientific model.

**Step 4 — Model construction or controlled modification**

Support two distinct execution modes:

- build: construct a new model from a reviewed specification.
- patch: apply a limited, explicitly authorized set of modifications to a copied existing MPH model.

Do not assume an arbitrary existing MPH file can be reliably reconstructed into a complete Manifest.

**Step 5 — Mandatory pre-solve validation**

Before any potentially expensive solve, run the static and mesh-level checks defined in Section 5.

Any blocking validation failure must prevent solving.

**Step 6 — Solver configuration and execution**

Generate the default solver sequence where required, compile or inspect the equations where necessary for resource assessment, configure verified solver settings, and launch the calculation through the supervised execution layer.

**Step 7 — Result extraction**

Extract the requested quantities, tables, curves, fields and images.

Preserve original numerical output files and avoid returning unnecessarily large arrays to the Agent conversation.

**Step 8 — Scientific and numerical validation**

Perform the checks declared in the Manifest, including physical constraints, conservation tests, mesh convergence and time-step sensitivity where applicable.

**Step 9 — Save and verify**

Save the MPH model, reload it in a controlled session, and verify the integrity of the model and stored results.

**Step 10 — Deliver**

Provide the model, results, figures, execution log, configuration and validation report.

### 3.2 Independent success states

Every task report must distinguish:

1. api_success: COMSOL accepted the requested API operations.
2. numerical_success: The model assembled and solved with valid numerical outputs.
3. physical_validation: Declared physical checks and numerical reliability criteria passed.
4. reproduction_success: The result met a predeclared analytic, numerical, experimental or reference-model comparison threshold.

Also report mesh/time convergence results separately when those audits are required.

A lower-level success must never be promoted into a higher-level success.

### 3.3 Failure behavior

The system must be able to stop safely and explain:

- Which operation failed.
- Which validation gate was not passed.
- Whether the failure is related to the environment, API, geometry, physics, units, mesh, solver or numerical resources.
- What evidence supports the diagnosis.
- What corrective options require user authorization.
- Whether the Worker, Server and associated computation processes have actually terminated.

Do not silently change model assumptions or physical parameters to force a successful solve.

### 3.4 Three-stage implementation and delivery

Implementation is divided into three incremental milestones:

- M0 — Feasibility Spike: Verify the Windows COMSOL 6.4 integration, process lifecycle and minimal model persistence.
- M1 — Core Closed-Loop MVP: Deliver the usable Skill, Manifest, build mode, pre-solve gates and one scientifically validated end-to-end simulation.
- M2 — Advanced Capabilities and Full Acceptance: Complete patch, convergence orchestration, full error testing and all remaining acceptance criteria.

All original acceptance criteria remain mandatory for full V1 completion. Milestones determine delivery order, not permission to remove requirements.

## 4. Scope

### In scope

**A. Agent Skill**

- Standard Agent Skill structure and entry point.
- Task understanding and planning.
- Dual-view scientific specification.
- User approval gates.
- Manifest preparation and validation.
- Runtime execution orchestration.
- Failure interpretation and reporting.

**B. COMSOL integration**

- COMSOL 6.4 installation and version detection.
- Python MPh integration.
- COMSOL native Java API integration.
- Controlled client-server lifecycle.
- Geometry and selection management.
- Materials, variables and parameters.
- Physics interfaces and boundary conditions.
- Multiphysics coupling where verified.
- Mesh generation and statistics.
- Study and solver configuration.
- Stationary, time-dependent and parametric computations where verified.
- Computation monitoring, cancellation and timeout.
- Result evaluation and export.
- MPH save, reload and verification.

**C. Execution reliability**

- Independent Worker process.
- COMSOL Server ownership and process tracking.
- Windows Job Object or equivalent process-tree containment.
- Non-interactive Server startup and authentication handling.
- Resource limits and execution timeouts.
- Server working-directory independence.
- Absolute file path enforcement.
- Pre-solve static and mesh gates.
- Error classification and recovery recommendations.
- Original-model and artifact protection.

**D. Scientific reliability**

- Dimensionally explicit parameter management.
- Geometric selection validation.
- Mesh quality assessment.
- DOF and computational budget assessment.
- Finite-value and solution-integrity checks.
- Conservation and balance checks where physically defined.
- Optional mesh and time-step convergence audits.
- Analytic, numerical and experimental baseline comparisons.
- Evidence-based validation reports.

**E. Extensibility**

- Version-specific API knowledge.
- Reusable physics profiles.
- Typed Manifest structure.
- Independent tests and benchmark cases.
- Controller-level multi-run orchestration.
- Later addition of MCP adapters if actual usage justifies them.

### Out of scope

- Claiming support for every COMSOL physics interface in V1.
- A dedicated application for a single material, scientific discipline or research project.
- Storing test-case scientific parameters or conclusions in production Skill instructions.
- Arbitrary autonomous changes to the user's physics or numerical assumptions.
- GUI mouse-coordinate automation as the primary execution mechanism.
- HPC clusters and distributed remote simulation management in V1.
- Unauthorized access to, modification of or redistribution of COMSOL software.
- Bypassing COMSOL license and module restrictions.
- An unnecessarily large MCP Server implementation before the execution engine has been validated.
- Fully automatic physics discovery from arbitrary existing MPH files.
- Automatic high-concurrency parameter or mesh sweeps without resource and license approval.

## 5. Architecture / constraints

### 5.1 Runtime

- COMSOL Multiphysics 6.4.
- Windows 64-bit.
- Python 64-bit, with the exact interpreter identified at runtime.
- MPh with a pinned, tested dependency version.
- COMSOL native Java API.
- Agent Skills-compatible runtime.
- JSON Schema for Manifest validation.

Do not hardcode the developer's installation path or Python environment.

### 5.2 Process-isolated execution architecture

This is a mandatory architectural requirement.

Use the following logical execution structure:

    Agent
      |
      v
    COMSOL Skill
      |
      v
    Task Controller
      |
      +---- task specification and approval
      +---- immutable parent/child task records
      +---- resource and license scheduling
      |
      v
    Isolated Python Worker
      |
      +---- MPh client
      |
      +---- owned COMSOL Server process
      |
      v
    COMSOL 6.4 computation
      |
      v
    Independent task output directory
      |
      v
    Verification and aggregation

**Execution rules:**

1. The Task Controller must remain responsive while COMSOL is solving.
2. Every managed computation must have a unique Job ID.
3. The Worker must run in an isolated OS process.
4. Prefer an independently owned COMSOL Client-Server session for production computations.
5. The Worker must track the COMSOL Server PID and every process it owns or launches.
6. Record process ownership, creation time, task identity, start time, timeout and termination status.
7. Use a Windows Job Object configured with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, or an equivalently reliable process-tree management mechanism.
8. Prevent unintentional process escape from the managed Job Object.
9. Where necessary, create suspended processes, assign them to the Job Object and then resume execution to avoid process-assignment races.
10. The Worker, COMSOL Server and their owned computational children must be accounted for in the same task lifecycle.
11. Request graceful cancellation before hard termination.
12. Hard termination is permitted only for a process tree demonstrably owned by the current task.
13. The system must not terminate an existing user-owned COMSOL Desktop or unrelated Server process.
14. Do not attach strict-timeout tasks to shared or externally owned sessions.
15. Use one managed COMSOL execution session by default.
16. Parallel computation requires explicit resource and license validation.

Stand-Alone MPh mode may be evaluated as an alternative only when the JVM and all COMSOL work are contained within the isolated Worker and hard process termination has been demonstrated.

The chosen COMSOL 6.4 execution backend must pass an actual process-lifecycle test before being accepted.

### 5.3 COMSOL Server startup, authentication and cleanup contract

This is a mandatory implementation contract for Windows.

The Worker must not assume that creating an MPh Client automatically starts or manages an independent COMSOL Server.

The Server lifecycle is divided into:

1. Locate the COMSOL 6.4 server executable.
2. Prepare an isolated task workspace.
3. Prepare non-interactive authentication.
4. Start the owned Server process.
5. Obtain its listening port and verify readiness.
6. Establish the MPh connection.
7. Execute one task.
8. Disconnect the client.
9. Terminate or shut down the owned Server.
10. Verify process-tree cleanup and record the final state.

**A. Executable discovery**

- Discover comsolmphserver.exe from the verified COMSOL 6.4 installation.
- Verify executable existence and version.
- Record the exact executable path.
- Do not hardcode a developer-specific installation location.

**B. Non-interactive startup**

Investigate and test COMSOL 6.4 server command-line options, including:

- -login auto
- -silent
- -port 0
- -portfile with an absolute path

These are candidate mechanisms, not an unconditionally fixed command.

Requirements:

- Avoid an interactive first-start login prompt blocking the Worker.
- Test -login auto behavior in a controlled environment.
- Confirm that the generated credentials are usable by the selected MPh authentication path.
- Check whether COMSOL creates or updates %USERPROFILE%\.comsol\v64\login.properties.
- Protect login files with appropriate Windows account permissions.
- Never print credentials in console output or execution logs.
- Never commit login files or credentials to Git.
- Evaluate -passwd nostore where the selected authentication flow supports it.
- Do not delete or replace existing user login configuration without explicit authorization.
- If automatic authentication is not reliable, provide a secure one-time initialization procedure instead of silently requesting interactive input during production execution.

**C. Port allocation and readiness**

- Prefer a per-task dynamically allocated port where supported.
- Use -portfile or an equivalent verified readiness mechanism.
- Do not assume a process has become ready merely because subprocess.Popen returned.
- Verify that the expected port is listening.
- Establish a real MPh connection before reporting Server startup success.
- Protect port files as task-specific temporary data.
- Clean them up after the task ends.
- Avoid exposing the Server unnecessarily to external network interfaces.
- Apply appropriate local firewall restrictions.

**D. Process cleanup**

- Assign the Worker and owned COMSOL processes to the managed Job Object or verified equivalent.
- Enable kill-on-job-close behavior.
- Record all owned process IDs.
- Perform graceful shutdown first.
- Verify that the Server and all task-owned computational children have exited.
- Escalate to process-tree termination only when required.
- Check for orphaned COMSOL processes after forced Worker or Server termination.
- Do not claim license release until the relevant COMSOL processes have actually terminated; distinguish process cleanup evidence from license-manager observations.

**E. Server working directory and file paths**

COMSOL may resolve relative paths according to the Server's working directory, model directory or model path, rather than the Python Worker's current directory.

Therefore:

- The controller resolves logical output paths before dispatch.
- Every file path sent to COMSOL Java API operations must be an absolute, normalized path.
- This applies to model.save, export nodes, import data, external data files, image export and other file operations.
- Resolve any relative path inside a task Manifest before calling the API.
- Validate directory existence and write permissions.
- Validate that the Server process can access the target path.
- Do not rely on the Server's current working directory.
- Record the Server working directory for diagnosis.
- The model's external dependencies must use explicit locations.

A relative path must not be passed directly to a production Java API file operation.

### 5.4 Worker atomic execution contract

This is mandatory for all standard and convergence-audit computations.

**The Worker contract is:**

**One Manifest → One managed COMSOL execution → One solve → One independent output directory.**

Each Worker invocation must be an isolated, independently auditable execution unit.

Rules:

1. A Worker receives exactly one immutable task Manifest.
2. It creates one unique Job ID and one unique output directory.
3. It performs model construction or an authorized patch.
4. It executes the pre-solve validation gates.
5. It performs one designated solve operation.
6. It extracts the declared target quantities.
7. It writes the execution report and evidence.
8. It finalizes the task output and returns a compact result record.
9. It does not keep a COMSOL model in memory for the next independent task.
10. It does not modify another Worker's output directory.
11. It does not silently reuse an unrelated Server or model session.

**Failure preservation:**

- Save the build or patched model checkpoint after successful construction and pre-solve validation, before the expensive solve.
- Preserve pre-solve model, Manifest, logs and completed intermediate results when a solve fails or is terminated.
- Use a unique task workspace.
- Write important files to temporary paths and finalize them atomically where practical.
- A failed child task must not invalidate successfully completed sibling tasks.

**Task output structure:**

    runs/
      <parent_task_id>/
        parent_manifest.json
        child_tasks.json
        aggregation_report.md

        <child_task_id>/
          manifest.json
          pre_solve_model.mph
          solved_model.mph
          results/
          logs/
          metrics.json
          verification_report.md
          execution_status.json

Files that do not exist because a task failed must be explicitly marked unavailable rather than represented by empty success artifacts.

The Worker must never overwrite another task's output or a user-provided source model.

### 5.5 Manifest architecture

Use a hybrid design:

**Strongly typed top-level specification + loosely coupled, versioned API Profiles.**

The canonical Manifest must contain nine domain sections:

1. parameters
2. geometry
3. selections
4. materials
5. physics
6. mesh
7. study
8. outputs
9. validation

Also include a metadata/execution envelope containing:

- schema_version
- comsol_version
- mode
- source_model, when applicable
- execution_limits
- expected_outputs
- parent_task_id, when applicable
- task_id
- variant_id, when applicable

The Manifest must not become a general-purpose programming language or unrestricted Java code container.

**API Profiles**

Store verified COMSOL feature definitions under:

skills/comsol-6.4/references/comsol-6.4/profiles/

A reusable profile should describe:

- COMSOL version.
- Physics interface and Java API type.
- Required feature and subfeature types.
- Supported property names and value types.
- Required material properties.
- Expected entity dimensions and selections.
- Applicable boundary conditions.
- Verified limitations.
- Test and evidence identifiers.

Physics-specific complexity belongs in Profiles, not in an ever-expanding rigid global Schema.

Unknown properties and feature types must not be guessed.

### 5.6 Geometry and entity selection stability

Persistent model definitions must not depend on unverified, hardcoded integer entity indices.

Use semantic geometric selections as the primary strategy:

1. Named or cumulative selections associated with geometry construction.
2. Coordinate-based selections such as Box, Ball, Cylinder or Disk where the geometry makes them semantically appropriate.
3. Object-based or other explicitly verified selection methods where appropriate.

Coordinate selection is not universally reliable. Every selection must be validated after geometry finalization.

Required checks:

- Expected geometric entity dimension.
- Selected entity count.
- Empty-selection detection.
- Geometric location.
- Bounding box or other relevant geometric signature.
- Area, volume or length when applicable.
- Expected relationship to the intended physical region.
- Whether a parameter change or Boolean operation altered the selection.

The Manifest must store selection semantics, not stale runtime indices.

Bare entity indices may only be used as temporary execution-level identifiers when they have just been obtained from the current finalized geometry and validated against the intended selection.

They must not be persisted as reusable selection definitions across geometry regeneration.

If a selection cannot be verified, stop before solving.

### 5.7 Unit and dimensional consistency

All dimensional numerical quantities must carry explicit unit information.

Use a typed representation such as:

    {
      "value": 5,
      "unit": "mm"
    }

For dimensionless quantities, explicitly use unit 1.

For mathematical expressions, use a separate typed expression representation with a declared expected physical dimension or unit.

The requirements apply to relevant material properties, physics settings, boundary conditions, mesh dimensions, study times and output quantities.

The execution engine must:

1. Validate units and physical dimensions before writing values to COMSOL.
2. Preserve the user's original value and unit in the execution record.
3. Generate explicitly unit-qualified COMSOL expressions.
4. Check that expressions evaluate to the expected physical dimension.
5. Detect unknown variables, invalid expressions and inconsistent units.
6. Collect available COMSOL unit diagnostics from supported API messages, warning nodes and computation logs.
7. Treat unresolved unit mismatch warnings as blocking by default.
8. Allow an exception only after an explicit, documented user decision.

Do not assume every unit warning can be retrieved through a single uniform API method. Its actual COMSOL 6.4 extraction mechanism must be investigated and tested.

The absence of a reported warning does not replace dimensional validation.

### 5.8 Pre-Solve Dry-Run Gate

A mandatory execution gate must exist between model construction and Study computation.

No formal computation may start before all required pre-solve checks pass or an explicitly authorized exception is recorded.

**Gate A — Geometry**

- Geometry sequence successfully finalized.
- No blocking geometry errors.
- Required domains and boundaries exist.
- Geometric selection checks pass.
- Empty or invalid regions are detected.
- Available geometry warnings are recorded.

**Gate B — Selections**

- All required physical feature selections are non-empty.
- Entity dimensions are correct.
- Selection location and geometric signatures match expectations.
- No stale entity indices are being reused.
- Parameterized geometry has not silently changed the intended selection.

**Gate C — Materials**

- Every active physical region has the required material assignment.
- Required properties are defined.
- Property expressions can be evaluated where required.
- Relevant property units are dimensionally consistent.
- Undefined material properties are reported.

**Gate D — Physics**

- Every configured physics interface exists.
- Its selected domains and boundaries are appropriate.
- Required features and boundary conditions are present.
- Critical settings are not silently left at unintended defaults.
- Required module licenses are available.

**Gate E — Expressions and units**

- Manifest expression validation passes.
- Critical parameter and property expressions are evaluable.
- Expected dimensions agree.
- Unit mismatch diagnostics have been reviewed.
- Blocking warnings prevent execution.

**Gate F — Study and Solver Sequence**

- Study steps are valid.
- Required physics interfaces are included.
- The default solver sequence is generated when needed.
- Solver configuration references existing nodes.

When creating or rebuilding the solver sequence, use the COMSOL 6.4 supported operation:

    study.createAutoSequences("all")

as appropriate, after defining the Study and before configuring custom solver nodes.

Do not assume model.sol("sol1") exists immediately after Study creation.

Do not regenerate solver sequences blindly after applying custom solver settings.

**Gate G — Mesh**

- Mesh generation succeeds.
- Mesh is not empty.
- Required geometric entities are completely meshed.
- Record total elements and relevant element types.
- Record minimum and average element quality.
- Record the quality measure used.
- Detect incomplete or problematic mesh sequences.

Mesh quality must be evaluated using the metric appropriate to the geometry and physical problem.

There is no universal acceptable minimum-quality threshold for every simulation. Thresholds must be defined by validated physics profiles or task-specific requirements.

**Gate H — DOF and Computational Budget**

DOF assessment must occur after the Study and required solver sequence have been created.

The system must not assume that mesh statistics alone provide the actual physics-dependent number of degrees of freedom.

Required implementation sequence:

1. Complete Gate F and generate the required default solver sequence.
2. Identify the corresponding Compile Equations feature for the intended Study step.
3. Probe the COMSOL 6.4-supported mechanism for computing equation-assembly statistics without executing the full numerical solve.
4. Obtain DOF information from the Compile Equations Statistics interface or the verified Java API mechanism, such as xmeshInfo().nDofs(), where supported.
5. Record the DOF count and, where available, its breakdown by field.
6. Release auxiliary Xmesh/DOF inspection resources when appropriate.
7. Compare the measured DOF and resource estimates against the user-defined safety budget.

Do not mandate an unverified method such as sol.compile() as the universal implementation.

The exact COMSOL Java API call sequence must be established by a minimal COMSOL 6.4 probe.

**Important resource distinction:**

Equation assembly or DOF statistics computation may itself consume significant time and memory for large models.

Therefore:

- Apply a preliminary resource estimate before requesting expensive DOF statistics.
- Treat DOF compilation as a separately observable preflight operation.
- Give it a configurable timeout and resource budget.
- Do not confuse a compile/statistics operation with a completed solve.
- If actual DOF retrieval is unavailable or would exceed the safety budget, report that limitation and provide a clearly labelled estimate where possible.
- Do not fabricate an actual DOF count from mesh element statistics.

Pause and request approval when configured safety budgets are exceeded or the resource requirement cannot be assessed reliably.

**Gate result:**

- PASS: all required checks passed.
- BLOCKED: one or more critical checks failed.
- REQUIRES_APPROVAL: a non-default exception or resource override requires user authorization.

### 5.9 Convergence Audit and multi-run orchestration

The Convergence Audit is an optional, controller-managed workflow.

It must not be implemented as a long-running loop that repeatedly modifies and overwrites one in-memory COMSOL model.

**Core ownership rule:**

The Task Controller owns multi-run orchestration.

The Worker owns only one atomic computation.

**Mesh convergence procedure:**

1. Start from one frozen parent Manifest and approved physical specification.
2. Define the baseline mesh strategy and a declared refinement strategy.
3. Derive multiple child Manifests for the selected mesh levels.
4. Give each child a unique task_id and variant_id.
5. Keep material properties, geometry, physical conditions, solver choices and target evaluation definitions consistent unless the approved protocol explicitly requires otherwise.
6. Change only the declared mesh refinement parameters between child tasks.
7. Dispatch each child independently to the Worker.
8. Preserve each task's own MPH model, logs, results and scalar metrics.
9. Aggregate the comparable outputs in the controller-level verification layer.

Formal mesh convergence should use at least three mesh levels where feasible.

**Time-step sensitivity procedure:**

- Derive independent child Manifests from the same reviewed physical specification.
- Change only the declared time-resolution settings.
- Compare the same physical quantities at consistent physical times.
- Preserve each run independently.
- Aggregate the results in the parent audit.

**Child task requirements:**

Each child Manifest must include:

- Parent task ID.
- Unique child task ID.
- Refinement or time-step variant ID.
- Frozen base Manifest fingerprint.
- Explicit parameter override/diff.
- Expected target observables.
- Validation thresholds.
- Independent output location.

**Scheduling rules:**

- Execute sequentially by default to protect license and memory availability.
- Parallel execution is optional and requires explicit resource and licensing checks.
- A failed or OOM child task must not invalidate earlier completed child outputs.
- Retrying one failed child must not rerun successful siblings.
- The controller must be able to resume aggregation from stored child results.

**Aggregation rules:**

Compare only physically and numerically comparable results.

Calculate the declared convergence metrics and, where applicable, Richardson extrapolation or Grid Convergence Index (GCI) under their valid assumptions.

Do not report a GCI when the assumptions or input refinement information are insufficient.

There is no universal requirement to use a fixed refinement factor such as 0.7 or a universal 1% convergence threshold.

The refinement strategy and acceptable tolerance must be specified by the user, scientific task or an approved physics profile.

Unexpectedly expensive audit runs require user approval before execution.

### 5.10 Solver and computation management

The execution layer must support:

- Study creation and verification.
- Default solver sequence generation.
- Verified solver configuration.
- Equation compilation/statistics inspection where required.
- Stationary and time-dependent execution.
- Parametric studies where supported.
- Progress reporting.
- Cancellation.
- Timeout handling.
- Resource limits.
- Raw solver log preservation.
- Error classification.

Solver modifications must not silently change the intended physics.

Any proposed modification to tolerances, stabilization, nonlinear ramping, time-step policy or other numerically meaningful settings must be reported.

Physics-changing and result-targeting adjustments require user authorization.

Each Worker invocation executes one designated solve. Multiple independent variants must be scheduled and aggregated by the Task Controller.

### 5.11 Conservation and physical balance checks

Support reusable conservation-check definitions.

Where scientifically applicable, a physics profile or reviewed Manifest may define:

- Conserved quantity.
- Control volume or domain.
- Inlet and outlet boundaries.
- Source and sink terms.
- Sign convention.
- Required integral expressions.
- Expected balance residual.
- Acceptable error threshold.

The execution layer may construct the required COMSOL integration operators, including surface and volume integration functionality, when the definitions are sufficiently specified.

Do not automatically invent or inject a conservation equation into every physics model.

A conservation test without correctly defined physical terms and boundary selections must not be reported as passed.

### 5.12 Dual-view approval and error explanation

The Agent must provide concise, human-readable explanations alongside machine-readable task files.

The error classifier should cover at least:

- Environment and version mismatch.
- Java/API initialization.
- Server startup and authentication.
- Server port and connection failure.
- License and module restrictions.
- Geometry construction failure.
- Empty or incorrect selection.
- Undefined material properties.
- Unit mismatch.
- Invalid expressions.
- Mesh generation and quality failure.
- Singular matrices.
- NaN/Inf and undefined field values.
- Linear or nonlinear solver non-convergence.
- Memory/resource exhaustion.
- Timeout and process failure.
- Orphaned Server or computation process.
- Output path and permission failures.
- Result extraction or persistence failure.

For each error, report:

1. Original COMSOL error message and relevant log evidence.
2. Error category.
3. Likely causes and confidence.
4. Recommended diagnostic checks.
5. Whether a proposed change would affect physics or numerical assumptions.
6. Worker and Server cleanup state.

Diagnostic suggestions must not automatically modify scientific parameters.

### 5.13 Version-specific API knowledge and cache

Maintain an exact-version knowledge base:

references/comsol-6.4/

Do not mix verification evidence between COMSOL versions.

Use explicit feature states:

- discovered: API type or property identified.
- probe_passed: minimal API operation succeeded.
- integration_tested: operation passed a reusable integration test.
- validated: operation passed the specified numerical or physical validation.

A feature must not be promoted into a stronger state without corresponding evidence.

Cache entries must include:

- COMSOL version.
- API class/feature/property.
- Python and MPh versions where relevant.
- Probe date.
- Verification range.
- Test identifier.
- Evidence and known limitations.
- Integrity hash for the relevant reference or profile.

Only verified functionality may be advertised as supported by V1.

### 5.14 Skill and repository structure

Separate the installable Skill from development governance, tests and project documentation.

Proposed structure:

    Comsol_run/
    |
    |-- README.md
    |-- TASK_PLAN.md
    |-- STATUS.md
    |-- pyproject.toml
    |-- config.example.toml
    |-- .gitignore
    |
    |-- skills/
    |   |-- comsol-6.4/
    |       |-- SKILL.md
    |       |-- scripts/
    |       |-- references/
    |       |   |-- comsol-6.4/
    |       |   |   |-- api/
    |       |   |   |-- profiles/
    |       |   |   |-- troubleshooting/
    |       |-- schemas/
    |       |-- templates/
    |
    |-- tests/
    |   |-- unit/
    |   |-- integration/
    |   |-- comsol-6.4/
    |   |-- fixtures/
    |   |-- benchmarks/
    |
    |-- docs/
    |   |-- architecture/
    |   |-- installation/
    |   |-- verification/
    |   |-- reports/
    |
    |-- tools/
        |-- skill_install/
        |-- development/

The installable Skill root is:

skills/comsol-6.4/

It must contain only runtime-relevant instructions, scripts, references, schemas and generic templates.

Development tests, benchmark case data, execution reports and governance documents must remain outside the production Skill directory.

Test datasets must never become production instructions or hardcoded scientific behavior.

### 5.15 Security and permissions

- Do not bypass COMSOL licensing.
- Never overwrite an original user MPH model.
- Hash and record source models used in patch mode.
- Keep credentials, license data and machine-specific configuration outside version control.
- Restrict process termination to demonstrably owned processes.
- Require authorization for expensive simulations and resource-budget overrides.
- Do not silently launch parallel COMSOL sessions.
- Do not embed arbitrary execution code in the Manifest.
- Maintain separate source, working, temporary and output files.
- Normalize all Java API file paths to absolute paths.
- Protect COMSOL login information and task credentials.
- Log all model-changing and solver-changing operations.

## 6. Acceptance criteria

All 37 original acceptance criteria are retained. Milestone labels specify the intended delivery stage, not a reduction in final acceptance requirements.

### Skill and specification

- [ ] AC-01 [M1]: An Agent can recognize a COMSOL task and load the correct Skill.
- [ ] AC-02 [M1]: The Skill operates independently of repository governance and test directories.
- [ ] AC-03 [M1]: Natural-language requirements can be transformed into a validated, schema-compliant Manifest.
- [ ] AC-04 [M1]: The Manifest contains the nine required domain sections and version/mode metadata.
- [ ] AC-05 [M2]: Both build and controlled patch execution modes are supported.
- [ ] AC-06 [M1]: The user receives the scientific summary and Manifest draft before model execution.
- [ ] AC-07 [M1]: Missing scientific assumptions cannot be silently invented.

### Environment and process reliability

- [ ] AC-08 [M0]: The actual COMSOL 6.4 installation and Python environment can be detected.
- [ ] AC-09 [M0]: A real COMSOL 6.4 Client-Server connection can be established and verified.
- [ ] AC-10 [M0]: Each managed task executes in an isolated Worker.
- [ ] AC-11 [M0]: Worker and owned COMSOL process identities can be tracked reliably.
- [ ] AC-12 [M0]: A controlled timeout test demonstrates graceful cancellation and safe termination of the process tree owned by the task.
- [ ] AC-13 [M0]: User-owned COMSOL processes and unrelated processes remain unaffected.
- [ ] AC-14 [M0]: A model can be created, saved, reloaded and inspected in COMSOL 6.4.

### Modeling and numerical execution

- [ ] AC-15 [M1]: A basic model can be created using verified geometry, material, physics, selection and mesh APIs.
- [ ] AC-16 [M1]: Geometric selections are validated for dimension, count and intended location.
- [ ] AC-17 [M1]: Persistent parameterized model definitions do not depend on unverified naked entity indices.
- [ ] AC-18 [M1]: Dimensional quantities use explicit units and are checked before COMSOL execution.
- [ ] AC-19 [M1]: The correct solver sequence is generated before customized solver settings are applied.
- [ ] AC-20 [M1]: The mandatory Pre-Solve Dry-Run Gate blocks invalid or incomplete models.
- [ ] AC-21 [M1]: Mesh statistics, including element count and quality, are available in the verification report.
- [ ] AC-22 [M1]: Actual DOF or an explicitly identified resource estimate is evaluated against configured execution limits.

### Scientific verification

- [ ] AC-23 [M1]: At least one real COMSOL 6.4 model completes a numerical computation.
- [ ] AC-24 [M1]: At least one supported case passes an independently defined analytic or quantitative reference check.
- [ ] AC-25 [M1]: The validation system distinguishes API, numerical, physical and reproduction success.
- [ ] AC-26 [M2]: Optional mesh convergence validation works on a controlled test case.
- [ ] AC-27 [M2]: Optional time-step sensitivity validation works on a controlled transient test case.
- [ ] AC-28 [M2]: Configured conservation checks produce reproducible numerical balance results.
- [ ] AC-29 [M1]: Relevant unit warnings and other blocking diagnostics are reported and prevent unapproved execution.
- [ ] AC-30 [M1]: No unsupported API feature can be silently treated as verified.

### Persistence, reporting and regression

- [ ] AC-31 [M1]: Results can be exported to usable numerical data and image formats.
- [ ] AC-32 [M1]: Saved MPH files can be reloaded and their key model structures and results inspected.
- [ ] AC-33 [M1]: The system produces a reproducible execution and scientific validation report.
- [ ] AC-34 [M1]: Source models are protected against unauthorized modification.
- [ ] AC-35 [M2]: Error diagnostics preserve original COMSOL messages and provide actionable explanations.
- [ ] AC-36 [M2]: Regression tests prevent previously verified API and execution behavior from silently degrading.
- [ ] AC-37 [M1]: Production Skill files contain no test-case-specific scientific assumptions or machine-specific paths.

**Full V1 acceptance requires all AC-01 through AC-37 to pass.**

## 7. Tests / evidence

### 7.1 M0 — Required feasibility Spike

This is the first implementation activity after plan approval.

The purpose is to prove the local COMSOL 6.4 execution architecture before constructing the broader framework.

Required evidence:

1. COMSOL version and executable discovery.
2. Python architecture and exact interpreter.
3. MPh and JPype versions.
4. COMSOL Server startup with no interactive login blockage.
5. Authentication using the selected MPh connection method.
6. Dynamic port allocation and Server readiness verification.
7. Worker isolation.
8. Server process ownership and Job Object assignment.
9. Graceful shutdown.
10. Controlled timeout and process-tree termination.
11. No impact on unrelated user-owned COMSOL sessions.
12. Verification that no task-owned COMSOL process remains orphaned.
13. Absolute-path model save and reload.
14. Creation, save and reload of a minimal model.
15. Evidence that a Worker timeout does not falsely report successful cleanup before actual process termination.

Specific first-start test cases:

- A clean or isolated COMSOL authentication profile.
- A previously initialized login profile.
- COMSOL Server startup using a tested non-interactive authentication configuration.
- A connection failure and timeout during Server initialization.
- Worker termination while Server remains active.

Do not overwrite or destroy the user's existing COMSOL authentication configuration to conduct these tests.

**DOF-specific M0 probe**

Investigate the COMSOL 6.4 Compile Equations sequence.

The probe must determine:

- How createAutoSequences("all") produces the required solver structure.
- How to identify the appropriate Compile Equations feature.
- Whether its Statistics or Java xmeshInfo() interface can provide actual DOFs without running the complete numerical solve.
- The resource cost of retrieving that information.
- How to release temporary Xmesh inspection data.

Do not assume a generic sol.compile() call exists or is the correct public interface.

The M0 result must document the exact tested API sequence or explicitly report that a non-solving DOF route has not been confirmed.

**M0 exit gate**

Do not begin full framework implementation until:

- COMSOL 6.4 is discoverable.
- Server startup and authentication work.
- MPh connects successfully.
- Worker and Server lifecycle management is proven.
- Timeout cleanup is demonstrated.
- A minimal model can be created, saved and reloaded.

If a blocking issue occurs, report the technical evidence and propose a revised execution backend. Do not build the remaining architecture on an unverified backend.

### 7.2 M1 — Core Closed-Loop MVP

After M0 passes, implement and validate:

1. Installable Skill and entry point.
2. Typed nine-section Manifest.
3. Human-readable scientific summary.
4. Build mode.
5. Generic geometry and selection execution.
6. Verified API Profile mechanism.
7. Explicit unit validation.
8. Pre-Solve Gates A–H.
9. Solver sequence generation.
10. DOF preflight where confirmed by M0.
11. Isolated execution and independent artifact directories.
12. One real physical simulation.
13. Numerical and physical benchmark comparison.
14. Result extraction and visualization.
15. Four-level success report.

The MVP must demonstrate a complete closed loop from natural-language requirements to a reusable and independently validated MPH model.

### 7.3 M2 — Advanced Capabilities and Full Acceptance

Implement and validate:

1. Guarded patch mode for existing MPH models.
2. Parent/child task Manifest derivation.
3. Independent multi-run execution.
4. Mesh Convergence Audit.
5. Time-Step Sensitivity Audit.
6. GCI or other justified convergence metrics.
7. Controller-level aggregation and resumability.
8. Configurable conservation and balance checks.
9. Extended error-classification coverage.
10. Full abnormal-condition injection tests.
11. Comprehensive regression suite.
12. Full acceptance verification for AC-01 through AC-37.

### 7.4 Required integration tests

- Geometry creation and regeneration.
- Boolean-operation and parameter-change selection stability.
- Named/cumulative and spatial selection validation.
- Material assignment and required-property checks.
- Unit and dimension validation, including intentionally invalid expressions.
- Study configuration and automatic solver-sequence creation.
- DOF preflight and resource estimation.
- Mesh completeness and element-quality retrieval.
- Pre-Solve Gate blocking behavior.
- Controlled Server startup, shutdown and cancellation.
- Absolute-path model save, external file loading and image export.
- Numerical result extraction and image export.
- Save/reload persistence.

### 7.5 Required scientific benchmarks

Select simple, physically meaningful cases that can be independently checked.

The first benchmark must:

- Use only functionality available in the installed COMSOL 6.4 license.
- Have a defined physical specification.
- Have an independent analytical or quantitative reference.
- Be sufficiently small for repeatable testing.
- Verify the full workflow from model construction to scientific validation.

Subsequent benchmarks should include:

- A model suitable for mesh convergence testing.
- A transient model suitable for time-step sensitivity testing.
- A case with clearly defined conservation or balance equations.

The selected test cases must remain in tests/ and must not become hardcoded production Skill rules.

### 7.6 Required failure tests

Intentionally test:

- Invalid geometry.
- Empty boundary selection.
- Incorrect entity dimension.
- Missing material property.
- Invalid unit.
- Unknown variable.
- Invalid solver reference.
- Mesh-generation failure.
- Non-finite numerical output.
- Solver non-convergence.
- License failure.
- Interactive Server login blocking.
- Server startup failure.
- Invalid port or failed connection.
- Timeout.
- Worker termination.
- Server termination.
- Orphaned process detection.
- Relative path rejection.
- Insufficient output-directory permissions.
- Source-model hash mismatch.
- Save/reload failure.
- Failed convergence child task.
- Aggregation with missing or incompatible child results.

Each failure must be classified correctly and produce sufficient diagnostic evidence.

### 7.7 Convergence regression tests

- All child runs originate from the same frozen parent specification.
- Each child receives a unique task ID and output directory.
- Mesh refinement changes only authorized mesh settings.
- Time-step refinement changes only authorized time-resolution settings.
- Child results remain available after sibling failure.
- Retrying a failed child does not rerun completed siblings.
- Aggregation does not include failed or incomparable results.
- GCI is not calculated when its assumptions are not satisfied.
- A completed parent audit preserves all child evidence.

### 7.8 Regression tests

- Existing verified API profiles remain functional.
- Parameterized geometry does not silently change physical selections.
- Manifest validation remains consistent.
- Solver customization is not erased by accidental sequence regeneration.
- Unit validation remains active.
- Pre-Solve Gate cannot be bypassed through the normal execution workflow.
- Source MPH files remain unchanged in patch mode.
- Test data do not leak into production Skill instructions.
- Relative file paths are not sent directly to COMSOL file operations.
- Worker failure cannot cause unrelated Server termination.
- Failure or timeout states cannot be reported as completion.

### 7.9 Manual acceptance

Final real-world acceptance must use the user's local COMSOL 6.4 environment.

The user must be able to:

- Execute the Skill through the intended Agent.
- Inspect the generated model in COMSOL Desktop.
- Verify the actual geometry and physical selections.
- Inspect the generated mesh and solver configuration.
- Reopen the delivered MPH model.
- Inspect numerical outputs and validation evidence.
- Inspect independent output directories for each child simulation.
- Verify that a failed child task does not destroy successful results from earlier runs.

Developer self-tests and integration tests do not substitute for final user acceptance.

## 8. Deliverables

### Core production files

- skills/comsol-6.4/SKILL.md
- Isolated COMSOL Worker and execution controller.
- MPh/Java API backend.
- Process lifecycle and timeout manager.
- COMSOL Server startup and authentication manager.
- Port allocation and readiness verification.
- Windows Job Object/process-tree management.
- Absolute-path normalization and validation.
- Manifest JSON Schema.
- Generic Manifest parser and executor.
- Build and patch mode support.
- Geometry selection validator.
- Unit and dimensional consistency validator.
- Pre-Solve Dry-Run Gate.
- Solver sequence and DOF inspection manager.
- Result extraction and export modules.
- Numerical and scientific verification engine.
- Optional convergence audit.
- Controller-level child-task orchestration and aggregation.
- Conservation-check framework.
- Error classification and diagnostic references.
- COMSOL 6.4 API profiles and evidence records.

### Repository governance and documentation

- TASK_PLAN.md: frozen development contract.
- STATUS.md: milestones, execution progress, decisions, risks and handovers.
- README.md: installation and entry-point guidance.
- config.example.toml: machine-specific settings template.
- .gitignore: excludes private configuration, caches and simulation artifacts.
- Architecture and installation documentation.
- Verification and test reports.

### Required initial STATUS.md structure

The initial STATUS.md must establish the following milestones.

**M0 — Feasibility Spike**

Objective: Prove the actual Windows COMSOL 6.4 backend and its managed lifecycle.

Deliverables:

- Environment discovery report.
- Server startup and authentication report.
- Worker/Server process lifecycle report.
- Job Object and timeout evidence.
- Absolute-path behavior evidence.
- DOF preflight feasibility report.
- Minimal MPH creation/save/reload evidence.

Exit: All M0 mandatory checks pass, or a documented blocker is approved for resolution.

**M1 — Core Closed-Loop MVP**

Objective: Deliver a usable first version of the general Skill.

Deliverables:

- Skill installation and activation.
- Manifest Schema and parser.
- Build mode.
- Verified API Profiles.
- Pre-Solve Gates A–H.
- Single-task Worker.
- One complete scientific benchmark.
- Result exports and four-level validation report.

Exit: The core end-to-end simulation works on COMSOL 6.4 and satisfies all M1 acceptance requirements.

**M2 — Advanced Capabilities and Full Acceptance**

Objective: Complete the remaining general capabilities and full validation.

Deliverables:

- Patch mode.
- Multi-run Controller.
- Mesh and time-step convergence audits.
- Conservation checks.
- Full failure testing and regression coverage.
- Full AC-01 through AC-37 verification.
- Final documentation and release candidate.

Exit: All 37 acceptance criteria pass and the user completes final manual acceptance.

### Evidence and artifacts

- COMSOL 6.4 environment report.
- Process-isolation and termination test evidence.
- Server authentication and startup evidence.
- DOF preflight evidence.
- API compatibility records.
- Model construction and save/reload evidence.
- Numerical benchmark reports.
- Mesh and time-step convergence reports.
- Scientific validation reports.
- Reproducible example files in the separate test directory.
- Multi-run aggregation evidence.

## 9. Release boundary

- [ ] Code/files only; do not publish.
- [ ] Prepare a release candidate; wait for my approval before publishing.
- [x] Other:

**Approved action: freeze this TASK_PLAN.md in the repository only.**

This commit does not authorize creation of STATUS.md or .gitignore, environment changes, dependency installation, COMSOL execution or implementation work.

After this Task Plan is committed:

1. Preserve the approved objective, scope, architecture and acceptance criteria.
2. Create the initial STATUS.md and .gitignore only when separately authorized as the next repository-initialization action.
3. Begin M0 only after the initialization boundary and execution authorization are confirmed.
4. Record implementation progress, test evidence, blockers and decisions in STATUS.md.
5. Request approval for changes that materially alter the frozen requirements.

Repository commits do not constitute permission to publish a formal release or distribute a completed package.

All future public releases require separate user approval.

## 10. User decisions already made

- The installed COMSOL version is 6.4.
- The target repository is Tuzhidingdong/Comsol_run.
- The objective is a general-purpose COMSOL Agent Skill, not a single-domain simulation application.
- The project must be suitable for Agent-driven local scientific simulation.
- The user owns the Task Plan and approval process.
- The Task Plan must be reviewed and frozen in the repository before implementation.
- The sibling STATUS.md is used for implementation progress and cross-session handover.
- COMSOL 6.4 is the initial formal compatibility and acceptance baseline.
- Scientific assumptions and physical-model decisions must remain visible to the user.
- Successful numerical execution must not be confused with scientific validation.
- Existing research cases and test datasets must not contaminate the general production Skill.
- Unverified COMSOL APIs must be probed and evidenced before being treated as supported.
- No source MPH model may be overwritten without explicit authorization.
- The user must retain final acceptance authority for the actual local simulation workflow.
- Reuse of external source code requires a verified compatible license; architectural ideas may be studied independently.
- Execution must use an isolated Worker and a demonstrably owned COMSOL Server process for managed computations.
- Non-interactive Server startup and authentication must be verified before production execution.
- All COMSOL file operations must use normalized absolute paths.
- A Worker invocation is one Manifest, one solve and one independent output directory.
- Multi-run convergence audits are orchestrated by the Task Controller, not by a persistent Worker model.
- DOF inspection belongs after solver-sequence creation and must use a verified COMSOL 6.4 Compile Equations/statistics mechanism.
- Development progresses through M0, M1 and M2 without removing any final acceptance criterion.
- No M1 or M2 implementation should proceed before M0 has demonstrated the underlying execution architecture.
