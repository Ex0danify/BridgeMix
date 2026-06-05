"""Per-plugin settings: a private JSON file at config_dir()/plugin-data/<id>.json.

Schema-less key/value storage; plugins own their own shape. Persistence never
raises (a missing or bad file reads as empty). Use it from the GUI thread; from a
worker thread, go through DeviceFacade.call.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from bridgemix.paths import config_dir

log = logging.getLogger(__name__)


def _store_dir() -> Path:
    return config_dir() / "plugin-data"


class SettingsStore:
    """A plugin's private key/value config, persisted as JSON."""

    def __init__(self, plugin_id: str) -> None:
        self._path = _store_dir() / f"{plugin_id}.json"
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            log.warning("Could not read plugin settings %s: %s", self._path, exc)
            return {}
        return raw if isinstance(raw, dict) else {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set *key* and persist immediately."""
        self._data[key] = value
        self._save()

    def update(self, values: dict[str, Any]) -> None:
        """Merge *values* and persist once."""
        self._data.update(values)
        self._save()

    def as_dict(self) -> dict[str, Any]:
        return dict(self._data)

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except OSError as exc:
            log.warning("Could not write plugin settings %s: %s", self._path, exc)
