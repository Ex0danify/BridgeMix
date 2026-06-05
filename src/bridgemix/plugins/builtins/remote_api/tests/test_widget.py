"""Tests for the Remote API plugin widget (``...plugins.builtins.remote_api.widget``).

Drives the widget's state machine against a fake ApiServer (no real uvicorn) and a
dict-backed settings store, so every server branch — running, stopped,
failed-start, port debounce — and the persistence wiring are covered without a
network or the filesystem.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

from PyQt6.QtCore import QObject, pyqtSignal

from bridgemix import theme
from bridgemix.plugins.builtins.remote_api.widget import RemoteApiWidget


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


class FakeStore:
    """Dict-backed stand-in for the SDK SettingsStore."""

    def __init__(self, data: dict | None = None) -> None:
        self._d = dict(data or {})

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value

    def update(self, values: dict):
        self._d.update(values)


def _ctx(store):
    # Minimal PluginContext stand-in: PluginWidget only reads device/settings/log.
    return SimpleNamespace(
        device=None, settings=store, log=logging.getLogger("test.remote_api"),
        host_version="1.0.0", plugin_dir=None,
    )


def _make(qapp, *, server=None, store=None):
    server = server or FakeApiServer()
    store = store if store is not None else FakeStore()
    return RemoteApiWidget(_ctx(store), server), server, store


# ── Initial state ─────────────────────────────────────────────────────────────

def test_stopped_initial_state(qapp):
    w, _, _ = _make(qapp)
    assert w._api_state_lbl.text() == "Stopped"
    assert theme.RED in w._api_bubble.styleSheet()
    assert w._api_toggle.isChecked() is False
    assert w._api_toggle.isEnabled() is True
    assert w._api_docs_btn.isEnabled() is False
    assert w._api_status.isHidden() is True  # no detail line when cleanly stopped


def test_initial_port_read_from_store(qapp):
    w, _, _ = _make(qapp, store=FakeStore({"port": 9123}))
    assert w._api_port.value() == 9123


# ── Transitions ───────────────────────────────────────────────────────────────

def test_toggle_on_starts_and_persists(qapp):
    server = FakeApiServer(start_returns=True)
    w, _, store = _make(qapp, server=server)

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
    assert store.get("enabled") is True  # choice persisted to the SDK store


def test_toggle_off_stops_and_persists(qapp):
    server = FakeApiServer(start_returns=True)
    w, _, store = _make(qapp, server=server)
    w._api_toggle.setChecked(True)
    w._on_api_enable_toggled(True)
    qapp.processEvents()

    w._api_toggle.setChecked(False)
    w._on_api_enable_toggled(False)
    assert server.stop_calls == 1
    assert w._api_state_lbl.text() == "Stopped"
    assert w._api_toggle.isChecked() is False
    assert store.get("enabled") is False


def test_failed_start_surfaces_error(qapp):
    server = FakeApiServer(start_returns=False)
    w, _, _ = _make(qapp, server=server)

    w._api_toggle.setChecked(True)
    w._on_api_enable_toggled(True)
    qapp.processEvents()

    assert w._api_state_lbl.text() == "Stopped"
    assert w._api_status.isHidden() is False
    assert "Failed" in w._api_status.text()
    assert w._api_toggle.isChecked() is False  # reverted to reflect the real state


# ── Port debounce ─────────────────────────────────────────────────────────────

def _start(w, qapp):
    w._api_toggle.setChecked(True)
    w._on_api_enable_toggled(True)
    qapp.processEvents()


def test_port_change_does_not_restart_immediately(qapp):
    server = FakeApiServer(start_returns=True)
    w, _, _ = _make(qapp, server=server)
    _start(w, qapp)
    server.start_calls.clear()

    w._api_port.setValue(9001)  # fires _on_api_port_changed via valueChanged

    # Only the debounce timer is armed — no churn yet.
    assert w._port_debounce.isActive()
    assert server.stop_calls == 0
    assert server.start_calls == []


def test_port_change_applies_after_debounce(qapp):
    server = FakeApiServer(start_returns=True)
    w, _, _ = _make(qapp, server=server)
    _start(w, qapp)
    server.start_calls.clear()

    w._api_port.setValue(9001)
    w._apply_port_change()  # simulate the debounce timer firing
    assert server.stop_calls == 1
    qapp.processEvents()  # deferred restart
    assert len(server.start_calls) == 1
    assert server.start_calls[0].port == 9001


def test_port_change_while_stopped_saves_without_restart(qapp):
    server = FakeApiServer()
    w, _, store = _make(qapp, server=server)

    w._api_port.setValue(9100)
    w._apply_port_change()

    assert server.stop_calls == 0
    assert server.start_calls == []
    assert store.get("port") == 9100
