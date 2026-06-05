"""Plugin SDK.

A plugin is a folder under data_dir()/plugins/<id>/ with a plugin.toml manifest
and an entry module exposing a Plugin subclass. The host discovers it, checks its
host_api against PLUGIN_API_VERSION, gets the user's consent, then mounts the
widget create_widget() returns into the Plugins panel.

The contract:

  * A plugin MUST subclass `Plugin` and implement `create_widget(ctx) -> QWidget`,
    returning a real QWidget (the host rejects anything else). Keep `__init__`
    cheap and side-effect-free.
  * A plugin MAY implement `shutdown()` to release resources; it must be safe to
    call even if `create_widget` never ran.
  * It may import ONLY from this module; everything it may touch arrives through
    `PluginContext`. The rest of bridgemix is not a stable interface.
  * `create_widget` is called once, on the GUI thread, and only after the plugin
    is compatible + consented + enabled + dependency-satisfied + conflict-free.
    The device is reached only via `ctx.device`; state persists only via
    `ctx.settings`. Any exception it raises is isolated, never crashing the app.
  * One plugin contributes one widget/card.

`PluginWidget` is an optional convenience base for the returned widget — handy,
not required. `from bridgemix.plugins import style` gives matching design tokens,
role helpers, and the signature controls (ToggleSwitch, meters, …).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from logging import Logger
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

    from bridgemix.plugins.device import DeviceFacade
    from bridgemix.plugins.settings_store import SettingsStore

# Version of the plugin contract. Bump the minor for additive changes, the major
# for breaking ones; plugins pin the range they support via host_api.
PLUGIN_API_VERSION = "1.0.0"


@dataclass(frozen=True)
class PluginContext:
    """What the host hands a plugin when it loads.

    device       thread-safe device access (read/set params, run GUI work, signals)
    settings     the plugin's private persisted key/value store
    log          logger namespaced to the plugin
    host_version BridgeMix's version string
    plugin_dir   folder the plugin was loaded from, for bundled assets
    """

    device: "DeviceFacade"
    settings: "SettingsStore"
    log: Logger
    host_version: str
    plugin_dir: Path | None = None


class Plugin(ABC):
    """Base class for plugins. Keep __init__ cheap; do the work in create_widget."""

    @abstractmethod
    def create_widget(self, ctx: "PluginContext") -> "QWidget":
        """Build and return the widget for the Plugins panel (once, on the GUI thread)."""

    def shutdown(self) -> None:
        """Stop threads/servers on quit or disable. Optional; safe to call anytime."""


# Re-exported here so plugins import everything from one place. Imported at the
# bottom to avoid a cycle (widget.py type-hints PluginContext under TYPE_CHECKING).
from bridgemix.plugins.device import (  # noqa: E402
    DeviceNotConnected,
    ParameterNotFound,
    ParameterOutOfRange,
    ParameterReadOnly,
)
from bridgemix.plugins.widget import CardWidth, PluginWidget  # noqa: E402

__all__ = [
    "PLUGIN_API_VERSION",
    "CardWidth",
    "DeviceNotConnected",
    "ParameterNotFound",
    "ParameterOutOfRange",
    "ParameterReadOnly",
    "Plugin",
    "PluginContext",
    "PluginWidget",
]
