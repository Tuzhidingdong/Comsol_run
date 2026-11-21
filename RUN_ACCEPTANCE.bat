@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================================
echo COMSOL Agent Skill - Local Acceptance
echo Target: COMSOL Multiphysics 6.4 / Windows 64-bit
echo ============================================================
echo This script creates a project-local Python environment.
echo It will not install COMSOL or change your COMSOL installation.
echo The COMSOL stage starts a local Server and may consume a license.
echo.

set "PY_CMD=python"
%PY_CMD% -c "import sys,struct; sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,14) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
if errorlevel 1 (
  set "PY_CMD="
  py -3.13 -c "import sys,struct; sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,14) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
  if not errorlevel 1 set "PY_CMD=py -3.13"
)
if not defined PY_CMD (
  py -3.12 -c "import sys,struct; sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,14) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
  if not errorlevel 1 set "PY_CMD=py -3.12"
)
if not defined PY_CMD (
  py -3.11 -c "import sys,struct; sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,14) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
  if not errorlevel 1 set "PY_CMD=py -3.11"
)
if not defined PY_CMD (
  py -3.10 -c "import sys,struct; sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,14) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
  if not errorlevel 1 set "PY_CMD=py -3.10"
)
if not defined PY_CMD (
  echo ERROR: 64-bit Python 3.10, 3.11, 3.12 or 3.13 was not found.
  echo Install a supported Python version or add it to PATH.
  pause
  exit /b 2
)

echo [1/5] Python selected:
%PY_CMD% --version
if errorlevel 1 goto :failed

if not exist ".venv\Scripts\python.exe" (
  echo [2/5] Creating project-local virtual environment...
  %PY_CMD% -m venv .venv
  if errorlevel 1 goto :failed
) else (
  echo [2/5] Reusing existing project-local virtual environment...
  ".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,14) else 1)"
  if errorlevel 1 (
    echo ERROR: Existing .venv uses an unsupported Python version.
    echo Remove .venv manually, then rerun this script.
    goto :failed
  )
)

echo [3/5] Installing project and test dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip install -e ".[dev,windows]"
if errorlevel 1 goto :failed

echo [4/5] Running unit tests...
".venv\Scripts\python.exe" -m pytest tests -q
if errorlevel 1 goto :failed

echo Running local environment diagnostics...
".venv\Scripts\python.exe" -m comsol_agent.cli doctor
if errorlevel 1 (
  echo.
  echo Environment diagnostics did not find a complete COMSOL 6.4 runtime.
  echo See README.md and STATUS.md. No COMSOL server was started.
  goto :failed
)

echo.
echo [5/5] The Job Object process-tree test and COMSOL smoke test will now run.
echo COMSOL 6.4 Server startup may use the installed license.
set /p RUN_COMSOL=Start the local COMSOL 6.4 M0 acceptance now? [Y/N]:
if /I not "%RUN_COMSOL%"=="Y" (
  echo M0 not run. Unit tests completed only; full local acceptance remains pending.
  pause
  exit /b 3
)

set COMSOL_AGENT_RUN_JOB_TESTS=1
set COMSOL_AGENT_RUN_M0=1
".venv\Scripts\python.exe" -m comsol_agent.cli m0 --output runs/acceptance --timeout 300
set RESULT=%ERRORLEVEL%

echo.
if "%RESULT%"=="0" (
  echo M0 PASS. Inspect runs\acceptance\acceptance_report.md.
) else (
  echo M0 FAILED or BLOCKED. Inspect runs\acceptance and generated logs.
)
pause
exit /b %RESULT%

:failed
echo.
echo Acceptance did not pass. See the error above and reports under runs/.
pause
exit /b 1
