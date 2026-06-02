"""
Mic SFX panel — Voice FX preset selector, Voice Changer, and Reverb.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from bridgemix.device.bridge_cast import BridgeCast

from bridgemix.gui.widgets.controls import LabeledSlider, ParamToggle
from bridgemix.gui.widgets.profile_widget import ProfileWidget


def _fmt_voice(v: int) -> str:
    """Map raw 0–127 to display −1.00…1.00. Center at raw 64 = 0.00."""
    if v >= 127:
        return "1.00"
    return f"{math.floor((v - 64) * 100 / 64) / 100:.2f}"


class MicSfxPanel(QWidget):
    def __init__(self, bridge: "BridgeCast", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._busy = False

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        vlay = QVBoxLayout(inner)
        vlay.setContentsMargins(12, 10, 12, 10)
        vlay.setSpacing(10)

        # ── Voice FX preset selector (full width, above the two groups) ─────────
        vlay.addWidget(self._preset_group())

        # ── Voice Changer + Reverb side-by-side ──────────────────────────────────
        # Wrap the row in a Maximum-height container so it can't absorb the panel's
        # spare vertical space (that goes to the trailing stretch below). Both
        # groups stay Preferred and stretch to the container's content height, so
        # they end up the same, compact height regardless of which has more rows.
        row_container = QWidget()
        row = QHBoxLayout(row_container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addWidget(self._voice_changer_group(), stretch=1)
        row.addWidget(self._reverb_group(), stretch=1)
        row_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        vlay.addWidget(row_container)

        # Push all content to the top — eliminates blank space at the bottom
        vlay.addStretch()

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ── Voice FX Presets ──────────────────────────────────────────────────────

    def _preset_group(self) -> ProfileWidget:
        self._preset_widget = ProfileWidget(
            "VOICE FX PRESETS",
            num_slots=5,
            load_filter=(
                "Roland / BridgeMix Voice FX (*.brdgcEfx *.brdgcBackup *.json);;"
                "All Files (*)"
            ),
            parent=self,
        )
        self._preset_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )

        # Preset selection is a two-parameter dance:
        #   • SELECT  → write voice_fx_preset (sec=0x7F type=0x7F addr=0x02), the
        #     command the device acts on (matches official-app capture).
        #   • DISPLAY → the device reports the active slot back via mic_fx_preset
        #     (MicFxNo, CHAN/SW/0x32), which also arrives in the sync dump.
        current = self._bridge.get_parameter("mic_fx_preset")
        self._preset_widget.set_current_slot(current)

        self._preset_widget.slot_selected.connect(self._on_preset_row_changed)
        self._preset_widget.params_loaded.connect(self._on_preset_params_loaded)
        self._preset_widget.write_requested.connect(self._on_preset_write)
        self._preset_widget.save_requested.connect(self._on_preset_save)
        self._preset_widget.revert_requested.connect(self._on_preset_revert)

        self._bridge.parameter_changed.connect(self._on_param_changed)
        self._bridge.voice_preset_names_updated.connect(self._on_preset_names_updated)

        return self._preset_widget

    def _on_preset_row_changed(self, row: int) -> None:
        if row < 0 or self._busy:
            return
        # Send the actual SELECT command; the device echoes the new active slot
        # back via mic_fx_preset, which _on_param_changed reflects in the list.
        self._bridge.set_parameter("voice_fx_preset", row)

    def _on_preset_names_updated(self, names: list) -> None:
        self._preset_widget.set_slot_names(names)

    def _on_preset_params_loaded(self, slot: int, params: dict) -> None:
        """Apply voice FX params from a file to the live device state."""
        applied = 0
        for name, value in params.items():
            try:
                self._bridge.set_parameter(name, int(value))
                applied += 1
            except Exception:
                pass
        if applied:
            QMessageBox.information(
                self, "Loaded",
                f"Applied {applied} voice FX parameters.\n\n"
                'Use "Write" to save these settings to the preset slot.',
            )
        else:
            QMessageBox.warning(
                self, "Nothing Loaded",
                "No recognised voice FX parameters found in the file.",
            )

    def _on_preset_write(self, slot: int, name: str) -> None:
        """Save the current live voice state to the selected preset slot."""
        # write_voice_fx_preset_name writes the name then commits the live state
        self._bridge.write_voice_fx_preset_name(slot, name)
        QTimer.singleShot(600, self._bridge.sync_voice_preset_names)

    def _on_preset_save(self, slot: int) -> None:
        """Export the current voice FX state to a file."""
        current_name = self._preset_widget.slot_display_name(slot)
        name, ok = QInputDialog.getText(
            self,
            "Export Voice FX Preset",
            "Preset name to embed in the file (max 18 characters):",
            text=current_name,
        )
        if not ok:
            return
        name = name.strip()[:18]
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Voice FX Preset",
            "",
            "BridgeMix JSON (*.json);;All Files (*)",
        )
        if not path:
            return
        data = self._bridge.export_profile(slot)
        data["profile_name"] = name
        try:
            Path(path).write_text(json.dumps(data, indent=4), encoding="utf-8")
            QMessageBox.information(
                self, "Exported",
                f'Voice FX preset "{name}" saved to {Path(path).name}',
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))

    def _on_preset_revert(self, slot: int) -> None:
        self._bridge.reset_voice_fx_preset_to_defaults(slot)

    # ── Voice Changer ─────────────────────────────────────────────────────────

    def _voice_changer_group(self) -> QGroupBox:
        grp = QGroupBox("VOICE CHANGER")
        lay = QVBoxLayout(grp)
        lay.setContentsMargins(10, 4, 10, 8)
        lay.setSpacing(4)
        b = self._bridge

        lay.addWidget(ParamToggle("Enable", "mic_fx_enable", b))

        mode_row = QHBoxLayout()
        mode_lbl = QLabel("MODE")
        mode_lbl.setStyleSheet(
            "font-size: 10px; color: #7a7a82; letter-spacing: 0.04em;"
            " background-color: transparent;"
        )
        self._rb_avatar = QRadioButton("Avatar")
        self._rb_sing   = QRadioButton("Sing")
        bg = QButtonGroup(self)
        bg.addButton(self._rb_avatar, 0)
        bg.addButton(self._rb_sing,   1)
        bg.idToggled.connect(self._on_voice_mode)
        (self._rb_sing if b.get_parameter("voice_mode") else self._rb_avatar).setChecked(True)
        self._voice_mode_bg = bg
        mode_row.addWidget(mode_lbl)
        mode_row.addSpacing(6)
        mode_row.addWidget(self._rb_avatar)
        mode_row.addWidget(self._rb_sing)
        mode_row.addStretch()
        lay.addLayout(mode_row)

        lay.addWidget(LabeledSlider("PITCH",   "voice_pitch",  b, 0, 127, _fmt_voice))
        lay.addWidget(LabeledSlider("FORMANT", "voice_format", b, 0, 127, _fmt_voice))
        # Trailing stretch so extra vertical height collects at the bottom rather
        # than inflating the Enable toggle row (matches the Reverb group).
        lay.addStretch()

        return grp

    def _on_voice_mode(self, id_: int, checked: bool) -> None:
        if checked:
            self._bridge.set_parameter("voice_mode", id_)

    # ── Reverb ────────────────────────────────────────────────────────────────

    def _reverb_group(self) -> QGroupBox:
        grp = QGroupBox("REVERB")
        lay = QVBoxLayout(grp)
        lay.setContentsMargins(10, 4, 10, 8)
        lay.setSpacing(4)
        b = self._bridge

        lay.addWidget(ParamToggle("Enable", "reverb_switch", b))
        lay.addWidget(LabeledSlider("SIZE",  "reverb_size",  b, 0, 9, lambda v: str(v + 1)))
        lay.addWidget(LabeledSlider("LEVEL", "reverb_level", b, 0, 9, lambda v: str(v + 1)))
        lay.addStretch()
        return grp

    # ── Shared parameter-changed handler ─────────────────────────────────────

    def _on_param_changed(self, name: str, value: int) -> None:
        if name == "voice_mode":
            btn = self._rb_sing if value else self._rb_avatar
            btn.blockSignals(True)
            btn.setChecked(True)
            btn.blockSignals(False)
        elif name == "mic_fx_preset":
            self._preset_widget.set_current_slot(value)
