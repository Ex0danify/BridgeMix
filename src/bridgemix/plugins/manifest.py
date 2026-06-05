"""Parse and validate plugin.toml, and check host-version compatibility.

The manifest is read-only metadata authored by the plugin developer, parsed with
stdlib tomllib. Parsing is strict: a bad manifest raises
ManifestError, which the manager shows as a failed card instead of crashing.

See doc/PLUGINS.md for the full reference.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

MANIFEST_NAME = "plugin.toml"

# Recognised permission tokens. Unknown ones are kept and shown at consent time,
# not rejected, so a newer plugin still loads on an older host.
KNOWN_PERMISSIONS = frozenset(
    {"device.read", "device.write", "network", "filesystem"}
)


class ManifestError(ValueError):
    """Raised when a ``plugin.toml`` is missing, malformed, or incomplete."""


@dataclass(frozen=True)
class PluginManifest:
    id: str
    name: str
    version: str
    entry_point: str            # "module:ClassName"
    description: str = ""
    maintainer: str = ""
    homepage: str = ""
    license: str = ""
    host_api: str = "*"         # version spec; "*" means "any host"
    requires: tuple[str, ...] = ()       # pip requirement strings
    permissions: tuple[str, ...] = ()    # declared, shown at consent time

    @property
    def entry_module(self) -> str:
        return self.entry_point.split(":", 1)[0]

    @property
    def entry_attr(self) -> str:
        return self.entry_point.split(":", 1)[1]


def _require_str(raw: dict, key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"'{key}' is required and must be a non-empty string")
    return value.strip()


def _opt_str(raw: dict, key: str, default: str = "") -> str:
    value = raw.get(key, default)
    if not isinstance(value, str):
        raise ManifestError(f"'{key}' must be a string")
    return value


def _opt_str_list(raw: dict, key: str) -> tuple[str, ...]:
    value = raw.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ManifestError(f"'{key}' must be a list of strings")
    return tuple(value)


def parse_manifest(raw: dict) -> PluginManifest:
    """Build a :class:`PluginManifest` from a parsed TOML mapping."""
    entry_point = _require_str(raw, "entry_point")
    if ":" not in entry_point:
        raise ManifestError("'entry_point' must be of the form 'module:ClassName'")

    return PluginManifest(
        id=_require_str(raw, "id"),
        name=_require_str(raw, "name"),
        version=_require_str(raw, "version"),
        entry_point=entry_point,
        description=_opt_str(raw, "description"),
        maintainer=_opt_str(raw, "maintainer"),
        homepage=_opt_str(raw, "homepage"),
        license=_opt_str(raw, "license"),
        host_api=_opt_str(raw, "host_api", "*") or "*",
        requires=_opt_str_list(raw, "requires"),
        permissions=_opt_str_list(raw, "permissions"),
    )


def load_manifest(path: Path) -> PluginManifest:
    """Read and parse a ``plugin.toml`` at *path*. Raises :class:`ManifestError`."""
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestError(f"no {MANIFEST_NAME} at {path}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise ManifestError(f"could not read {path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"invalid TOML in {path}: {exc}") from exc
    return parse_manifest(raw)


# ── host_api compatibility ──────────────────────────────────────────────────────

# Clause operators recognised in a host_api spec; anything not starting with one
# of these is a bare version, read as an exact match ("1.0" → "==1.0").
_SPEC_OPERATORS = ("===", "~=", ">=", "<=", "==", "!=", ">", "<")


def is_compatible(host_api: str, host_version: str) -> bool:
    """Does the host_api spec admit host_version?

    Spec is a comma-separated set of PEP 440 clauses like ">=1.0,<2.0"; all must
    hold. "*" or empty matches anything, and a bare "1.0" means "==1.0". An
    unparseable spec or version fails closed, so we never load a plugin we can't
    reason about.
    """
    spec = (host_api or "").strip()
    if spec in ("", "*"):
        return True

    clauses = []
    for clause in (c.strip() for c in spec.split(",")):
        if not clause:
            continue
        clauses.append(clause if clause.startswith(_SPEC_OPERATORS) else f"=={clause}")

    try:
        return SpecifierSet(",".join(clauses)).contains(host_version, prereleases=True)
    except (InvalidSpecifier, InvalidVersion):
        return False
