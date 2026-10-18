"""Explicitly replace only this user's verified DataMind listener, never another app."""

import os
import shlex
import signal
import socket
import subprocess
import time
from pathlib import Path

from app.config import ROOT


def _find_pids_windows(port: int) -> set[str]:
    try:
        proc = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, check=True)
        pids = set()
        for line in proc.stdout.splitlines():
            parts = line.strip().split()
            if (
                len(parts) >= 5
                and parts[0].upper() == "TCP"
                and parts[3].upper() == "LISTENING"
                and parts[1].endswith(f":{port}")
            ):
                pids.add(parts[4])
        return pids
    except (subprocess.SubprocessError, OSError):
        return set()


def _get_process_info_windows(pid: int) -> tuple[str, str]:
    my_uid = str(getattr(os, "getuid", lambda: "1000")())
    try:
        cmd = f"Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}' | Select-Object -ExpandProperty CommandLine"
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip(), my_uid
    except (subprocess.SubprocessError, OSError):
        return "", my_uid


def listener(port: int) -> int | None:
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) != 0:
            return None
    try:
        result = subprocess.run(
            ["lsof", "-t", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"], capture_output=True, text=True, check=False
        )
        pids = set(result.stdout.split())
    except (FileNotFoundError, OSError):
        pids = _find_pids_windows(port)

    if len(pids) != 1:
        raise SystemExit("Port is occupied; could not identify one safe-to-replace process.")
    pid = int(next(iter(pids)))
    try:
        command = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True, check=True
        ).stdout.strip()
        owner = subprocess.run(
            ["ps", "-p", str(pid), "-o", "uid="], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (FileNotFoundError, OSError):
        command, owner = _get_process_info_windows(pid)

    args = shlex.split(command, posix=(os.name != "nt"))
    my_uid = str(getattr(os, "getuid", lambda: "1000")())
    try:
        candidate = Path(args[1])
        target = (ROOT / "run.py").resolve()
        is_same_script = len(args) >= 2 and (
            candidate.resolve() == target
            or (ROOT.parent / candidate).resolve() == target
            or (ROOT / candidate).resolve() == target
        )
    except (OSError, ValueError):
        is_same_script = len(args) >= 2 and (
            args[1] == str(ROOT / "run.py") or (ROOT / "run.py").name in args[1]
        )
    if owner != my_uid or not is_same_script:
        raise SystemExit("Port is owned by another application; refusing to stop it. Choose --port instead.")
    return pid


def stop_previous(port: int):
    pid = listener(port)
    if pid is None:
        return
    try:
        os.kill(pid, signal.SIGINT)
    except OSError:
        if os.name == "nt":
            os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return
        time.sleep(0.1)
    raise SystemExit("Previous backend did not release the port; no force-kill was attempted.")
