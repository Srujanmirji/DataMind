from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app import launcher
from app.config import ROOT


def setup_probe(monkeypatch, occupied=True):
    probe = MagicMock()
    probe.__enter__.return_value = probe
    probe.connect_ex.return_value = 0 if occupied else 1
    monkeypatch.setattr(launcher.socket, "socket", lambda: probe)
    return probe


@pytest.mark.parametrize(
    "owner,command", [("999999", f"python {ROOT}/run.py"), ("self", "python /other/app.py")]
)
def test_refuses_unrelated_process(monkeypatch, owner, command):
    setup_probe(monkeypatch)
    my_uid = str(getattr(launcher.os, "getuid", lambda: "1000")())
    outputs = iter(["42", command, my_uid if owner == "self" else owner])
    monkeypatch.setattr(launcher.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=next(outputs)))
    with pytest.raises(SystemExit, match="another application"):
        launcher.listener(8000)


def test_refuses_multiple_listeners(monkeypatch):
    setup_probe(monkeypatch)
    monkeypatch.setattr(launcher.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout="42\n43"))
    with pytest.raises(SystemExit, match="one safe-to-replace"):
        launcher.listener(8000)


def test_recognizes_own_process(monkeypatch):
    setup_probe(monkeypatch)
    my_uid = str(getattr(launcher.os, "getuid", lambda: "1000")())
    outputs = iter(["42", f"python {ROOT}/run.py --demo", my_uid])
    monkeypatch.setattr(launcher.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=next(outputs)))
    assert launcher.listener(8000) == 42


def test_replacement_stops_only_verified_process(monkeypatch):
    probe = setup_probe(monkeypatch)
    probe.connect_ex.return_value = 1
    monkeypatch.setattr(launcher, "listener", lambda port: 42)
    kill = MagicMock()
    monkeypatch.setattr(launcher.os, "kill", kill)
    launcher.stop_previous(8000)
    kill.assert_called_once_with(42, launcher.signal.SIGINT)


def test_replacement_timeout_never_force_kills(monkeypatch):
    setup_probe(monkeypatch)
    monkeypatch.setattr(launcher, "listener", lambda port: 42)
    times = iter([0, 6])
    monkeypatch.setattr(launcher.time, "monotonic", lambda: next(times))
    kill = MagicMock()
    monkeypatch.setattr(launcher.os, "kill", kill)
    with pytest.raises(SystemExit, match="no force-kill"):
        launcher.stop_previous(8000)
    kill.assert_called_once_with(42, launcher.signal.SIGINT)


def test_unused_port(monkeypatch):
    setup_probe(monkeypatch, occupied=False)
    assert launcher.listener(8000) is None
