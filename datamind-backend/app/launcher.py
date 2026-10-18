"""Explicitly replace only this user's verified DataMind listener, never another app."""

import os
import shlex
import signal
import socket
import subprocess
import time

from app.config import ROOT


def listener(port: int) -> int | None:
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) != 0:
            return None
    result = subprocess.run(
        ["lsof", "-t", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"], capture_output=True, text=True, check=False
    )
    pids = set(result.stdout.split())
    if len(pids) != 1:
        raise SystemExit("Port is occupied; could not identify one safe-to-replace process.")
    pid = int(next(iter(pids)))
    command = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True, check=True
    ).stdout.strip()
    owner = subprocess.run(
        ["ps", "-p", str(pid), "-o", "uid="], capture_output=True, text=True, check=True
    ).stdout.strip()
    args = shlex.split(command)
    if owner != str(os.getuid()) or len(args) < 2 or args[1] != str(ROOT / "run.py"):
        raise SystemExit("Port is owned by another application; refusing to stop it. Choose --port instead.")
    return pid


def stop_previous(port: int):
    pid = listener(port)
    if pid is None:
        return
    os.kill(pid, signal.SIGINT)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return
        time.sleep(0.1)
    raise SystemExit("Previous backend did not release the port; no force-kill was attempted.")
