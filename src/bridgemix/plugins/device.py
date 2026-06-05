"""Thread-safe device access for plugins.

The BridgeCast facade is owned by the GUI thread and must not be touched from
anywhere else, or concurrent writes interleave SysEx frames on the wire. Plugins
often run their own threads, so DeviceFacade marshals every call onto the GUI
thread: it queues a thunk plus a Future, runs the thunk on the GUI thread, and
the caller blocks on the Future. call() exposes that primitive; the typed methods
below are built on it.

Every typed read/write goes through _device_call(), which refuses with
DeviceNotConnected when no device is attached — so the guard is enforced once, for
all plugins, rather than left to each caller. status() is the lone exception: it
reports connectivity and must answer even when nothing is connected.

It does not expose the raw BridgeCast, so internal refactors don't break plugins.
"""
from __future__ import annotations

from concurrent.futures import Future
from typing import Any, Callable

from PyQt6.QtCore import QObject, Qt, pyqtSignal, pyqtSlot

from bridgemix.device.bridge_cast import BridgeCast
from bridgemix.device.parameters import REGISTRY

# Cap how long a worker-thread call will wait for the GUI thread to service it.
# The GUI thread should answer within milliseconds; this only guards against a
# wedged event loop so a stray request can't hang a worker forever.
_CALL_TIMEOUT_S = 5.0


class ParameterNotFound(KeyError):
    """Raised when a parameter name is not in the REGISTRY."""


class ParameterReadOnly(ValueError):
    """Raised when attempting to write a read-only parameter."""


class ParameterOutOfRange(ValueError):
    """Raised when a writing value falls outside the parameter's range."""


class DeviceNotConnected(RuntimeError):
    """Raised when the device state is read or written while nothing is connected."""


class DeviceFacade(QObject):
    """GUI-thread-resident marshaller. Construct it on the GUI thread."""

    # Forwarded device signals — safe for a plugin to connect to from its own
    # thread (Qt delivers across threads via queued connections). These mirror
    # the subset of BridgeCast signals plugins are most likely to need.
    connected = pyqtSignal(bool)                 # device connected / disconnected
    parameter_changed = pyqtSignal(str, int)     # name, value
    device_info_updated = pyqtSignal(str, str)   # model_name, firmware_version

    # Carries (thunk, future); connected to _run with a queued connection, so the
    # slot always executes on this object's (GUI) thread.
    _invoke = pyqtSignal(object)

    def __init__(self, bridge: BridgeCast, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._device_info: tuple[str, str] | None = None
        self._invoke.connect(self._run, Qt.ConnectionType.QueuedConnection)
        bridge.device_info_updated.connect(self._on_device_info)
        # Re-broadcast the bridge's signals under the facade's stable name.
        bridge.connected.connect(self.connected)
        bridge.parameter_changed.connect(self.parameter_changed)
        bridge.device_info_updated.connect(self.device_info_updated)

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

    def call(self, thunk: Callable[[], Any]) -> Any:
        """Run *thunk* on the GUI thread and return its result (blocking).

        The primitive every plugin can rely on: wrap any code that must touch the
        device (or other GUI-thread state) in a callable and pass it here. Raises
        whatever *thunk* raises, or :class:`TimeoutError` if the GUI thread does
        not service the call in time.
        """
        future: Future = Future()
        self._invoke.emit((thunk, future))
        return future.result(timeout=_CALL_TIMEOUT_S)

    def _device_call(self, thunk: Callable[[], Any]) -> Any:
        """Like :meth:`call`, but refuses when no device is connected.

        Every typed read/write goes through here, so the connection guard lives in
        one place and applies to *all* plugins: none can read or write a parameter
        on a device that isn't there. The check runs on the GUI thread, atomically
        with the access, so it can't race a disconnect. Raises
        :class:`DeviceNotConnected`.
        """
        def _guarded() -> Any:
            if not self._bridge.is_connected:
                raise DeviceNotConnected()
            return thunk()
        return self.call(_guarded)

    def _on_device_info(self, model: str, firmware: str) -> None:
        self._device_info = (model, firmware)

    # ── Typed convenience methods (callable from any thread) ──────────────────

    def status(self) -> dict[str, Any]:
        def _read() -> dict[str, Any]:
            info = self._device_info
            return {
                "connected": self._bridge.is_connected,
                "model": info[0] if info else None,
                "firmware": info[1] if info else None,
            }
        return self.call(_read)

    def list_parameters(self) -> list[dict[str, Any]]:
        def _read() -> list[dict[str, Any]]:
            state = self._bridge.state
            return [_describe(name, state.get(name)) for name in REGISTRY]
        return self._device_call(_read)

    def get_parameter(self, name: str) -> dict[str, Any]:
        param = REGISTRY.get(name)
        if param is None:
            raise ParameterNotFound(name)

        def _read() -> dict[str, Any]:
            return _describe(name, self._bridge.state.get(name))
        return self._device_call(_read)

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
        return self._device_call(_write)

    def state(self) -> dict[str, int]:
        return self._device_call(lambda: dict(self._bridge.state))


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
