"""
System panel — LED brightness (own group) and Phones gain / Indicator type /
Mute display dropdowns (own group).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from bridgemix.gui.widgets.controls import LabeledSlider, ScrollGuardComboBox

if TYPE_CHECKING:
    from bridgemix.device.bridge_cast import BridgeCast

# Above this LED-brightness level the device needs additional bus power; without
# it the higher levels are ignored.  We can't read the power state, so we just
# mark the ceiling on the slider.
_BRIGHTNESS_POWER_LIMIT = 3


class SystemPanel(QWidget):
    def __init__(self, bridge: "BridgeCast", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)
        layout.addWidget(self._brightness_group())
        layout.addWidget(self._settings_group())
        layout.addWidget(self._reset_group())
        layout.addStretch()
        bridge.parameter_changed.connect(self._on_param)

    # ── LED brightness ────────────────────────────────────────────────────────

    def _brightness_group(self) -> QGroupBox:
        grp = QGroupBox("LED BRIGHTNESS")
        lay = QVBoxLayout(grp)
        lay.setContentsMargins(10, 6, 10, 10)
        lay.setSpacing(6)

        lay.addWidget(LabeledSlider(
            "", "led_brightness", self._bridge, 0, 7, str,
            limit=_BRIGHTNESS_POWER_LIMIT,
            limit_tooltip=(
                "Levels above 3 require additional bus power; without it the "
                "device caps brightness at 3."
            ),
            value_width=18,   # single-digit level — keep it tucked against the slider
        ))

        hint = QLabel(
            "Brightness above Level 3 requires additional power and is "
            "otherwise ignored by the device."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            "font-size: 12px; color: #9a9aa2; background-color: transparent;"
        )
        lay.addWidget(hint)
        return grp

    # ── Dropdown settings ─────────────────────────────────────────────────────

    def _settings_group(self) -> QGroupBox:
        grp = QGroupBox("SYSTEM")
        form = QFormLayout(grp)
        form.setSpacing(8)
        b = self._bridge

        self._phones_combo = ScrollGuardComboBox()
        self._phones_combo.addItems(["Normal", "Boost 1", "Boost 2"])
        self._phones_combo.setCurrentIndex(b.get_parameter("phones_gain"))
        self._phones_combo.currentIndexChanged.connect(
            lambda i: b.set_parameter("phones_gain", i)
        )
        form.addRow("Phones Gain:", self._phones_combo)

        self._indicator_combo = ScrollGuardComboBox()
        self._indicator_combo.addItems(["Level", "Meter"])
        self._indicator_combo.setCurrentIndex(b.get_parameter("indicator_type"))
        self._indicator_combo.currentIndexChanged.connect(
            lambda i: b.set_parameter("indicator_type", i)
        )
        form.addRow("Indicator Type:", self._indicator_combo)

        self._mute_disp_combo = ScrollGuardComboBox()
        self._mute_disp_combo.addItems(["Blink", "OFF"])
        self._mute_disp_combo.setCurrentIndex(b.get_parameter("mute_display"))
        self._mute_disp_combo.currentIndexChanged.connect(
            lambda i: b.set_parameter("mute_display", i)
        )
        form.addRow("Mute Display:", self._mute_disp_combo)

        return grp

    # ── Factory reset ─────────────────────────────────────────────────────────

    def _reset_group(self) -> QGroupBox:
        grp = QGroupBox("FACTORY RESET")
        lay = QVBoxLayout(grp)
        lay.setContentsMargins(10, 6, 10, 10)
        lay.setSpacing(6)

        hint = QLabel(
            "Restores all device settings — volumes, effects, profiles, LED "
            "colours and hot keys — to factory defaults. This cannot be undone."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            "font-size: 12px; color: #9a9aa2; background-color: transparent;"
        )
        lay.addWidget(hint)

        self._reset_btn = QPushButton("Reset to Factory Defaults")
        self._reset_btn.setObjectName("DangerBtn")
        self._reset_btn.clicked.connect(self._on_reset_clicked)
        lay.addWidget(self._reset_btn)
        return grp

    def _on_reset_clicked(self) -> None:
        reply = QMessageBox.warning(
            self,
            "Factory Reset",
            "Reset the device to factory defaults?\n\n"
            "All volumes, effects, profiles, LED colours and hot-key "
            "assignments will be erased. This cannot be undone.",
            QMessageBox.StandardButton.Reset | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Reset:
            self._bridge.factory_reset()

    # ── Bridge → UI ───────────────────────────────────────────────────────────
    # Brightness self-syncs via its bound LabeledSlider; only the combos need
    # manual reflection of device-pushed changes.

    @staticmethod
    def _set_combo(combo: ScrollGuardComboBox, value: int) -> None:
        """Set a combo index without re-emitting currentIndexChanged (no write-back)."""
        combo.blockSignals(True)
        combo.setCurrentIndex(value)
        combo.blockSignals(False)

    def _on_param(self, name: str, value: int) -> None:
        if name == "phones_gain":
            self._set_combo(self._phones_combo, value)
        elif name == "indicator_type":
            self._set_combo(self._indicator_combo, value)
        elif name == "mute_display":
            self._set_combo(self._mute_disp_combo, value)
