"""Optional convenience base class for plugin widgets.

Subclassing this is **not** required — ``Plugin.create_widget`` may return any
``QWidget``. It just removes boilerplate: it stashes the context (and exposes
``device``/``settings``/``log`` directly) and gives you a ready vertical ``body``
layout to drop controls into.
"""
from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QVBoxLayout, QWidget

if TYPE_CHECKING:
    from bridgemix.plugins import PluginContext


class CardWidth(enum.Enum):
    """How wide the host should make a plugin's card.

    COMPACT keeps a small plugin from stretching across the panel — the card takes
    its natural width and packs side by side with other compact cards. FULL (the
    default) spans the panel width and sits on its own row.
    """

    COMPACT = "compact"
    FULL = "full"


class PluginWidget(QWidget):
    """A QWidget that holds the plugin context and a ready ``body`` layout."""

    def __init__(self, ctx: "PluginContext", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        # Convenience shortcuts onto the context.
        self.device = ctx.device
        self.settings = ctx.settings
        self.log = ctx.log

        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(8)

    def header_widget(self) -> QWidget | None:
        """Optional compact control — typically the plugin's primary on/off toggle —
        for the host to place in the card header rather than the body, keeping the
        card small when there's little else to show. Return the *same* widget each
        call; the host re-homes it across rebuilds. Default: nothing."""
        return None

    def card_width(self) -> CardWidth:
        """Preferred card width (see :class:`CardWidth`). Default: FULL."""
        return CardWidth.FULL
