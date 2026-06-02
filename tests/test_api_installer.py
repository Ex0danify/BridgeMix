"""Tests for the in-app dependency installer (``bridgemix.api.installer``).

The pip call is mocked, and ``_run`` is invoked directly on the test thread
(its ``finished`` signal fires synchronously over a direct connection), so no
real installation or event loop is needed.
"""
from __future__ import annotations

import subprocess
from types import SimpleNamespace

from bridgemix.api import installer as inst
from bridgemix.api.installer import DependencyInstaller


# ── can_install gating ────────────────────────────────────────────────────────

def test_can_install_true_in_owned_env(monkeypatch):
    monkeypatch.setattr(inst, "_in_flatpak", lambda: False)
    monkeypatch.setattr(inst, "_externally_managed", lambda: False)
    assert inst.can_install() is True


def test_can_install_false_in_flatpak(monkeypatch):
    monkeypatch.setattr(inst, "_in_flatpak", lambda: True)
    monkeypatch.setattr(inst, "_externally_managed", lambda: False)
    assert inst.can_install() is False


def test_can_install_false_when_externally_managed(monkeypatch):
    monkeypatch.setattr(inst, "_in_flatpak", lambda: False)
    monkeypatch.setattr(inst, "_externally_managed", lambda: True)
    assert inst.can_install() is False


# ── install result signalling ─────────────────────────────────────────────────

def _capture(installer: DependencyInstaller) -> list[tuple[bool, str]]:
    out: list[tuple[bool, str]] = []
    installer.finished.connect(lambda ok, msg: out.append((ok, msg)))
    return out


def test_run_success_emits_true(qapp, monkeypatch):
    captured_cmd = {}

    def fake_run(cmd, **kwargs):
        captured_cmd["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(inst.subprocess, "run", fake_run)
    installer = DependencyInstaller()
    out = _capture(installer)

    installer._run()

    assert out == [(True, "Dependencies installed.")]
    # Installs into the running interpreter via pip, with the API requirements.
    assert captured_cmd["cmd"][:4] == [inst.sys.executable, "-m", "pip", "install"]
    assert any("fastapi" in part for part in captured_cmd["cmd"])


def test_run_failure_surfaces_pip_error(qapp, monkeypatch):
    def fake_run(cmd, **kwargs):
        return SimpleNamespace(
            returncode=1, stdout="", stderr="ERROR: could not find a version\n"
        )

    monkeypatch.setattr(inst.subprocess, "run", fake_run)
    installer = DependencyInstaller()
    out = _capture(installer)

    installer._run()

    assert len(out) == 1
    ok, msg = out[0]
    assert ok is False
    assert "could not find a version" in msg


def test_run_timeout_is_reported(qapp, monkeypatch):
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 300)

    monkeypatch.setattr(inst.subprocess, "run", fake_run)
    installer = DependencyInstaller()
    out = _capture(installer)

    installer._run()

    assert out[0][0] is False
    assert "timed out" in out[0][1].lower()


def test_run_pip_missing_is_reported(qapp, monkeypatch):
    def fake_run(cmd, **kwargs):
        raise OSError("No such file")

    monkeypatch.setattr(inst.subprocess, "run", fake_run)
    installer = DependencyInstaller()
    out = _capture(installer)

    installer._run()

    assert out[0][0] is False
    assert "pip" in out[0][1].lower()
