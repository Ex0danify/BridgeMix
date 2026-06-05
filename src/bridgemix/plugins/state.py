"""Persisted enabled/consented flags per plugin, in config_dir()/plugins.json.

A user plugin runs arbitrary code with full privileges, so it stays disabled
until enabled, and the first enable needs consent. Both bits are remembered here
so we ask once. A missing or malformed file reads as "nothing enabled, nothing
consented" and never raises.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from bridgemix.paths import config_dir

log = logging.getLogger(__name__)


def _state_path() -> Path:
    return config_dir() / "plugins.json"


class PluginState:
    """Reads/writes the enabled + consented flags for each plugin id."""

    def __init__(self) -> None:
        self._path = _state_path()
        self._data: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            log.warning("Could not read plugin state %s: %s", self._path, exc)
            return {}
        if not isinstance(raw, dict):
            return {}
        # Keep only well-formed entries.
        return {
            pid: entry for pid, entry in raw.items()
            if isinstance(pid, str) and isinstance(entry, dict)
        }

    # ── Queries ───────────────────────────────────────────────────────────────

    def has_entry(self, plugin_id: str) -> bool:
        """Whether we've stored any explicit state for this plugin yet."""
        return plugin_id in self._data

    def is_enabled(self, plugin_id: str) -> bool:
        return bool(self._data.get(plugin_id, {}).get("enabled", False))

    def is_consented(self, plugin_id: str) -> bool:
        return bool(self._data.get(plugin_id, {}).get("consented", False))

    # ── Mutations (persist immediately) ───────────────────────────────────────

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        self._data.setdefault(plugin_id, {})["enabled"] = enabled
        self._save()

    def set_consented(self, plugin_id: str, consented: bool) -> None:
        self._data.setdefault(plugin_id, {})["consented"] = consented
        self._save()

    def forget(self, plugin_id: str) -> None:
        """Drop all state for a plugin (e.g. after it is uninstalled)."""
        if self._data.pop(plugin_id, None) is not None:
            self._save()

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except OSError as exc:
            log.warning("Could not write plugin state %s: %s", self._path, exc)
