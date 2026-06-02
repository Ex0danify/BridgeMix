"""
Game EQ preset *library* — an app-side bank of named EQ curves.

The device only stores 5 Game EQ slots.  The official app additionally keeps a
larger library of curves on the host that can be assigned into any of those 5
slots.  This module is the BridgeMix equivalent: a directory of JSON files, each
holding one named curve (the ``game_eq_*`` parameter values).

Curves are sourced without fabrication — capture them from the device's live EQ
(``capture_live``) or import Roland ``.brdgcEfx`` files via the existing
ProfileWidget loader, then save into the library here.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from bridgemix.device.parameters import REGISTRY

log = logging.getLogger(__name__)

_LIBRARY_DIR = Path.home() / ".config" / "bridgemix" / "game_eq_library"

# Parameters that define a stored Game FX preset.  Profiles/slots hold the whole
# Game FX block, so a library preset restores EQ + Limiter + Virtual Surround
# (not just the EQ curve).  Derived from REGISTRY so it can't drift.
CURVE_PARAM_NAMES: list[str] = (
    ["game_eq_enable"]
    + [n for n in REGISTRY if n.startswith("game_eq_band")]
    + [n for n in REGISTRY if n.startswith("game_limiter")]
    + [n for n in REGISTRY if n.startswith("game_vsurround")]
)

# Surround/back angles are read_only in REGISTRY (they use the high-bit angle
# encoding) — they must be written via BridgeCast.set_vsurround_angle(), not
# set_parameter().  Callers applying a preset should special-case these.
ANGLE_PARAM_NAMES: frozenset[str] = frozenset({
    "game_vsurround_surround_angle",
    "game_vsurround_back_angle",
})


def library_dir() -> Path:
    _LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    return _LIBRARY_DIR


def _slugify(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip().rstrip(".")
    return slug or "preset"


def capture_live(state: dict[str, int]) -> dict[str, int]:
    """Snapshot the current Game EQ curve from a bridge state dict."""
    return {n: state[n] for n in CURVE_PARAM_NAMES if n in state}


def _factory_presets() -> dict[str, dict[str, int]]:
    # Lazy import avoids a circular dependency (factory imports CURVE_PARAM_NAMES).
    from bridgemix.preset.game_eq_factory import FACTORY_PRESETS
    return FACTORY_PRESETS


def list_library() -> list[str]:
    """Return display names of all library curves: factory presets first, then
    user-saved ones (a user file with the same name overrides the factory entry).
    """
    names: list[str] = list(_factory_presets().keys())
    for path in sorted(library_dir().glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            name = raw.get("name") or path.stem
        except (OSError, ValueError):
            log.warning("Skipping unreadable library file %s", path.name)
            continue
        if name not in names:
            names.append(name)
    return names


def save_library_preset(name: str, params: dict[str, int]) -> Path:
    """Write a named curve to the library; returns the file path.

    Only valid in-range curve parameters are stored.
    """
    clean: dict[str, int] = {}
    for k, v in params.items():
        p = REGISTRY.get(k)
        if k in CURVE_PARAM_NAMES and p is not None and isinstance(v, int) \
                and p.min_value <= v <= p.max_value:
            clean[k] = v
    path = library_dir() / f"{_slugify(name)}.json"
    path.write_text(
        json.dumps(
            {"ExportApp": "BridgeMix", "kind": "game_eq_preset",
             "name": name, "parameters": clean},
            indent=2,
        ),
        encoding="utf-8",
    )
    log.info("Game EQ library: saved %r (%d params) to %s", name, len(clean), path.name)
    return path


def load_library_preset(name: str) -> dict[str, int]:
    """Load a curve's parameters by display name. User files take precedence over
    factory presets. Raises ValueError if missing."""
    for path in library_dir().glob("*.json"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (raw.get("name") or path.stem) == name:
            params = raw.get("parameters", {})
            return {k: int(v) for k, v in params.items()
                    if k in CURVE_PARAM_NAMES and isinstance(v, int)}
    factory = _factory_presets()
    if name in factory:
        return dict(factory[name])
    raise ValueError(f"No library preset named {name!r}")


def delete_library_preset(name: str) -> bool:
    """Delete a curve by display name. Returns True if a file was removed."""
    for path in library_dir().glob("*.json"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (raw.get("name") or path.stem) == name:
            path.unlink()
            log.info("Game EQ library: deleted %r", name)
            return True
    return False
