"""
Lifecycle wrapper for the optional REST API server.

Runs uvicorn in a background thread and exposes start/stop plus a Qt signal so
the System panel can reflect state. ``fastapi``/``uvicorn`` are imported lazily
inside :meth:`ApiServer.start`, so importing this module never pulls them in.
"""
from __future__ import annotations

import logging
import threading
import time

from PyQt6.QtCore import QObject, pyqtSignal

from bridgemix.plugins.builtins.remote_api.settings import ApiSettings
from bridgemix.plugins.device import DeviceFacade

log = logging.getLogger(__name__)

# How long start() waits for uvicorn to bind and come up before deciding whether
# it succeeded or failed.
_STARTUP_TIMEOUT_S = 3.0


def dependencies_available() -> bool:
    """True if the optional REST API dependencies can be imported."""
    import importlib.util
    return (
        importlib.util.find_spec("fastapi") is not None
        and importlib.util.find_spec("uvicorn") is not None
    )


class ApiServer(QObject):
    """Owns the uvicorn thread. Construct and drive it from the GUI thread."""

    # (running, message) — message carries the docs URL on success or the reason
    # on failure/stop.
    state_changed = pyqtSignal(bool, str)

    def __init__(self, gateway: DeviceFacade, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._gateway = gateway
        self._server = None          # uvicorn.Server while running
        self._thread: threading.Thread | None = None
        self._error: BaseException | None = None
        self._host = ""
        self._port = 0

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def docs_url(self) -> str | None:
        if not self.is_running:
            return None
        return f"http://{self._host}:{self._port}/docs"

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self, settings: ApiSettings) -> bool:
        """Start the server. Returns True on success, emitting state_changed."""
        if self.is_running:
            return True
        if not dependencies_available():
            self.state_changed.emit(
                False, "REST API dependencies (fastapi, uvicorn) are not installed."
            )
            return False

        import uvicorn

        from bridgemix.plugins.builtins.remote_api.app import create_app

        self._error = None
        self._host = settings.host
        self._port = settings.port

        app = create_app(self._gateway, settings.host, settings.port)
        config = uvicorn.Config(
            app,
            host=settings.host,
            port=settings.port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        # Without this, uvicorn installs signal handlers, which is only allowed on
        # the main thread.
        self._server.install_signal_handlers = lambda: None

        self._thread = threading.Thread(
            target=self._serve, name="bridgemix-api", daemon=True
        )
        self._thread.start()

        # Wait for uvicorn to either come up (server.started) or fail to bind.
        deadline = time.monotonic() + _STARTUP_TIMEOUT_S
        while time.monotonic() < deadline:
            if self._error is not None:
                self._thread = None
                self._server = None
                msg = f"Failed to start API on {settings.host}:{settings.port} — {self._error}"
                log.warning(msg)
                self.state_changed.emit(False, msg)
                return False
            if getattr(self._server, "started", False):
                url = self.docs_url() or ""
                log.info("REST API started on %s:%d", settings.host, settings.port)
                self.state_changed.emit(True, f"Running — docs at {url}")
                return True
            time.sleep(0.02)

        # Timed out without a clear signal — treat as failure and tear down.
        self.stop()
        msg = f"API did not come up within {_STARTUP_TIMEOUT_S:.0f}s."
        self.state_changed.emit(False, msg)
        return False

    def stop(self) -> None:
        """Stop the server and wait for the thread to exit."""
        if self._server is not None:
            self._server.should_exit = True
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=_STARTUP_TIMEOUT_S)
        self._thread = None
        self._server = None
        self.state_changed.emit(False, "Stopped.")

    # ── Worker thread ─────────────────────────────────────────────────────────

    def _serve(self) -> None:
        try:
            self._server.run()
        except BaseException as exc:  # noqa: BLE001 — surfaced to start() via _error
            self._error = exc
            log.exception("REST API server thread crashed")
