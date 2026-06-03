"""Background check for newer GitHub releases.

Dependency-free (``urllib`` only — no git, no ``requests``) so it works on any
machine that can already run BridgeMix. The check runs off the UI thread and
never raises into it: any network or parse failure simply means "no update
info", and the app keeps working offline.

The latest-release tag is fetched from the GitHub API and cached in
``~/.cache/bridgemix/update_check.json``, so the network is hit at most once
per :data:`_CHECK_INTERVAL`.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

log = logging.getLogger(__name__)

_REPO = "Ex0danify/BridgeMix"
_RELEASES_API = f"https://api.github.com/repos/{_REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{_REPO}/releases/latest"

_CACHE_PATH = Path.home() / ".cache" / "bridgemix" / "update_check.json"
_CHECK_INTERVAL = 24 * 60 * 60   # seconds between network checks
_TIMEOUT = 5                     # seconds for the HTTP request

_FALLBACK_VERSION = "0.1.0"


def current_version() -> str:
    """Installed BridgeMix version, or a sane fallback if metadata is missing."""
    try:
        return _pkg_version("bridgemix")
    except PackageNotFoundError:
        return _FALLBACK_VERSION


@dataclass(frozen=True)
class UpdateInfo:
    """Outcome of a version check."""

    current: str
    latest: str
    url: str

    @property
    def available(self) -> bool:
        return _is_newer(self.latest, self.current)


def _parse_version(text: str) -> tuple[int, ...]:
    """Parse a tag like ``v1.2.3`` / ``1.2`` into a comparable int tuple.

    Stops at the first non-numeric component, so a pre-release suffix
    (``1.2.0-rc1``) compares as ``(1, 2, 0)``. Unparseable input → ``()``.
    """
    core = text.strip().lstrip("vV").split("-")[0].split("+")[0]
    parts: list[int] = []
    for piece in core.split("."):
        if not piece.isdigit():
            break
        parts.append(int(piece))
    return tuple(parts)


def _is_newer(latest: str, current: str) -> bool:
    """True if *latest* parses to a strictly higher version than *current*."""
    lt, ct = _parse_version(latest), _parse_version(current)
    if not lt:
        return False
    n = max(len(lt), len(ct))
    lt += (0,) * (n - len(lt))
    ct += (0,) * (n - len(ct))
    return lt > ct


def _read_cache() -> dict | None:
    try:
        raw = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        log.debug("Could not read update cache %s: %s", _CACHE_PATH, exc)
        return None
    return raw if isinstance(raw, dict) else None


def _write_cache(latest: str, url: str) -> None:
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(
            json.dumps({"checked_at": time.time(), "latest": latest, "url": url}),
            encoding="utf-8",
        )
    except OSError as exc:
        log.debug("Could not write update cache %s: %s", _CACHE_PATH, exc)


def _cached_info(cache: dict, current: str) -> UpdateInfo | None:
    latest = cache.get("latest")
    if not isinstance(latest, str):
        return None
    url = cache.get("url")
    return UpdateInfo(current, latest, url if isinstance(url, str) and url else RELEASES_PAGE)


def _fetch_latest() -> tuple[str, str] | None:
    """GET the latest release tag + page URL from GitHub. ``None`` on any failure.

    A repo with no published releases returns 404 (an :class:`HTTPError`), which
    is handled like any other network failure.
    """
    req = urllib.request.Request(
        _RELEASES_API,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "BridgeMix"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, UnicodeDecodeError) as exc:
        log.debug("Update check failed: %s", exc)
        return None
    if not isinstance(data, dict):
        return None
    tag = data.get("tag_name")
    if not isinstance(tag, str) or not tag:
        return None
    url = data.get("html_url")
    return tag, url if isinstance(url, str) and url else RELEASES_PAGE


def check(force: bool = False) -> UpdateInfo | None:
    """Return update info, reusing the day-old cache unless *force*.

    Blocking — call off the UI thread (see :class:`UpdateChecker`). Returns
    ``None`` only when there is no usable cache *and* the network fetch failed.
    """
    current = current_version()
    cache = _read_cache()

    if cache is not None and not force:
        checked_at = cache.get("checked_at")
        if isinstance(checked_at, (int, float)) and (time.time() - checked_at) < _CHECK_INTERVAL:
            cached = _cached_info(cache, current)
            if cached is not None:
                return cached

    fetched = _fetch_latest()
    if fetched is None:
        # Offline / API down: fall back to a stale cache if we have one.
        return _cached_info(cache, current) if cache is not None else None

    latest, url = fetched
    _write_cache(latest, url)
    return UpdateInfo(current, latest, url)


class UpdateChecker(QObject):
    """Runs :func:`check` on a background thread and emits the result.

    Signals
    -------
    checked(object)
        Emitted exactly once with an :class:`UpdateInfo`, or ``None`` if no
        result could be obtained. Because the worker runs on its own thread, Qt
        delivers this via a queued connection on the receiver's thread.
    """

    checked = pyqtSignal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: threading.Thread | None = None

    def start(self, force: bool = False) -> None:
        """Kick off a check; a no-op if one is already running."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run, args=(force,), name="bridgemix-update-check", daemon=True
        )
        self._thread.start()

    def _run(self, force: bool) -> None:
        try:
            info = check(force=force)
        except Exception as exc:   # a checker thread must never take the app down
            log.debug("Update check thread error: %s", exc)
            info = None
        self.checked.emit(info)
