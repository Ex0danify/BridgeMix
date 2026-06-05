"""Tests for the device facade (``bridgemix.plugins.device.DeviceFacade``)."""

from __future__ import annotations

import threading

import pytest
from PyQt6.QtCore import QObject, pyqtSignal

from bridgemix.plugins.device import (
    DeviceFacade,
    DeviceNotConnected,
    ParameterNotFound,
    ParameterOutOfRange,
    ParameterReadOnly,
)
from bridgemix.device.parameters import REGISTRY


class StubBridge(QObject):
    """Minimal stand-in for BridgeCast's gateway-facing surface."""

    connected = pyqtSignal(bool)
    parameter_changed = pyqtSignal(str, int)
    device_info_updated = pyqtSignal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self._state = {name: p.default_value for name, p in REGISTRY.items()}
        self._is_connected = True
        self.write_thread: threading.Thread | None = None

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def state(self) -> dict[str, int]:
        return dict(self._state)

    def set_parameter(self, name: str, value: int) -> None:
        self.write_thread = threading.current_thread()
        self._state[name] = value


def _writable_param() -> str:
    for name, p in REGISTRY.items():
        if not p.read_only and p.min_value < p.max_value:
            return name
    raise AssertionError("no writable parameter in REGISTRY")


def _readonly_param() -> str | None:
    return next((name for name, p in REGISTRY.items() if p.read_only), None)


@pytest.fixture
def gateway(qapp):
    return DeviceFacade(StubBridge())


# ── Validation (no event loop needed: raises before marshalling) ──────────────

def test_get_unknown_parameter_raises(gateway):
    with pytest.raises(ParameterNotFound):
        gateway.get_parameter("not_a_real_param")


def test_set_unknown_parameter_raises(gateway):
    with pytest.raises(ParameterNotFound):
        gateway.set_parameter("not_a_real_param", 1)


def test_set_out_of_range_raises(gateway):
    name = _writable_param()
    over = REGISTRY[name].max_value + 1
    with pytest.raises(ParameterOutOfRange):
        gateway.set_parameter(name, over)


def test_set_readonly_raises(gateway):
    name = _readonly_param()
    if name is None:
        pytest.skip("no read-only parameter registered")
    with pytest.raises(ParameterReadOnly):
        gateway.set_parameter(name, REGISTRY[name].min_value)


# ── Thread marshalling (worker thread + pumped GUI loop) ──────────────────────

def _call_from_worker(qapp, fn):
    """Run *fn* on a worker thread while pumping the GUI loop; return its result."""
    box: dict = {}

    def worker():
        try:
            box["result"] = fn()
        except BaseException as exc:  # noqa: BLE001 — surface to the test thread
            box["error"] = exc

    t = threading.Thread(target=worker)
    t.start()
    while t.is_alive():
        qapp.processEvents()
    t.join()
    if "error" in box:
        raise box["error"]
    return box["result"]


def test_set_parameter_executes_on_gui_thread(qapp):
    bridge = StubBridge()
    gw = DeviceFacade(bridge)
    name = _writable_param()
    target = REGISTRY[name].min_value

    result = _call_from_worker(qapp, lambda: gw.set_parameter(name, target))

    assert result["value"] == target
    assert bridge.state[name] == target
    # The device write must have happened on the GUI (main) thread, not the worker.
    assert bridge.write_thread is threading.main_thread()


def test_set_while_disconnected_raises(qapp):
    bridge = StubBridge()
    bridge._is_connected = False
    gw = DeviceFacade(bridge)
    name = _writable_param()

    with pytest.raises(DeviceNotConnected):
        _call_from_worker(qapp, lambda: gw.set_parameter(name, REGISTRY[name].min_value))

    # The cached value must be left untouched — nothing was written.
    assert bridge.state[name] == REGISTRY[name].default_value
    assert bridge.write_thread is None


def test_reads_while_disconnected_raise(qapp):
    bridge = StubBridge()
    bridge._is_connected = False
    gw = DeviceFacade(bridge)
    name = _writable_param()

    # Every device-data read needs a connection; only status() is exempt.
    with pytest.raises(DeviceNotConnected):
        _call_from_worker(qapp, gw.list_parameters)
    with pytest.raises(DeviceNotConnected):
        _call_from_worker(qapp, lambda: gw.get_parameter(name))
    with pytest.raises(DeviceNotConnected):
        _call_from_worker(qapp, gw.state)
    # status() still answers and reports the disconnection.
    assert _call_from_worker(qapp, gw.status)["connected"] is False


def test_get_unknown_precedes_disconnect(qapp):
    # An unknown name is a validation error even when disconnected (raised before
    # the marshalled connection check).
    bridge = StubBridge()
    bridge._is_connected = False
    gw = DeviceFacade(bridge)
    with pytest.raises(ParameterNotFound):
        gw.get_parameter("not_a_real_param")


def test_status_reflects_device_info(qapp):
    bridge = StubBridge()
    gw = DeviceFacade(bridge)
    bridge.device_info_updated.emit("Roland Bridge Cast", "3.00")

    status = _call_from_worker(qapp, gw.status)

    assert status["connected"] is True
    assert status["model"] == "Roland Bridge Cast"
    assert status["firmware"] == "3.00"


def test_list_parameters_covers_registry(qapp):
    gw = DeviceFacade(StubBridge())
    listed = _call_from_worker(qapp, gw.list_parameters)
    assert len(listed) == len(REGISTRY)
    assert {p["name"] for p in listed} == set(REGISTRY)
