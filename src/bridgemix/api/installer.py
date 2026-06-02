"""
In-app installer for the optional REST API dependencies.

Runs ``<this-python> -m pip install fastapi uvicorn`` in a background thread so
the GUI stays responsive, then invalidates the import caches so a freshly
installed package is importable without restarting the app.

Installing into the running interpreter is only sound when we actually own it
(a venv / conda env / user install). Inside a Flatpak sandbox or a PEP-668
"externally managed" system Python it won't work or won't persist, so
:func:`can_install` gates the feature and the panel falls back to a manual hint.
"""
from __future__ import annotations

import importlib
import logging
import os
import subprocess
import sys
import sysconfig
import threading

from PyQt6.QtCore import QObject, pyqtSignal

from bridgemix.api import API_REQUIREMENTS

log = logging.getLogger(__name__)


def _in_flatpak() -> bool:
    return os.path.exists("/.flatpak-info") or "FLATPAK_ID" in os.environ


def _externally_managed() -> bool:
    """True if this Python is PEP-668 externally managed (pip would refuse)."""
    stdlib = sysconfig.get_path("stdlib")
    return bool(stdlib) and os.path.exists(os.path.join(stdlib, "EXTERNALLY-MANAGED"))


def can_install() -> bool:
    """Whether an in-app ``pip install`` is likely to succeed and persist."""
    if _in_flatpak():
        return False
    if _externally_managed():
        return False
    return True


class DependencyInstaller(QObject):
    """Installs the REST API dependencies; emits ``finished(success, message)``."""

    finished = pyqtSignal(bool, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def install(self) -> None:
        """Start the install in a background thread (no-op if already running)."""
        if self.is_running:
            return
        self._thread = threading.Thread(
            target=self._run, name="bridgemix-pip-install", daemon=True
        )
        self._thread.start()

    def _run(self) -> None:
        cmd = [sys.executable, "-m", "pip", "install", "--no-input", *API_REQUIREMENTS]
        log.info("Installing REST API dependencies: %s", " ".join(cmd))
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            self.finished.emit(False, "Installation timed out after 5 minutes.")
            return
        except OSError as exc:
            self.finished.emit(False, f"Could not run pip: {exc}")
            return

        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip().splitlines()
            tail = detail[-1] if detail else f"pip exited with code {proc.returncode}"
            log.warning("REST API dependency install failed: %s", tail)
            self.finished.emit(False, f"Installation failed: {tail}")
            return

        # Make the just-installed packages importable in this running process.
        importlib.invalidate_caches()
        log.info("REST API dependencies installed.")
        self.finished.emit(True, "Dependencies installed.")
