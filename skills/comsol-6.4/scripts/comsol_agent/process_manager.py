from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


class ProcessContainmentError(RuntimeError):
    pass


@dataclass
class ManagedProcessResult:
    worker_pid: int | None
    exit_code: int | None
    timed_out: bool
    job_object_used: bool
    graceful_cancel_requested: bool
    hard_termination_used: bool
    cleanup_verified: bool
    process_ids_in_job: list[int]
    remaining_process_ids: list[int]
    details: dict


def _job_process_ids(win32job, job) -> list[int]:
    try:
        info = win32job.QueryInformationJobObject(job, win32job.JobObjectBasicProcessIdList)
        if isinstance(info, dict):
            values = info.get("ProcessIdList", [])
        elif isinstance(info, (tuple, list)):
            # PyWin32 releases may expose (assigned_count, list_capacity, pids).
            values = info[-1] if info else []
        else:
            values = []
        return [int(pid) for pid in values]
    except Exception:
        return []


def run_managed_worker(
    command: Sequence[str],
    *,
    cwd: str | Path,
    timeout_seconds: float,
    graceful_cancel_seconds: float = 10,
    cancel_file: str | Path | None = None,
    env: dict[str, str] | None = None,
    send_ctrl_break: bool = True,
) -> ManagedProcessResult:
    if os.name != "nt":
        raise ProcessContainmentError("Production managed COMSOL execution requires Windows Job Objects")
    try:
        import win32api
        import win32con
        import win32event
        import win32job
        import win32process
    except ImportError as exc:
        raise ProcessContainmentError(
            "pywin32 is required. Install the project Windows extra; unsafe subprocess fallback is disabled."
        ) from exc

    job = win32job.CreateJobObject(None, None)
    process_handle = None
    thread_handle = None
    pid = None
    timed_out = False
    graceful_requested = False
    hard_termination = False
    exit_code = None
    details: dict = {}
    pids_in_job: list[int] = []
    try:
        limits = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
        basic = limits["BasicLimitInformation"]
        basic["LimitFlags"] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        limits["BasicLimitInformation"] = basic
        win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, limits)

        startup = win32process.STARTUPINFO()
        flags = win32con.CREATE_SUSPENDED | win32con.CREATE_NEW_PROCESS_GROUP | win32con.CREATE_UNICODE_ENVIRONMENT
        command_line = subprocess.list2cmdline([str(part) for part in command])
        process_handle, thread_handle, pid, _ = win32process.CreateProcess(
            None, command_line, None, None, False, flags, env,
            str(Path(cwd).resolve()), startup
        )

        # The child is suspended until it belongs to the kill-on-close Job Object.
        win32job.AssignProcessToJobObject(job, process_handle)
        win32process.ResumeThread(thread_handle)
        win32api.CloseHandle(thread_handle)
        thread_handle = None

        started = time.monotonic()
        while True:
            wait_result = win32event.WaitForSingleObject(process_handle, 200)
            if wait_result == win32event.WAIT_OBJECT_0:
                exit_code = int(win32process.GetExitCodeProcess(process_handle))
                break
            if time.monotonic() - started >= timeout_seconds:
                timed_out = True
                if cancel_file:
                    path = Path(cancel_file).resolve()
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("cancel_requested\n", encoding="utf-8")
                graceful_requested = True
                grace_end = time.monotonic() + max(0.0, graceful_cancel_seconds)
                if send_ctrl_break:
                    try:
                        win32api.GenerateConsoleCtrlEvent(win32con.CTRL_BREAK_EVENT, int(pid))
                    except Exception as exc:
                        details["ctrl_break_error"] = str(exc)
                while time.monotonic() < grace_end:
                    if win32event.WaitForSingleObject(process_handle, 200) == win32event.WAIT_OBJECT_0:
                        exit_code = int(win32process.GetExitCodeProcess(process_handle))
                        break
                if exit_code is None:
                    hard_termination = True
                    win32job.TerminateJobObject(job, 124)
                    win32event.WaitForSingleObject(process_handle, 15000)
                    try:
                        exit_code = int(win32process.GetExitCodeProcess(process_handle))
                    except Exception:
                        exit_code = None
                break

        details["elapsed_seconds"] = round(time.monotonic() - started, 3)
        details["job_termination_policy"] = "KILL_ON_JOB_CLOSE"
        details["creation_suspended_until_job_assignment"] = True
        details["process_tree_inherits_job"] = True
        pids_in_job = _job_process_ids(win32job, job)
    except Exception:
        try:
            if process_handle is not None:
                win32process.TerminateProcess(process_handle, 125)
        except Exception:
            pass
        raise
    finally:
        if thread_handle is not None:
            try:
                win32api.CloseHandle(thread_handle)
            except Exception:
                pass
        if process_handle is not None:
            try:
                win32api.CloseHandle(process_handle)
            except Exception:
                pass
        # Closing the Job Object triggers KILL_ON_JOB_CLOSE for every remaining
        # owned COMSOL child, not only the Worker root.
        try:
            win32api.CloseHandle(job)
        except Exception:
            pass

    deadline = time.monotonic() + 5.0
    remaining: list[int] = []
    while True:
        try:
            import psutil
            remaining = [child_pid for child_pid in pids_in_job if psutil.pid_exists(child_pid)]
        except Exception:
            remaining = []
        if not remaining or time.monotonic() >= deadline:
            break
        time.sleep(0.1)
    cleanup_verified = not remaining and exit_code is not None
    details["cleanup_check_method"] = "JobObjectBasicProcessIdList + psutil"
    details["job_object_closed"] = True
    details["cleanup_verified_for_all_recorded_job_pids"] = cleanup_verified
    return ManagedProcessResult(
        worker_pid=int(pid) if pid else None,
        exit_code=exit_code,
        timed_out=timed_out,
        job_object_used=True,
        graceful_cancel_requested=graceful_requested,
        hard_termination_used=hard_termination,
        cleanup_verified=cleanup_verified,
        process_ids_in_job=pids_in_job,
        remaining_process_ids=remaining,
        details=details
    )


def verify_job_object_process_tree(output_dir: str | Path, timeout_seconds: float = 3.0) -> dict:
    if os.name != "nt":
        return {"status": "NOT_RUN", "reason": "Windows Job Object test requires Windows"}
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    pid_file = out / "job_tree_pids.json"
    result = run_managed_worker(
        [sys.executable, "-m", "comsol_agent.process_probe", "--pid-file", str(pid_file)],
        cwd=Path.cwd(),
        timeout_seconds=timeout_seconds,
        graceful_cancel_seconds=0.25,
        send_ctrl_break=False
    )
    if not pid_file.is_file():
        return {"status": "FAIL", "reason": "Probe Worker did not write child process identities", "managed_result": asdict(result)}
    import json
    import psutil
    identities = json.loads(pid_file.read_text(encoding="utf-8"))
    time.sleep(0.5)
    remaining = [int(process_id) for process_id in identities.values() if psutil.pid_exists(int(process_id))]
    passed = (
        result.timed_out and result.job_object_used and result.hard_termination_used
        and result.cleanup_verified and not remaining
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "managed_result": asdict(result),
        "process_ids": identities,
        "remaining_process_ids": remaining,
        "all_owned_processes_terminated": not remaining
    }
