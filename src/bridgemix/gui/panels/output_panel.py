"""
Output panel — Output delay and Line Out / USB Out / Sub Mix routing.

(Output mutes live on the mixer/home page output strips, not here.)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QVBoxLayout,
    QWidget,
)

from bridgemix.gui.widgets.controls import LabeledSlider, ParamToggle, ScrollGuardComboBox

if TYPE_CHECKING:
    from bridgemix.device.bridge_cast import BridgeCast


def _fmt_delay(v: int) -> str:
    """0–60 steps map linearly to 0–1000 ms."""
    return f"{round(v * 1000 / 60)} ms"


class OutputPanel(QWidget):
    def __init__(self, bridge: "BridgeCast", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)
        layout.addWidget(self._delay_group())
        layout.addWidget(self._routing_group())
        layout.addStretch()
        bridge.parameter_changed.connect(self._on_param)

    # ── Output Delay ──────────────────────────────────────────────────────────

    def _delay_group(self) -> QGroupBox:
        grp = QGroupBox("OUTPUT DELAY")
        lay = QVBoxLayout(grp)
        lay.setContentsMargins(10, 6, 10, 10)
        lay.setSpacing(6)
        lay.addWidget(ParamToggle("Enable", "output_delay_sw", self._bridge))
        lay.addWidget(LabeledSlider(
            "DELAY", "output_delay_amount", self._bridge, 0, 60, _fmt_delay,
        ))
        return grp

    # ── Output Routing ────────────────────────────────────────────────────────

    def _routing_group(self) -> QGroupBox:
        grp = QGroupBox("OUTPUT ROUTING")
        form = QFormLayout(grp)
        b = self._bridge

        self._line_out_combo = ScrollGuardComboBox()
        self._line_out_combo.addItems(["Mic (dry)", "Stream Mix", "Phones Sync"])
        self._line_out_combo.setCurrentIndex(b.get_parameter("line_out_mode"))
        self._line_out_combo.currentIndexChanged.connect(
            lambda i: b.set_parameter("line_out_mode", i)
        )
        form.addRow("Line Out Source:", self._line_out_combo)

        self._usb_out_combo = ScrollGuardComboBox()
        self._usb_out_combo.addItems(["Mic (dry)", "Stream Mix"])
        self._usb_out_combo.setCurrentIndex(b.get_parameter("usb_out_mode"))
        self._usb_out_combo.currentIndexChanged.connect(
            lambda i: b.set_parameter("usb_out_mode", i)
        )
        form.addRow("USB Out Source:", self._usb_out_combo)

        self._sub_mix_combo = ScrollGuardComboBox()
        self._sub_mix_combo.addItems(["Personal Mix", "Mic Dry", "Aux"])
        self._sub_mix_combo.setCurrentIndex(b.get_parameter("sub_mix_mode"))
        self._sub_mix_combo.currentIndexChanged.connect(
            lambda i: b.set_parameter("sub_mix_mode", i)
        )
        form.addRow("Sub Mix Source:", self._sub_mix_combo)

        return grp

    # ── Bridge → UI ───────────────────────────────────────────────────────────
    # The delay toggle/slider self-sync via their bound widgets; only the routing
    # combos need manual reflection of device-pushed changes.

    @staticmethod
    def _set_combo(combo: ScrollGuardComboBox, value: int) -> None:
        """Set a combo index without re-emitting currentIndexChanged (no write-back)."""
        combo.blockSignals(True)
        combo.setCurrentIndex(value)
        combo.blockSignals(False)

    def _on_param(self, name: str, value: int) -> None:
        if name == "line_out_mode":
            self._set_combo(self._line_out_combo, value)
        elif name == "usb_out_mode":
            self._set_combo(self._usb_out_combo, value)
        elif name == "sub_mix_mode":
            self._set_combo(self._sub_mix_combo, value)
