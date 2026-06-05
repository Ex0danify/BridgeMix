"""Optional-dependency handling for plugins: presence/version checks, cross-plugin
conflict detection, and an in-app pip installer.

All plugins share one interpreter, so there is only ever one installed version of
any distribution. We therefore can't isolate conflicting versions — instead we
detect when two plugins constrain the same distribution incompatibly, and install
the *union* of everyone's requirements in a single pip pass so the resolver picks
one version that satisfies them all (or fails loudly).

Installing into the running interpreter only works when we own it (a venv or user
install); inside a Flatpak sandbox or a PEP-668 externally-managed Python it
won't, so can_install() gates the feature and the card falls back to a hint.
"""
from __future__ import annotations

import importlib
import importlib.metadata
import logging
import os
import re
import subprocess
import sys
import sysconfig
import threading
from dataclasses import dataclass

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version
from PyQt6.QtCore import QObject, pyqtSignal

log = logging.getLogger(__name__)

# Fallback name extraction for requirement strings packaging can't parse.
_REQ_NAME = re.compile(r"^\s*([A-Za-z0-9._-]+)")


def _in_flatpak() -> bool:
    return os.path.exists("/.flatpak-info") or "FLATPAK_ID" in os.environ


def _externally_managed() -> bool:
    """True if this Python is PEP-668 externally managed (pip would refuse)."""
    stdlib = sysconfig.get_path("stdlib")
    return bool(stdlib) and os.path.exists(os.path.join(stdlib, "EXTERNALLY-MANAGED"))


def can_install() -> bool:
    """Whether an in-app ``pip install`` is likely to succeed and persist."""
    return not _in_flatpak() and not _externally_managed()


# ── Requirement satisfaction ────────────────────────────────────────────────────


def _parse(req_str: str) -> Requirement | None:
    try:
        return Requirement(req_str)
    except InvalidRequirement:
        return None


def _applies(req: Requirement) -> bool:
    """Whether an environment marker (if any) selects the current environment."""
    return req.marker is None or req.marker.evaluate()


def _installed_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _is_satisfied(req_str: str) -> bool:
    """Whether *req_str* is met by what's installed — name **and** version."""
    req = _parse(req_str)
    if req is None:
        # Unparseable spec: fall back to a coarse presence-by-name check.
        m = _REQ_NAME.match(req_str)
        return _installed_version(m.group(1) if m else req_str.strip()) is not None
    if not _applies(req):
        return True  # marker excludes this environment → not required here
    version = _installed_version(req.name)
    if version is None:
        return False
    return not req.specifier or req.specifier.contains(version, prereleases=True)


def missing_requirements(requires: list[str] | tuple[str, ...]) -> list[str]:
    """Return the subset of *requires* not satisfied by the current environment."""
    return [r for r in requires if not _is_satisfied(r)]


# ── Cross-plugin conflict detection ─────────────────────────────────────────────


@dataclass(frozen=True)
class DependencyConflict:
    """Two or more plugins constrain *dist* in a way no single version satisfies."""

    dist: str                                   # canonical distribution name
    requirements: tuple[tuple[str, str], ...]   # (plugin_id, requirement_str)


def find_conflicts(requires_by_plugin: dict[str, list[str]]) -> list[DependencyConflict]:
    """Find distributions that two+ plugins constrain incompatibly.

    Groups every plugin's applicable requirements by canonical distribution name;
    a distribution constrained by more than one plugin is a conflict when the
    intersection of their specifiers admits no version.
    """
    by_dist: dict[str, list[tuple[str, Requirement]]] = {}
    for pid, reqs in requires_by_plugin.items():
        for raw in reqs:
            req = _parse(raw)
            if req is None or not _applies(req):
                continue
            by_dist.setdefault(canonicalize_name(req.name), []).append((pid, req))

    conflicts: list[DependencyConflict] = []
    for dist, items in by_dist.items():
        if len({pid for pid, _ in items}) < 2:
            continue  # only one plugin constrains it → no inter-plugin conflict
        combined = SpecifierSet()
        for _, req in items:
            combined &= req.specifier
        if not _satisfiable(combined):
            conflicts.append(
                DependencyConflict(dist, tuple((pid, str(req)) for pid, req in items))
            )
    return conflicts


def _satisfiable(specset: SpecifierSet) -> bool:
    """Offline heuristic: is there any version satisfying the whole specifier set?

    Probes versions at and just around the literals named in the specifiers (plus
    far-low/far-high sentinels). This catches provable contradictions like
    ``>=2,<2`` or ``==1.0,==2.0`` while never false-flagging a set we couldn't
    fully parse — the authoritative check is the resolver at install time.
    """
    if not specset:
        return True

    candidates = {Version("0"), Version("9999")}
    unparsed = False
    for spec in specset:
        text = spec.version[:-2] if spec.version.endswith(".*") else spec.version
        try:
            v = Version(text)
        except InvalidVersion:
            unparsed = True
            continue
        candidates.add(v)
        rel = list(v.release) or [0]
        candidates.add(Version(".".join(map(str, rel[:-1] + [rel[-1] + 1]))))
        if rel[-1] > 0:
            candidates.add(Version(".".join(map(str, rel[:-1] + [rel[-1] - 1]))))

    if any(specset.contains(c, prereleases=True) for c in candidates):
        return True
    # No probe matched: only call it unsatisfiable if every clause was understood.
    return unparsed


# ── Installer ───────────────────────────────────────────────────────────────────


class DependencyInstaller(QObject):
    """Installs a requirement list in one resolved pip pass.

    Pass the union of every active plugin's requirements so pip reconciles them
    together rather than clobbering versions install-by-install. Emits
    ``finished(success, message)``.
    """

    finished = pyqtSignal(bool, str)

    def __init__(self, requirements: list[str], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._requirements = list(requirements)
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def install(self) -> None:
        """Start the install in a background thread (no-op if already running)."""
        if self.is_running or not self._requirements:
            return
        self._thread = threading.Thread(
            target=self._run, name="bridgemix-plugin-pip", daemon=True
        )
        self._thread.start()

    def _run(self) -> None:
        cmd = [sys.executable, "-m", "pip", "install", "--no-input", *self._requirements]
        log.info("Installing plugin dependencies: %s", " ".join(cmd))
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            self.finished.emit(False, "Installation timed out after 5 minutes.")
            return
        except OSError as exc:
            self.finished.emit(False, f"Could not run pip: {exc}")
            return

        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip().splitlines()
            tail = detail[-1] if detail else f"pip exited with code {proc.returncode}"
            log.warning("Plugin dependency install failed: %s", tail)
            self.finished.emit(False, f"Installation failed: {tail}")
            return

        importlib.invalidate_caches()
        log.info("Plugin dependencies installed.")
        self.finished.emit(True, "Dependencies installed.")
