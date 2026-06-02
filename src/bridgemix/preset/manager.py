"""
JSON preset save / load for BridgeCast parameters.

Only writable parameters from REGISTRY are saved/loaded.
Read-only parameters (hardware monitors) are excluded.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from bridgemix.device.parameters import REGISTRY

log = logging.getLogger(__name__)

_PRESET_DIR = Path.home() / ".config" / "bridgemix" / "presets"


def _writable_names() -> list[str]:
    return [name for name, p in REGISTRY.items() if not p.read_only]


def save_preset(path: Path, state: dict[str, int]) -> None:
    """Save writable parameter state to a JSON file.

    Raises OSError if the file cannot be written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {name: state[name] for name in _writable_names() if name in state}
    path.write_text(json.dumps(data, indent=2))
    log.info("Preset saved to %s (%d params)", path, len(data))


def load_preset(path: Path) -> dict[str, int]:
    """Load preset from JSON; returns only valid, in-range parameter values.

    Raises ValueError if the file cannot be read or is not valid JSON.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"Could not read preset {path.name!r}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"Preset {path.name!r} is not a JSON object.")
    result: dict[str, int] = {}
    for name, value in raw.items():
        p = REGISTRY.get(name)
        if p is None or p.read_only:
            continue
        if not isinstance(value, int):
            continue
        if p.min_value <= value <= p.max_value:
            result[name] = value
        else:
            log.warning("Preset value %d out of range for %s — skipped", value, name)
    log.info("Preset loaded from %s (%d params)", path, len(result))
    return result


def preset_dir() -> Path:
    _PRESET_DIR.mkdir(parents=True, exist_ok=True)
    return _PRESET_DIR
