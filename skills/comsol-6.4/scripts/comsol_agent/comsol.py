from __future__ import annotations

import importlib.metadata
import os
import platform
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io_utils import sha256_file


class ComsolEnvironmentError(RuntimeError):
    pass


def discover_comsol_server(home: str | Path | None = None) -> Path:
    candidates: list[Path] = []
    configured = home or os.environ.get("COMSOL64_HOME") or os.environ.get("COMSOL_HOME")
    if configured:
        root = Path(configured).expanduser()
        candidates.extend([
            root / "Multiphysics" / "bin" / "win64" / "comsolmphserver.exe",
            root / "bin" / "win64" / "comsolmphserver.exe",
            root / "comsolmphserver.exe"
        ])
    on_path = shutil.which("comsolmphserver.exe") or shutil.which("comsolmphserver")
    if on_path:
        candidates.append(Path(on_path))
    for variable in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        base = os.environ.get(variable)
        if base:
            candidates.extend([
                Path(base) / "COMSOL" / "COMSOL64" / "Multiphysics" / "bin" / "win64" / "comsolmphserver.exe",
                Path(base) / "COMSOL" / "COMSOL64" / "bin" / "win64" / "comsolmphserver.exe"
            ])
    seen: set[str] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        key = str(resolved).casefold()
        if key not in seen:
            seen.add(key)
            if resolved.is_file():
                return resolved
    raise ComsolEnvironmentError(
        "COMSOL 6.4 comsolmphserver.exe was not found. Set COMSOL64_HOME to the COMSOL64 "
        "installation directory or add the COMSOL 6.4 win64 bin directory to PATH."
    )


def environment_report(home: str | Path | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "python_executable": os.path.abspath(os.sys.executable),
        "python_version": platform.python_version(),
        "python_bits": struct.calcsize("P") * 8,
        "target_comsol": "6.4",
        "comsol_server_executable": None,
        "mph_version": None,
        "psutil_version": None,
        "pywin32_available": False
    }
    try:
        report["comsol_server_executable"] = str(discover_comsol_server(home))
    except ComsolEnvironmentError as exc:
        report["comsol_discovery_error"] = str(exc)
    for package, key in (("mph", "mph_version"), ("psutil", "psutil_version")):
        try:
            report[key] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            report[key] = None
    try:
        import win32job  # noqa: F401
        report["pywin32_available"] = True
    except ImportError:
        pass
    mph_supported = False
    if report["mph_version"]:
        try:
            mph_supported = tuple(int(x) for x in report["mph_version"].split(".")[:2]) >= (1, 4)
        except ValueError:
            mph_supported = False
    report["mph_supported"] = mph_supported
    report["ready_for_managed_windows_run"] = (
        report["system"] == "Windows"
        and report["python_bits"] == 64
        and report["comsol_server_executable"] is not None
        and mph_supported
        and report["pywin32_available"]
    )
    return report


@dataclass
class ComsolSession:
    cores: int = 1
    version: str = "6.4"
    startup_timeout: int = 120
    home: str | None = None

    def __post_init__(self) -> None:
        self.server = None
        self.client = None
        self.server_pid: int | None = None
        self.server_port: int | None = None
        self.mph_version: str | None = None
        self.login_mode: str | None = None
        self.login_file: Path | None = None
        self.login_file_hash_before: str | None = None

    def start(self) -> "ComsolSession":
        if platform.system() != "Windows":
            raise ComsolEnvironmentError("The managed COMSOL backend currently targets Windows 64-bit only")
        if struct.calcsize("P") * 8 != 64:
            raise ComsolEnvironmentError("A 64-bit Python interpreter is required")
        server_exe = discover_comsol_server(self.home)
        os.environ["PATH"] = str(server_exe.parent) + os.pathsep + os.environ.get("PATH", "")
        try:
            import mph
        except ImportError as exc:
            raise ComsolEnvironmentError("MPh is not installed in this Python environment") from exc
        try:
            self.mph_version = importlib.metadata.version("mph")
            if tuple(int(x) for x in self.mph_version.split(".")[:2]) < (1, 4):
                raise ComsolEnvironmentError("MPh 1.4.0 or later is required for the Windows Server startup path")
            self.login_file = Path.home() / ".comsol" / "v64" / "login.properties"
            if self.login_file.is_file():
                self.login_mode = "never-existing-user-login-preserved"
                self.login_file_hash_before = sha256_file(self.login_file)
                arguments = ["-login", "never"]
            else:
                self.login_mode = "auto-first-run-initialization"
                arguments = []
            # MPh Server defaults to -login auto and parses its standard output
            # for the dynamic port. When a login file already exists, the
            # appended -login never overrides the default without resetting it.
            # Do not pass -silent: graceful Server.stop sends "close" on stdin.
            self.server = mph.Server(
                cores=self.cores,
                version=self.version,
                port=0,
                timeout=self.startup_timeout,
                multi="off",
                arguments=arguments
            )
            process = getattr(self.server, "process", None)
            self.server_pid = getattr(process, "pid", None)
            self.server_port = int(self.server.port)
            if process is not None and process.poll() is not None:
                raise ComsolEnvironmentError(f"COMSOL Server exited during startup with code {process.returncode}")
            self.client = mph.Client(
                cores=self.cores,
                version=self.version,
                port=self.server_port,
                host="localhost"
            )
            actual = str(self.client.version)
            if not actual.startswith("6.4"):
                raise ComsolEnvironmentError(f"Connected to COMSOL {actual}; this project requires 6.4")
            return self
        except Exception:
            self.close()
            raise

    def smoke_test(self, output_dir: str | Path) -> dict[str, Any]:
        if self.client is None:
            raise ComsolEnvironmentError("COMSOL session is not connected")
        out = Path(output_dir).expanduser().resolve()
        out.mkdir(parents=True, exist_ok=True)
        model_path = (out / "comsol_m0_smoke.mph").resolve()
        if model_path.exists():
            raise FileExistsError(f"Refusing to overwrite existing model: {model_path}")
        model = self.client.create("ComsolRunM0Smoke")
        label_before_save = model.name()
        try:
            model.save(str(model_path))
            if not model_path.is_file() or model_path.stat().st_size == 0:
                raise ComsolEnvironmentError("COMSOL reported save completion but no non-empty MPH file exists")
            self.client.remove(model)
            model = self.client.load(str(model_path))
            names = list(self.client.names())
            files = [str(Path(item).resolve()) for item in self.client.files()]
            # COMSOL 6.4 relabels a model loaded from an MPH file using the
            # file stem. Verified against a real 6.4 Server: a model created as
            # "ComsolRunM0Smoke" and saved to "comsol_m0_smoke.mph" is reported
            # by client.names()/Model.name() as "comsol_m0_smoke" after reload.
            # Assert the reloaded identity against the file stem rather than
            # the pre-save label, while still requiring a visible, named model.
            expected_reload_label = model_path.stem
            reloaded_label = model.name()
            if expected_reload_label not in names:
                raise ComsolEnvironmentError(
                    f"Reloaded model label {expected_reload_label!r} (from MPH file stem) "
                    f"is not visible in the COMSOL client model list: {names}"
                )
            if reloaded_label != expected_reload_label:
                raise ComsolEnvironmentError(
                    f"Reloaded model label {reloaded_label!r} does not match the MPH file stem "
                    f"{expected_reload_label!r}"
                )
            if str(model_path) not in files:
                raise ComsolEnvironmentError("Reloaded model path is not present in the COMSOL client file list")
            modules = list(self.client.modules())
            login_exists = bool(self.login_file and self.login_file.is_file())
            login_hash_after = sha256_file(self.login_file) if login_exists else None
            existing_login_preserved = (
                self.login_file_hash_before is None or login_hash_after == self.login_file_hash_before
            )
            if self.login_file_hash_before and not existing_login_preserved:
                raise ComsolEnvironmentError("Existing COMSOL v64 login.properties changed during M0; investigate before proceeding")
            return {
                "comsol_version": str(self.client.version),
                "mph_version": self.mph_version,
                "server_pid": self.server_pid,
                "server_port": self.server_port,
                "client_standalone": bool(self.client.standalone),
                "licensed_modules_reported": modules,
                "login_mode": self.login_mode,
                "login_file": str(self.login_file) if self.login_file else None,
                "login_file_exists_after_start": login_exists,
                "existing_login_file_preserved": existing_login_preserved,
                "model_path": str(model_path),
                "model_size_bytes": model_path.stat().st_size,
                "model_label_before_save": label_before_save,
                "model_label_after_reload": reloaded_label,
                "reloaded_model_names": names,
                "file_paths_absolute": model_path.is_absolute(),
                "save_reload_passed": True
            }
        finally:
            if model is not None:
                try:
                    self.client.remove(model)
                except Exception:
                    pass

    def close(self) -> dict[str, Any]:
        errors: list[str] = []
        if self.client is not None:
            try:
                self.client.disconnect()
            except Exception as exc:
                errors.append(f"client_disconnect: {exc}")
            self.client = None
        if self.server is not None:
            try:
                self.server.stop(timeout=20)
            except Exception as exc:
                errors.append(f"server_stop: {exc}")
            self.server = None
        return {
            "server_pid": self.server_pid,
            "cleanup_errors": errors,
            "cleanup_requested": True,
            "login_mode": self.login_mode,
            "login_file": str(self.login_file) if self.login_file else None
        }

    def __enter__(self) -> "ComsolSession":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
