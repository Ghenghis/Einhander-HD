"""Bounded, read-only process checks for isolated captures; no shell or WMI.

Only the helper child imports psutil. Keeping the native queries in that child
lets callers fail closed within a deadline even if an OS query stalls.
"""
import json
from pathlib import Path
import subprocess
import sys
import time


GAME_NAME = "einhander_recompiled.exe"


def _process_names(psutil):
    if sys.platform != "win32":
        return [(process.pid, process.name()) for process in psutil.process_iter()]
    # Toolhelp supplies names for protected system processes whose psutil
    # name() may be empty. Read no memory, command lines or access tokens here.
    import ctypes
    from ctypes import wintypes

    class Entry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("pid", wintypes.DWORD), ("heap", ctypes.c_size_t),
                    ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
                    ("parent", wintypes.DWORD), ("priority", wintypes.LONG),
                    ("flags", wintypes.DWORD), ("name", wintypes.WCHAR * 260)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    for function in (kernel.Process32FirstW, kernel.Process32NextW):
        function.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
        function.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    rows = []
    try:
        entry = Entry()
        entry.dwSize = ctypes.sizeof(entry)
        success = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while success:
            rows.append((entry.pid, entry.name))
            success = kernel.Process32NextW(snapshot, ctypes.byref(entry))
        error = ctypes.get_last_error()
        if error != 18:  # ERROR_NO_MORE_FILES; reject a partial census.
            raise ctypes.WinError(error)
    finally:
        kernel.CloseHandle(snapshot)
    return rows


def _inspect(pid, psutil):
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        raise ValueError("Expected a positive process ID")
    process = psutil.Process(pid)
    created = process.create_time()
    name, executable, arguments = process.name(), process.exe(), process.cmdline()
    if not name or not executable or not arguments or not all(isinstance(x, str) for x in arguments):
        raise RuntimeError("Process identity is incomplete for PID " + str(pid))
    if not process.is_running() or process.create_time() != created:
        raise RuntimeError("Process identity changed for PID " + str(pid))
    return dict(ProcessId=pid, Name=name, ExecutablePath=executable,
                CommandLine=arguments, CreateTime=created)


def _game_processes(psutil, *, seconds=3, clock=time.monotonic):
    deadline = clock() + seconds
    rows = []
    for pid, name in _process_names(psutil):
        if clock() >= deadline:
            raise TimeoutError("Game-process inventory exceeded its deadline")
        try:
            if not name:
                raise RuntimeError("Unknown process name for PID " + str(pid))
            if name.lower() == GAME_NAME:
                rows.append(_inspect(pid, psutil))
        except psutil.NoSuchProcess:
            # An exited process cannot still hold the seed. AccessDenied and
            # other unknown states deliberately propagate instead of guessing.
            continue
    return rows


def _query(operation, pid=None, *, timeout=5):
    arguments = [sys.executable, str(Path(__file__).resolve()), operation]
    if pid is not None:
        arguments.append(str(pid))
    try:
        result = subprocess.run(arguments, check=True, capture_output=True,
                                text=True, timeout=timeout)
        return json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise RuntimeError("Direct process " + operation + " could not be verified") from error


def process_identity(pid):
    row = _query("identity", pid)
    if not isinstance(row, dict) or row.get("ProcessId") != pid:
        raise RuntimeError("Process identity returned the wrong PID")
    return row


def running_games():
    rows = _query("inventory")
    if not isinstance(rows, list):
        raise RuntimeError("Game-process inventory is malformed")
    return rows


def require_seed_closed(rows, source_root):
    root = str(Path(source_root).resolve()).replace("\\", "/").lower()
    for row in rows:
        executable, command = row.get("ExecutablePath"), row.get("CommandLine")
        if not executable or not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
            raise RuntimeError("Game identity is incomplete; private seed use is unknown")
        observed = " ".join([executable, *command]).replace("\\", "/").lower()
        if root in observed:
            raise RuntimeError("The private v4 card source may be in active use")


def verify_private_identity(row, pid, arguments, directory):
    expected = Path(arguments[0]).resolve()
    if row.get("ProcessId") != pid or Path(row.get("ExecutablePath") or "").resolve() != expected:
        raise RuntimeError("Owned process PID or executable does not match")
    if not expected.is_relative_to(Path(directory).resolve()):
        raise RuntimeError("Owned process executable escaped the private directory")
    command = row.get("CommandLine")
    if not isinstance(command, list) or not command or Path(command[0]).resolve() != expected or command[1:] != arguments[1:]:
        raise RuntimeError("Owned process command line does not match")


if __name__ == "__main__":
    import psutil
    if len(sys.argv) == 2 and sys.argv[1] == "inventory":
        print(json.dumps(_game_processes(psutil)))
    elif len(sys.argv) == 3 and sys.argv[1] == "identity":
        print(json.dumps(_inspect(int(sys.argv[2]), psutil)))
    else:
        raise SystemExit("Use inventory or identity PID")
