"""
Thread-safe gateway between the REST server and the BridgeCast facade.

The uvicorn server runs in its own thread, but the BridgeCast facade (and the
MIDI transport behind it) is owned by the Qt GUI thread and must not be touched
from anywhere else — the heartbeat QTimer sends SysEx from the GUI thread, and a
concurrent write would interleave frames on the wire.

This gateway marshals every call onto the GUI thread: it emits a queued Qt signal
carrying a thunk plus a :class:`concurrent.futures.Future`, the slot runs the
thunk on the GUI thread, and the calling (server) thread blocks on the future
until the result (or exception) is available.
"""
from __future__ import annotations

from concurrent.futures import Future
from typing import Any, Callable

from PyQt6.QtCore import QObject, Qt, pyqtSignal, pyqtSlot

from bridgemix.device.bridge_cast import BridgeCast
from bridgemix.device.parameters import REGISTRY

# Cap how long a server-thread call will wait for the GUI thread to service it.
# The GUI thread should answer within milliseconds; this only guards against a
# wedged event loop so a stray request can't hang a worker forever.
_CALL_TIMEOUT_S = 5.0


class ParameterNotFound(KeyError):
    """Raised when a parameter name is not in the REGISTRY."""


class ParameterReadOnly(ValueError):
    """Raised when attempting to write a read-only parameter."""


class ParameterOutOfRange(ValueError):
    """Raised when a write value falls outside the parameter's range."""


class BridgeGateway(QObject):
    """GUI-thread-resident marshaller. Construct it on the GUI thread."""

    # Carries (thunk, future); connected to _run with a queued connection so the
    # slot always executes on this object's (GUI) thread.
    _invoke = pyqtSignal(object)

    def __init__(self, bridge: BridgeCast, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._device_info: tuple[str, str] | None = None
        self._invoke.connect(self._run, Qt.ConnectionType.QueuedConnection)
        bridge.device_info_updated.connect(self._on_device_info)

    # ── GUI-thread plumbing ───────────────────────────────────────────────────

    @pyqtSlot(object)
    def _run(self, payload: tuple[Callable[[], Any], Future]) -> None:
        thunk, future = payload
        if not future.set_running_or_notify_cancel():
            return
        try:
            future.set_result(thunk())
        except BaseException as exc:  # noqa: BLE001 — propagate to the waiting thread
            future.set_exception(exc)

    def _call(self, thunk: Callable[[], Any]) -> Any:
        """Run *thunk* on the GUI thread and return its result (blocking)."""
        future: Future = Future()
        self._invoke.emit((thunk, future))
        return future.result(timeout=_CALL_TIMEOUT_S)

    def _on_device_info(self, model: str, firmware: str) -> None:
        self._device_info = (model, firmware)

    # ── Public API (called from the server thread) ────────────────────────────

    def status(self) -> dict[str, Any]:
        def _read() -> dict[str, Any]:
            info = self._device_info
            return {
                "connected": self._bridge.is_connected,
                "model": info[0] if info else None,
                "firmware": info[1] if info else None,
            }
        return self._call(_read)

    def list_parameters(self) -> list[dict[str, Any]]:
        def _read() -> list[dict[str, Any]]:
            state = self._bridge.state
            return [_describe(name, state.get(name)) for name in REGISTRY]
        return self._call(_read)

    def get_parameter(self, name: str) -> dict[str, Any]:
        param = REGISTRY.get(name)
        if param is None:
            raise ParameterNotFound(name)

        def _read() -> dict[str, Any]:
            return _describe(name, self._bridge.state.get(name))
        return self._call(_read)

    def set_parameter(self, name: str, value: int) -> dict[str, Any]:
        param = REGISTRY.get(name)
        if param is None:
            raise ParameterNotFound(name)
        if param.read_only:
            raise ParameterReadOnly(name)
        if not (param.min_value <= value <= param.max_value):
            raise ParameterOutOfRange(
                f"{value} out of range [{param.min_value}, {param.max_value}] for {name}"
            )

        def _write() -> dict[str, Any]:
            self._bridge.set_parameter(name, value)
            return _describe(name, self._bridge.state.get(name))
        return self._call(_write)

    def state(self) -> dict[str, int]:
        return self._call(lambda: dict(self._bridge.state))


def _describe(name: str, value: int | None) -> dict[str, Any]:
    p = REGISTRY[name]
    return {
        "name": name,
        "value": value,
        "min": p.min_value,
        "max": p.max_value,
        "default": p.default_value,
        "read_only": p.read_only,
    }
