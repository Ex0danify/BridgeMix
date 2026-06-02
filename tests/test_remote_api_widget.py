"""Tests for the Remote API extra widget (``...panels.extras.remote_api``).

Drives the widget's state machine against a fake ApiServer (no real uvicorn) and
with the dependency/install probes monkeypatched, so every UI branch — running,
stopped, failed-start, deps-missing — is covered without a network or a pip call.
Visibility is checked via ``isHidden()`` (the explicit flag), which is reliable
for a widget that is never actually shown.
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QObject, pyqtSignal

from bridgemix import theme
from bridgemix.gui.panels.extras import remote_api
from bridgemix.gui.panels.extras.remote_api import RemoteApiWidget


class FakeApiServer(QObject):
    state_changed = pyqtSignal(bool, str)

    def __init__(self, start_returns: bool = True) -> None:
        super().__init__()
        self._running = False
        self.start_calls: list = []
        self.stop_calls = 0
        self.start_returns = start_returns

    @property
    def is_running(self) -> bool:
        return self._running

    def docs_url(self):
        return "http://127.0.0.1:8765/docs" if self._running else None

    def start(self, settings) -> bool:
        self.start_calls.append(settings)
        self._running = self.start_returns
        msg = "Running" if self._running else "Failed: port in use"
        self.state_changed.emit(self._running, msg)
        return self.start_returns

    def stop(self) -> None:
        self.stop_calls += 1
        self._running = False
        self.state_changed.emit(False, "Stopped.")


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch):
    """Never touch the real ~/.config during widget tests."""
    from bridgemix.api.settings import ApiSettings
    monkeypatch.setattr(remote_api, "load_settings", lambda: ApiSettings())
    monkeypatch.setattr(remote_api, "save_settings", lambda s: None)


def _make(qapp, monkeypatch, *, deps=True, installable=True, server=None):
    monkeypatch.setattr(remote_api, "dependencies_available", lambda: deps)
    monkeypatch.setattr(remote_api, "can_install", lambda: installable)
    return RemoteApiWidget(server or FakeApiServer()), server


# ── Initial states ────────────────────────────────────────────────────────────

def test_stopped_initial_state(qapp, monkeypatch):
    w, _ = _make(qapp, monkeypatch, deps=True)
    assert w._api_state_lbl.text() == "Stopped"
    assert theme.RED in w._api_bubble.styleSheet()
    assert w._api_toggle.isChecked() is False
    assert w._api_toggle.isEnabled() is True
    assert w._api_install_btn.isHidden() is True
    assert w._api_docs_btn.isEnabled() is False
    assert w._api_status.isHidden() is True  # no detail line when cleanly stopped


def test_deps_missing_but_installable(qapp, monkeypatch):
    w, _ = _make(qapp, monkeypatch, deps=False, installable=True)
    assert w._api_toggle.isEnabled() is False
    assert w._api_install_btn.isHidden() is False
    assert "not installed" in w._api_status.text()
    assert w._api_status.isHidden() is False


def test_deps_missing_not_installable(qapp, monkeypatch):
    w, _ = _make(qapp, monkeypatch, deps=False, installable=False)
    assert w._api_install_btn.isHidden() is True
    assert "pip install bridgemix[api]" in w._api_status.text()


# ── Transitions ───────────────────────────────────────────────────────────────

def test_toggle_on_starts_and_shows_running(qapp, monkeypatch):
    server = FakeApiServer(start_returns=True)
    w, _ = _make(qapp, monkeypatch, deps=True, server=server)

    w._api_toggle.setChecked(True)
    w._on_api_enable_toggled(True)
    assert w._api_state_lbl.text() == "Starting…"  # painted before the deferred start
    qapp.processEvents()  # fire the QTimer.singleShot(0, start)

    assert len(server.start_calls) == 1
    assert w._api_state_lbl.text() == "Running"
    assert theme.GREEN in w._api_bubble.styleSheet()
    assert w._api_docs_btn.isEnabled() is True
    assert w._api_port.isEnabled() is False
    assert w._api_toggle.isChecked() is True


def test_toggle_off_stops(qapp, monkeypatch):
    server = FakeApiServer(start_returns=True)
    w, _ = _make(qapp, monkeypatch, deps=True, server=server)
    w._api_toggle.setChecked(True)
    w._on_api_enable_toggled(True)
    qapp.processEvents()

    w._api_toggle.setChecked(False)
    w._on_api_enable_toggled(False)
    assert server.stop_calls == 1
    assert w._api_state_lbl.text() == "Stopped"
    assert w._api_toggle.isChecked() is False


def test_failed_start_surfaces_error(qapp, monkeypatch):
    server = FakeApiServer(start_returns=False)
    w, _ = _make(qapp, monkeypatch, deps=True, server=server)

    w._api_toggle.setChecked(True)
    w._on_api_enable_toggled(True)
    qapp.processEvents()

    assert w._api_state_lbl.text() == "Stopped"
    assert w._api_status.isHidden() is False
    assert "Failed" in w._api_status.text()
    assert w._api_toggle.isChecked() is False  # reverted to reflect the real state


def test_install_finished_success_reenables(qapp, monkeypatch):
    w, _ = _make(qapp, monkeypatch, deps=False, installable=True)
    assert w._api_toggle.isEnabled() is False
    # Simulate deps now present, then the installer reporting success.
    monkeypatch.setattr(remote_api, "dependencies_available", lambda: True)
    w._on_install_finished(True, "Dependencies installed.")
    assert w._api_toggle.isEnabled() is True
    assert w._api_install_btn.isHidden() is True


def test_install_finished_failure_shows_message(qapp, monkeypatch):
    w, _ = _make(qapp, monkeypatch, deps=False, installable=True)
    w._on_install_finished(False, "Installation failed: network error")
    assert "network error" in w._api_status.text()
    assert w._api_status.isHidden() is False


# ── Port debounce ─────────────────────────────────────────────────────────────

def _start(w, qapp):
    w._api_toggle.setChecked(True)
    w._on_api_enable_toggled(True)
    qapp.processEvents()


def test_port_change_does_not_restart_immediately(qapp, monkeypatch):
    server = FakeApiServer(start_returns=True)
    w, _ = _make(qapp, monkeypatch, deps=True, server=server)
    _start(w, qapp)
    server.start_calls.clear()

    w._api_port.setValue(9001)  # fires _on_api_port_changed via valueChanged

    # Only the debounce timer is armed — no churn yet.
    assert w._port_debounce.isActive()
    assert server.stop_calls == 0
    assert server.start_calls == []


def test_port_change_applies_after_debounce(qapp, monkeypatch):
    server = FakeApiServer(start_returns=True)
    w, _ = _make(qapp, monkeypatch, deps=True, server=server)
    _start(w, qapp)
    server.start_calls.clear()

    w._api_port.setValue(9001)
    w._apply_port_change()  # simulate the debounce timer firing
    assert server.stop_calls == 1
    qapp.processEvents()  # deferred restart
    assert len(server.start_calls) == 1
    assert server.start_calls[0].port == 9001


def test_port_change_while_stopped_saves_without_restart(qapp, monkeypatch):
    saved: list = []
    monkeypatch.setattr(remote_api, "save_settings", lambda s: saved.append(s))
    server = FakeApiServer()
    w, _ = _make(qapp, monkeypatch, deps=True, server=server)

    w._api_port.setValue(9100)
    w._apply_port_change()

    assert server.stop_calls == 0
    assert server.start_calls == []
    assert saved and saved[-1].port == 9100
