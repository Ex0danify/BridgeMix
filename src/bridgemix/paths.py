"""XDG base directories.

Paths come from the XDG_* env vars (with the usual defaults) so they also resolve
inside a Flatpak sandbox, where Flatpak points them under ~/.var/app/<id>/.
config_dir() holds small JSON settings; data_dir() holds bulkier app data.
"""
from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "bridgemix"


def _xdg_base(env_var: str, default: Path) -> Path:
    """Return ``$env_var`` if set to an absolute path, else *default*."""
    raw = os.environ.get(env_var, "").strip()
    # XDG says relative paths are ignored.
    if raw and os.path.isabs(raw):
        return Path(raw)
    return default


def config_dir() -> Path:
    """``$XDG_CONFIG_HOME/bridgemix`` (default ``~/.config/bridgemix``)."""
    return _xdg_base("XDG_CONFIG_HOME", Path.home() / ".config") / APP_NAME


def data_dir() -> Path:
    """``$XDG_DATA_HOME/bridgemix`` (default ``~/.local/share/bridgemix``)."""
    return _xdg_base("XDG_DATA_HOME", Path.home() / ".local" / "share") / APP_NAME


def plugins_dir() -> Path:
    """Where user-installed plugins live: ``data_dir()/plugins``."""
    return data_dir() / "plugins"
