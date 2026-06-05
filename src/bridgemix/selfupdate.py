"""In-place upgrade of the running checkout to the latest GitHub release tag.

BridgeMix is installed as an editable checkout (``pip install -e``), so the
running code *is* the git working tree (see :mod:`bridgemix.updates`). An
in-place update therefore means moving that checkout onto the latest release tag
and re-syncing dependencies — no binary swap, no reinstall ceremony.

This only applies when the app runs from a git checkout with ``git`` on PATH; a
plain tarball/wheel install has no ``.git``, so :func:`can_self_update` gates the
feature and the UI falls back to the browser download link. The update runs off
the UI thread and reports through ``finished(success, message)``; it never
mutates a dirty tree, and on success the caller prompts the user to restart
(already-imported modules stay in memory).
"""
from __future__ import annotations

import html
import logging
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

log = logging.getLogger(__name__)

_GIT_TIMEOUT = 60     # seconds for a single git call
_PIP_TIMEOUT = 300    # seconds for the dependency re-sync


def repo_root() -> Path | None:
    """The git checkout the app runs from, or ``None`` if it isn't one.

    Walks up from this module (``src/bridgemix/selfupdate.py``) looking for a
    ``.git`` entry. Returns ``None`` when installed from a wheel/tarball, where
    there is nothing to ``git checkout``.
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists():
            return parent
    return None


def can_self_update() -> bool:
    """Whether an in-place git update is possible: a checkout *and* git on PATH."""
    return repo_root() is not None and shutil.which("git") is not None


def _git(root: Path, *args: str, timeout: int = _GIT_TIMEOUT) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _tail(proc: subprocess.CompletedProcess) -> str:
    """Last non-empty line of a subprocess' output, for a one-line error."""
    detail = (proc.stderr or proc.stdout or "").strip().splitlines()
    return detail[-1] if detail else ""


def is_clean(root: Path) -> bool:
    """True if the working tree has no uncommitted changes."""
    proc = _git(root, "status", "--porcelain")
    return proc.returncode == 0 and not proc.stdout.strip()


class SelfUpdater(QObject):
    """Moves the checkout onto a release *tag* and re-syncs deps off the UI thread.

    Emits ``finished(success, message)``. We check out the tag itself (detached
    HEAD at the exact release) rather than fast-forwarding a branch, so the
    result is deterministic regardless of which branch the user happened to be
    on. The working tree is left untouched unless it is clean.
    """

    finished = pyqtSignal(bool, str)

    def __init__(self, tag: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tag = tag
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Begin the update in a background thread (no-op if already running)."""
        if self.is_running:
            return
        self._thread = threading.Thread(
            target=self._run, name="bridgemix-self-update", daemon=True
        )
        self._thread.start()

    def _run(self) -> None:
        root = repo_root()
        if root is None:
            self.finished.emit(False, "Not running from a git checkout.")
            return
        try:
            self._apply(root)
        except subprocess.TimeoutExpired:
            self.finished.emit(False, "Update timed out.")
        except OSError as exc:   # git/pip missing or unspawnable — never crash the UI
            self.finished.emit(False, f"Could not run the updater: {exc}")

    def _apply(self, root: Path) -> None:
        if not is_clean(root):
            self.finished.emit(
                False, "You have local changes here — commit or discard them first."
            )
            return

        fetch = _git(root, "fetch", "--tags", "--force", "origin")
        if fetch.returncode != 0:
            self.finished.emit(False, _tail(fetch) or "Could not reach the update server.")
            return

        # `tags/<tag>` is unambiguous (never resolves to a same-named branch) and
        # detaches HEAD exactly at the release commit.
        checkout = _git(root, "checkout", "--quiet", f"tags/{self._tag}")
        if checkout.returncode != 0:
            self.finished.emit(False, _tail(checkout) or f"Could not switch to {self._tag}.")
            return

        # Re-sync dependencies in case pyproject changed; a no-op when it didn't.
        pip = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-input", "-e", str(root)],
            capture_output=True,
            text=True,
            timeout=_PIP_TIMEOUT,
        )
        if pip.returncode != 0:
            self.finished.emit(
                False, f"Updated the code, but the dependency sync failed: {_tail(pip)}"
            )
            return

        log.info("Self-update to %s complete; restart required.", self._tag)
        self.finished.emit(True, f"Updated to {self._tag}. Restart BridgeMix to finish.")


def escape(message: str) -> str:
    """HTML-escape a result message (git output may contain ``<``/``>``)."""
    return html.escape(message)
