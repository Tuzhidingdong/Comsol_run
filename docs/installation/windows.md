# Windows installation and local acceptance

## Requirements

- Windows 10/11, 64-bit.
- COMSOL Multiphysics 6.4, with a valid local license.
- 64-bit Python 3.10, 3.11, 3.12 or 3.13.
- Internet access for the first Python dependency installation.
- Permission to create a local virtual environment inside this repository.

The tool does not install COMSOL, modify its installation directory, change license configuration, or reset an existing COMSOL login.

## First acceptance

1. Clone the repository.
2. Open the repository root in Windows Explorer.
3. Double-click RUN_ACCEPTANCE.bat.
4. Review the selected Python version.
5. Allow dependency installation and the offline unit tests to finish.
6. Review the doctor output for COMSOL 6.4 executable discovery.
7. Confirm the prompt to launch the COMSOL 6.4 M0 smoke test.

The M0 procedure first tests Windows Job Object containment using a harmless Python process and one child process. If either process survives the kill-on-close test, the script stops before launching COMSOL Server.

The COMSOL smoke test then:

- starts a local COMSOL 6.4 Server through MPh;
- uses a random free local port;
- uses automatic login only when no COMSOL v64 login file exists;
- uses login-never mode when the user's existing login file is present;
- connects through the MPh Client API;
- creates a minimal model;
- saves it to an absolute path;
- removes it from memory;
- reloads it from the saved file;
- records available licensed modules;
- disconnects and shuts down the owned Server.

A first-ever COMSOL Client-Server start may create the file at %USERPROFILE%\.comsol\v64\login.properties. An existing file is hashed before startup and checked afterwards; if it changes, M0 fails.

## Outputs

All generated files are under runs/acceptance/. Do not commit this directory.

The consolidated report is runs/acceptance/acceptance_report.md. The detailed run directory includes:

- environment_report.json
- job_object_probe_result.json
- controller_result.json
- worker_result.json
- execution_report.json
- verification_report.md
- comsol_m0_smoke.mph when the COMSOL connection succeeds.

## Troubleshooting

### COMSOL executable not found

Set COMSOL64_HOME to the installation root that contains Multiphysics/bin/win64/comsolmphserver.exe, then rerun RUN_ACCEPTANCE.bat.

### Python version not supported

Install 64-bit Python 3.10–3.13 and make it available on PATH or through the Python Launcher.

### Server startup/authentication fails

Inspect worker_result.json and the Worker traceback. Do not delete or reset the existing login.properties as a workaround. MPh 1.4 uses COMSOL automatic login on first start; when a v64 login file already exists, this project requests login-never mode.

### Job Object test fails

Do not run the COMSOL step. The managed process containment test must pass first. The framework intentionally does not fall back to an unmanaged subprocess run.

### Unit tests pass but COMSOL is not available

This is not M0 acceptance. Python tests validate the orchestration and validation logic only. A COMSOL 6.4 Server connection and MPH save/reload test are required.
