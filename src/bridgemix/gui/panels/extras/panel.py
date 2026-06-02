"""
Extras panel — a home for host-side / optional features that are not part of the
Bridge Cast device itself. Each extra is a self-contained widget stacked in a
scrollable column; add a new one by appending a single ``addWidget`` line below.

Today it hosts the optional Remote API (REST). Future extras drop in here without
touching the device-facing panels.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from bridgemix.api.server import ApiServer
from bridgemix.gui.panels.extras.remote_api import RemoteApiWidget

if TYPE_CHECKING:
    from bridgemix.device.bridge_cast import BridgeCast


class ExtrasPanel(QWidget):
    def __init__(
        self,
        bridge: "BridgeCast",
        api_server: ApiServer,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._bridge = bridge  # kept for future device-aware extras

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        layout.addWidget(RemoteApiWidget(api_server))
        # Future extras: layout.addWidget(NextExtra(...))

        layout.addStretch()
        scroll.setWidget(content)
