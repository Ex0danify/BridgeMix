"""Tests for the REST-API gateway (``bridgemix.api.gateway``).

Two concerns are covered:

* **Validation** — unknown / read-only / out-of-range writes raise before any
  device access, so these run without an event loop.
* **Thread marshalling** — the core contract: a call made from a worker thread
  must execute the device access on the GUI thread.  We drive it the way the
  real server does (worker thread + pumped GUI event loop), because the gateway
  uses a *queued* signal connection that only delivers while events are pumped.
"""
from __future__ import annotations

import threading

import pytest
from PyQt6.QtCore import QObject, pyqtSignal

from bridgemix.api.gateway import (
    BridgeGateway,
    ParameterNotFound,
    ParameterOutOfRange,
    ParameterReadOnly,
)
from bridgemix.device.parameters import REGISTRY


class StubBridge(QObject):
    """Minimal stand-in for BridgeCast's gateway-facing surface."""

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
    return BridgeGateway(StubBridge())


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
    gw = BridgeGateway(bridge)
    name = _writable_param()
    target = REGISTRY[name].min_value

    result = _call_from_worker(qapp, lambda: gw.set_parameter(name, target))

    assert result["value"] == target
    assert bridge.state[name] == target
    # The device write must have happened on the GUI (main) thread, not the worker.
    assert bridge.write_thread is threading.main_thread()


def test_status_reflects_device_info(qapp):
    bridge = StubBridge()
    gw = BridgeGateway(bridge)
    bridge.device_info_updated.emit("Roland Bridge Cast", "3.00")

    status = _call_from_worker(qapp, gw.status)

    assert status["connected"] is True
    assert status["model"] == "Roland Bridge Cast"
    assert status["firmware"] == "3.00"


def test_list_parameters_covers_registry(qapp):
    gw = BridgeGateway(StubBridge())
    listed = _call_from_worker(qapp, gw.list_parameters)
    assert len(listed) == len(REGISTRY)
    assert {p["name"] for p in listed} == set(REGISTRY)
