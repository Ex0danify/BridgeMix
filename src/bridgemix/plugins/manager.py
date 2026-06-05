"""Plugin discovery, validation and lifecycle.

Discovers built-ins (shipped under builtins/) and user plugins (dropped into
data_dir()/plugins/), validates each manifest, checks host_api, gates user
plugins behind enable + one-time consent, then loads the entry class and calls
create_widget. Every step is isolated, so a broken plugin becomes an ERROR record
rather than an exception that reaches the app. No UI lives here; the manager hands
PluginRecords to the Plugins panel.
"""
from __future__ import annotations

import enum
import importlib
import importlib.util
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QWidget

from bridgemix import __version__ as APP_VERSION
from bridgemix.paths import plugins_dir
from bridgemix.plugins import PLUGIN_API_VERSION, Plugin, PluginContext
from bridgemix.plugins.installer import find_conflicts, missing_requirements
from bridgemix.plugins.manifest import (
    MANIFEST_NAME,
    ManifestError,
    PluginManifest,
    is_compatible,
    load_manifest,
)
from bridgemix.plugins.settings_store import SettingsStore
from bridgemix.plugins.state import PluginState

if TYPE_CHECKING:
    from bridgemix.plugins.device import DeviceFacade

log = logging.getLogger(__name__)

_BUILTINS_DIR = Path(__file__).parent / "builtins"
# Namespace user-plugin entry modules under their plugin id so two plugins that
# ship a same-named top-level module don't clobber each other in sys.modules.
_USER_MODULE_PREFIX = "bridgemix_userplugins"


class PluginStatus(enum.Enum):
    LOADED = "loaded"             # running; widget mounted
    DISABLED = "disabled"        # valid + consented, but the user turned it off
    NEEDS_CONSENT = "consent"    # user plugin awaiting first-run consent
    MISSING_DEPS = "missing_deps"  # enabled, but required packages aren't installed
    CONFLICT = "conflict"        # its deps clash with another enabled plugin's
    INCOMPATIBLE = "incompat"    # host_api does not admit this host
    ERROR = "error"              # manifest invalid or load/instantiate failed


@dataclass
class PluginRecord:
    """Mutable per-plugin bookkeeping shared with the Plugins panel."""

    id: str
    path: Path
    source: str                       # "builtin" | "user"
    manifest: PluginManifest | None = None
    status: PluginStatus = PluginStatus.ERROR
    error: str = ""
    instance: Plugin | None = None
    widget: "QWidget | None" = None
    builtin_package: str | None = None
    missing_deps: list[str] = field(default_factory=list)
    conflict: str = ""  # human-readable description when status is CONFLICT

    @property
    def name(self) -> str:
        return self.manifest.name if self.manifest else self.id

    @property
    def is_builtin(self) -> bool:
        return self.source == "builtin"


class PluginManager(QObject):
    """Owns plugin discovery and lifecycle. Construct on the GUI thread."""

    def __init__(self, device: "DeviceFacade", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._device = device
        self._state = PluginState()
        self._records: list[PluginRecord] = []

    @property
    def records(self) -> list[PluginRecord]:
        return list(self._records)

    # ── Discovery ─────────────────────────────────────────────────────────────

    def discover(self) -> None:
        """Rescan both sources, then reconcile so every record lands in a coherent
        status (loading whatever is enabled). Keeps already-loaded plugins and picks
        up new ones; removing a plugin needs a restart for clean teardown."""
        existing = {r.id: r for r in self._records}
        found: list[PluginRecord] = []
        seen: set[str] = set()

        for path, source, pkg in self._candidate_dirs():
            record = self._build_record(path, source, pkg)
            if record.id in seen:
                # Duplicate id — keep the first (built-ins are scanned first).
                log.warning("Duplicate plugin id %r at %s ignored", record.id, path)
                continue
            seen.add(record.id)
            # Preserve a live instance across a rescan.
            prior = existing.get(record.id)
            if prior is not None and prior.status is PluginStatus.LOADED:
                found.append(prior)
            else:
                found.append(record)

        self._records = found
        self.reconcile()

    def _candidate_dirs(self):
        """Yield (dir, source, builtin_package) for every plugin directory."""
        if _BUILTINS_DIR.is_dir():
            for child in sorted(_BUILTINS_DIR.iterdir()):
                if (child / MANIFEST_NAME).is_file():
                    yield child, "builtin", f"bridgemix.plugins.builtins.{child.name}"

        user_root = plugins_dir()
        if user_root.is_dir():
            for child in sorted(user_root.iterdir()):
                if (child / MANIFEST_NAME).is_file():
                    yield child, "user", None

    def _build_record(self, path: Path, source: str, pkg: str | None) -> PluginRecord:
        try:
            manifest = load_manifest(path / MANIFEST_NAME)
        except ManifestError as exc:
            return PluginRecord(
                id=path.name, path=path, source=source,
                status=PluginStatus.ERROR, error=str(exc),
            )

        # Status is left at its default here; discover() reconciles right after,
        # which is the single place statuses are computed.
        return PluginRecord(
            id=manifest.id, path=path, source=source,
            manifest=manifest, builtin_package=pkg,
        )

    def _is_enabled(self, record: PluginRecord) -> bool:
        # Built-ins default ON; user plugins default OFF. An explicit stored flag
        # always wins.
        if self._state.has_entry(record.id):
            return self._state.is_enabled(record.id)
        return record.is_builtin

    # ── Reconciliation ────────────────────────────────────────────────────────

    def reconcile(self) -> None:
        """Recompute every record's status and load/unload to match, as a unit.

        Running over all records together is what makes cross-plugin facts
        coherent: a dependency clash between two enabled plugins flags *both*, and
        disabling one immediately clears the other's conflict.
        """
        active = [r for r in self._records if self._is_active(r)]
        requires_by_plugin = {
            r.id: list(r.manifest.requires) for r in active if r.manifest
        }
        conflicts = self._conflict_messages(requires_by_plugin)

        for record in self._records:
            target = self._target_status(record, conflicts)
            self._apply_target(record, target, conflicts)

    def _is_active(self, record: PluginRecord) -> bool:
        """Whether the user has this plugin turned on (so its deps should exist)."""
        m = record.manifest
        return (
            m is not None
            and is_compatible(m.host_api, PLUGIN_API_VERSION)
            and not (record.source == "user" and not self._state.is_consented(record.id))
            and self._is_enabled(record)
        )

    def _target_status(self, record: PluginRecord, conflicts: dict[str, str]) -> PluginStatus:
        manifest = record.manifest
        if manifest is None:
            return PluginStatus.ERROR
        if not is_compatible(manifest.host_api, PLUGIN_API_VERSION):
            return PluginStatus.INCOMPATIBLE
        if record.source == "user" and not self._state.is_consented(record.id):
            return PluginStatus.NEEDS_CONSENT
        if not self._is_enabled(record):
            return PluginStatus.DISABLED
        if record.id in conflicts:
            return PluginStatus.CONFLICT
        if missing_requirements(manifest.requires):
            return PluginStatus.MISSING_DEPS
        return PluginStatus.LOADED

    def _apply_target(
        self, record: PluginRecord, target: PluginStatus, conflicts: dict[str, str]
    ) -> None:
        if target is PluginStatus.LOADED:
            record.missing_deps = []
            record.conflict = ""
            if record.status is not PluginStatus.LOADED:
                self._instantiate(record)  # sets LOADED, or ERROR on failure
            return

        # Any non-running target: tear down a live instance first, then annotate.
        if record.instance is not None:
            self._shutdown(record)
        record.status = target
        record.conflict = conflicts.get(record.id, "") if target is PluginStatus.CONFLICT else ""
        record.missing_deps = (
            missing_requirements(record.manifest.requires)
            if target is PluginStatus.MISSING_DEPS and record.manifest else []
        )

    def _conflict_messages(self, requires_by_plugin: dict[str, list[str]]) -> dict[str, str]:
        """Map each conflicting plugin id to a one-line description of the clash."""
        names = {r.id: r.name for r in self._records}
        messages: dict[str, str] = {}
        for conflict in find_conflicts(requires_by_plugin):
            for pid, req in conflict.requirements:
                others = ", ".join(
                    f"{names.get(opid, opid)} wants {oreq}"
                    for opid, oreq in conflict.requirements
                    if opid != pid
                )
                msg = f"needs {req}, clashes with {others} over {conflict.dist}"
                messages[pid] = (messages.get(pid, "") + "; " + msg).lstrip("; ")
        return messages

    def dependency_install_set(self, record: PluginRecord) -> list[str]:
        """Requirements to install for *record*, unioned with every other active
        plugin's, so one pip pass resolves them together instead of clobbering."""
        seen: set[str] = set()
        out: list[str] = []
        sources = [record] + [
            r for r in self._records if r.id != record.id and self._is_active(r)
        ]
        for r in sources:
            for req in (r.manifest.requires if r.manifest else ()):
                if req not in seen:
                    seen.add(req)
                    out.append(req)
        return out

    def _instantiate(self, record: PluginRecord) -> None:
        """Import + instantiate + build the widget for *record* (isolated)."""
        manifest = record.manifest
        assert manifest is not None
        try:
            cls = self._import_entry(record)
            if not (isinstance(cls, type) and issubclass(cls, Plugin)):
                raise TypeError(
                    f"{manifest.entry_point} is not a bridgemix.plugins.Plugin subclass"
                )
            instance = cls()
            ctx = PluginContext(
                device=self._device,
                settings=SettingsStore(manifest.id),
                log=logging.getLogger(f"bridgemix.plugin.{manifest.id}"),
                host_version=APP_VERSION,
                plugin_dir=record.path,
            )
            widget = instance.create_widget(ctx)
            if not isinstance(widget, QWidget):
                raise TypeError(
                    "create_widget must return a QWidget, got "
                    f"{type(widget).__name__}"
                )
        except Exception as exc:  # noqa: BLE001 — never let a plugin crash the app
            log.exception("Plugin %r failed to load", record.id)
            record.status = PluginStatus.ERROR
            record.error = str(exc)
            record.instance = None
            record.widget = None
            return

        record.instance = instance
        record.widget = widget
        record.status = PluginStatus.LOADED
        record.error = ""

    def _import_entry(self, record: PluginRecord) -> type:
        manifest = record.manifest
        assert manifest is not None
        if record.is_builtin:
            module = importlib.import_module(
                f"{record.builtin_package}.{manifest.entry_module}"
            )
        else:
            module = self._import_user_module(record, manifest.entry_module)
        return getattr(module, manifest.entry_attr)

    def _import_user_module(self, record: PluginRecord, entry_module: str):
        """Import the entry module from the plugin directory under a per-plugin
        module name (so plugins can't collide). The directory goes on sys.path so
        the module's own sibling imports resolve."""
        qualified = f"{_USER_MODULE_PREFIX}.{record.id}.{entry_module}"
        if qualified in sys.modules:
            return sys.modules[qualified]

        pkg_init = record.path / entry_module / "__init__.py"
        mod_file = record.path / f"{entry_module}.py"
        if pkg_init.is_file():
            location, search = pkg_init, [str(record.path / entry_module)]
        elif mod_file.is_file():
            location, search = mod_file, None
        else:
            raise ModuleNotFoundError(
                f"entry module {entry_module!r} not found in {record.path}"
            )

        if str(record.path) not in sys.path:
            sys.path.insert(0, str(record.path))

        spec = importlib.util.spec_from_file_location(
            qualified, location, submodule_search_locations=search
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"could not load {location}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[qualified] = module
        spec.loader.exec_module(module)
        return module

    # ── User actions ──────────────────────────────────────────────────────────

    def grant_consent(self, record: PluginRecord) -> None:
        """Record one-time consent for a user plugin and enable it."""
        self._state.set_consented(record.id, True)
        self._state.set_enabled(record.id, True)
        self.reconcile()

    def enable(self, record: PluginRecord) -> None:
        """Turn a plugin on — assumes consent already granted."""
        self._state.set_enabled(record.id, True)
        self.reconcile()

    def disable(self, record: PluginRecord) -> None:
        """Turn a plugin off. Re-reconciles so any plugin it conflicted with can
        now load. (Widget removal is the panel's job.)"""
        self._state.set_enabled(record.id, False)
        self.reconcile()

    # ── Teardown ──────────────────────────────────────────────────────────────

    def shutdown_all(self) -> None:
        for record in self._records:
            self._shutdown(record)

    def _shutdown(self, record: PluginRecord) -> None:
        if record.instance is not None:
            try:
                record.instance.shutdown()
            except Exception:  # noqa: BLE001 — best-effort cleanup
                log.exception("Plugin %r raised during shutdown", record.id)
        record.instance = None
        record.widget = None
