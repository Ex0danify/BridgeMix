"""
Chat FX panel — De-esser, Compressor.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from bridgemix.device.bridge_cast import BridgeCast

from bridgemix.gui.widgets.controls import LabeledSlider, ParamToggle


# ── Value-format helpers ───────────────────────────────────────────────────────

_COMP_RATIOS = [
    "1.00:1", "1.12:1", "1.25:1", "1.40:1", "1.60:1", "1.80:1", "2.00:1",
    "2.50:1", "3.20:1", "4.00:1", "5.60:1", "8.00:1", "16.0:1", "Inf:1",
]

_RELEASE_MS = [
    50, 60, 80, 100, 130, 160, 200, 250, 320, 400, 500,
    640, 800, 1000, 1250, 1600, 2000, 2500, 3200, 4000, 5000,
]


def _fmt_attack(v: int) -> str:
    return "0.0ms" if v == 0 else f"{v * 10}ms"


def _fmt_release(v: int) -> str:
    ms = _RELEASE_MS[v] if 0 <= v < len(_RELEASE_MS) else v
    return f"{ms}ms"


def _fmt_threshold(v: int) -> str:
    return f"{v * 3 - 48}dB"


def _fmt_ratio(v: int) -> str:
    return _COMP_RATIOS[v] if 0 <= v < len(_COMP_RATIOS) else str(v)


def _fmt_post_gain(v: int) -> str:
    return f"+{v}dB"


# ── Main panel ────────────────────────────────────────────────────────────────

class ChatFxPanel(QWidget):
    def __init__(self, bridge: "BridgeCast", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        vlay = QVBoxLayout(inner)
        vlay.setContentsMargins(12, 10, 12, 10)
        vlay.setSpacing(10)

        # Wrap the row in a Maximum-height container so it can't absorb the panel's
        # spare vertical space (that goes to the trailing stretch below). Both
        # groups stay Preferred and stretch to the container's content height, so
        # they end up the same, compact height regardless of which has more rows.
        row_container = QWidget()
        row = QHBoxLayout(row_container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addWidget(self._compressor_group(), stretch=1)
        row.addWidget(self._de_esser_group(), stretch=1)
        row_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        vlay.addWidget(row_container)
        vlay.addStretch()

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ── Compressor ────────────────────────────────────────────────────────────

    def _compressor_group(self) -> QGroupBox:
        grp = QGroupBox("COMPRESSOR")
        lay = QVBoxLayout(grp)
        lay.setContentsMargins(10, 6, 10, 10)
        lay.setSpacing(6)

        lay.addWidget(ParamToggle("Enable", "chat_compressor", self._bridge))
        lay.addWidget(LabeledSlider("THRESHOLD", "chat_compressor_threshold", self._bridge, 0, 0x10, _fmt_threshold))
        lay.addWidget(LabeledSlider("RATIO",     "chat_compressor_ratio",     self._bridge, 0, 0x0D, _fmt_ratio))
        lay.addWidget(LabeledSlider("ATTACK",    "chat_compressor_attack",    self._bridge, 0, 0x0A, _fmt_attack))
        lay.addWidget(LabeledSlider("RELEASE",   "chat_compressor_release",   self._bridge, 0, 0x14, _fmt_release))
        lay.addWidget(LabeledSlider("POST GAIN", "chat_compressor_post_gain", self._bridge, 0, 0x1E, _fmt_post_gain))
        lay.addStretch()
        return grp

    # ── De-esser ──────────────────────────────────────────────────────────────

    def _de_esser_group(self) -> QGroupBox:
        grp = QGroupBox("DE-ESSER")
        lay = QVBoxLayout(grp)
        lay.setContentsMargins(10, 6, 10, 10)
        lay.setSpacing(6)

        lay.addWidget(ParamToggle("Enable", "chat_de_esser", self._bridge))
        lay.addWidget(LabeledSlider(
            "DEPTH", "chat_de_esser_depth", self._bridge, 0, 9, lambda v: str(v + 1),
        ))
        lay.addStretch()
        return grp
