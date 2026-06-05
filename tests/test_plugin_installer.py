"""Tests for the SDK dependency installer (``bridgemix.plugins.installer``).

The pip call is mocked and ``_run`` is invoked directly on the test thread (its
``finished`` signal fires synchronously over a direct connection), so no real
install or event loop is needed.
"""
from __future__ import annotations

import subprocess
from types import SimpleNamespace

from bridgemix.plugins import installer as inst
from bridgemix.plugins.installer import (
    DependencyInstaller,
    find_conflicts,
    missing_requirements,
)

_REQS = ["fastapi>=0.110", "uvicorn>=0.27"]


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


# ── missing_requirements ──────────────────────────────────────────────────────

def test_missing_requirements_detects_absent_and_present():
    # pytest is certainly installed; a nonsense name certainly is not.
    missing = missing_requirements(["pytest>=1", "no-such-dist-xyz>=9"])
    assert missing == ["no-such-dist-xyz>=9"]


def test_missing_requirements_is_version_aware():
    # pytest is installed, but not at version >= 999 — an unsatisfied specifier
    # must count as missing, not "present".
    assert missing_requirements(["pytest>=999"]) == ["pytest>=999"]
    assert missing_requirements(["pytest>=1"]) == []


# ── find_conflicts ────────────────────────────────────────────────────────────

def test_no_conflict_for_compatible_ranges():
    assert find_conflicts({"a": ["dep>=1.0"], "b": ["dep>=1.2"]}) == []


def test_no_conflict_for_different_distributions():
    assert find_conflicts({"a": ["foo>=1"], "b": ["bar>=1"]}) == []


def test_no_conflict_when_only_one_plugin_constrains():
    # A single plugin contradicting itself is its own problem, not an inter-plugin
    # conflict; find_conflicts only reports clashes between different plugins.
    assert find_conflicts({"a": ["dep<2", "dep>=2"]}) == []


def test_conflict_for_contradictory_ranges():
    conflicts = find_conflicts({"a": ["dep<2"], "b": ["dep>=2"]})
    assert len(conflicts) == 1
    assert conflicts[0].dist == "dep"
    assert {pid for pid, _ in conflicts[0].requirements} == {"a", "b"}


def test_conflict_for_different_pins():
    assert len(find_conflicts({"a": ["dep==1.0"], "b": ["dep==2.0"]})) == 1


def test_conflict_groups_by_canonical_name():
    # "Foo.Bar" and "foo-bar" are the same distribution.
    assert len(find_conflicts({"a": ["Foo.Bar<2"], "b": ["foo-bar>=2"]})) == 1


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
    installer = DependencyInstaller(_REQS)
    out = _capture(installer)

    installer._run()

    assert out == [(True, "Dependencies installed.")]
    assert captured_cmd["cmd"][:4] == [inst.sys.executable, "-m", "pip", "install"]
    assert any("fastapi" in part for part in captured_cmd["cmd"])


def test_run_failure_surfaces_pip_error(qapp, monkeypatch):
    def fake_run(cmd, **kwargs):
        return SimpleNamespace(
            returncode=1, stdout="", stderr="ERROR: could not find a version\n"
        )

    monkeypatch.setattr(inst.subprocess, "run", fake_run)
    installer = DependencyInstaller(_REQS)
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
    installer = DependencyInstaller(_REQS)
    out = _capture(installer)

    installer._run()

    assert out[0][0] is False
    assert "timed out" in out[0][1].lower()


def test_run_pip_missing_is_reported(qapp, monkeypatch):
    def fake_run(cmd, **kwargs):
        raise OSError("No such file")

    monkeypatch.setattr(inst.subprocess, "run", fake_run)
    installer = DependencyInstaller(_REQS)
    out = _capture(installer)

    installer._run()

    assert out[0][0] is False
    assert "pip" in out[0][1].lower()
