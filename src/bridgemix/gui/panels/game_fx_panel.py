"""
Game FX panel — Game Limiter, Virtual Surround, Game EQ.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import json
from pathlib import Path

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

from bridgemix.gui.widgets.controls import LabeledSlider, ParamToggle, Slider, ToggleSwitch
from bridgemix.gui.widgets.eq_widget import EqWidget
from bridgemix.gui.widgets.profile_widget import ProfileWidget
from bridgemix.gui.widgets.surround_canvas import SurroundCanvas
from bridgemix.preset import game_eq_library as geq_lib


# ── Value-format helpers ───────────────────────────────────────────────────────

_LIM_RELEASE_MS = [
    10, 12, 15, 20, 25, 30, 40, 50, 60, 80,
    100, 125, 160, 200, 250, 320, 400, 500, 640, 800,
    1000, 1250, 1600, 2500, 5000,
]


def _fmt_lim_level(v: int) -> str:
    return f"{v - 25}dB"


def _fmt_lim_release(v: int) -> str:
    ms = _LIM_RELEASE_MS[v] if 0 <= v < len(_LIM_RELEASE_MS) else v
    return f"{ms}ms"


def _fmt_angle(v: int) -> str:
    return f"{v}°"


# ── Angle slider row (label + slider + value label, writes via bridge method) ──

class _AngleSlider(QWidget):
    """Slider row for a vsurround angle parameter.

    Standard LabeledSlider won't work for surround/back angles because they
    require set_vsurround_angle() instead of set_parameter().  This widget
    handles both cases uniformly via a use_angle_method flag.
    """

    def __init__(
        self,
        label: str,
        param: str,
        bridge: "BridgeCast",
        min_val: int,
        max_val: int,
        use_angle_method: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._param  = param
        self._bridge = bridge
        self._use_angle_method = use_angle_method
        self._block  = False

        from PyQt6.QtWidgets import QLabel as _QLabel

        cap = _QLabel(label)
        cap.setStyleSheet(
            "font-size: 10px; color: #7a7a82; letter-spacing: 0.04em;"
            " background-color: transparent;"
        )

        self._slider = Slider(Qt.Orientation.Horizontal)
        self._slider.setRange(min_val, max_val)
        self._slider.setValue(bridge.get_parameter(param))

        self._val_lbl = _QLabel(_fmt_angle(bridge.get_parameter(param)))
        self._val_lbl.setFixedWidth(38)
        self._val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(self._slider, stretch=1)
        row.addWidget(self._val_lbl)

        vlay = QVBoxLayout(self)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(2)
        vlay.addWidget(cap)
        vlay.addLayout(row)

        self._slider.valueChanged.connect(self._on_moved)
        bridge.parameter_changed.connect(self._on_param)

    def _on_moved(self, v: int) -> None:
        if self._block:
            return
        self._val_lbl.setText(_fmt_angle(v))
        if self._use_angle_method:
            self._bridge.set_vsurround_angle(self._param, v)
        else:
            self._bridge.set_parameter(self._param, v)

    def _on_param(self, name: str, value: int) -> None:
        if name == self._param:
            self._block = True
            self._slider.setValue(value)
            self._val_lbl.setText(_fmt_angle(value))
            self._block = False


# ── Main panel ────────────────────────────────────────────────────────────────

class GameFxPanel(QWidget):
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

        # Game EQ preset slots (full width, top of page)
        vlay.addWidget(self._game_eq_preset_widget())

        # Row 1: Limiter | Virtual Surround
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        row1.addWidget(self._limiter_group(), stretch=4)
        row1.addWidget(self._vsurround_group(), stretch=5)
        vlay.addLayout(row1)

        # Row 2: Game EQ (full width)
        vlay.addWidget(self._game_eq_group())
        vlay.addStretch()

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ── Limiter ───────────────────────────────────────────────────────────────

    def _limiter_group(self) -> QGroupBox:
        grp = QGroupBox("GAME LIMITER")
        lay = QVBoxLayout(grp)
        lay.setContentsMargins(10, 6, 10, 10)
        lay.setSpacing(6)

        lay.addWidget(ParamToggle("Enable", "game_limiter", self._bridge))
        lay.addWidget(LabeledSlider(
            "LEVEL", "game_limiter_level", self._bridge, 0, 25, _fmt_lim_level,
        ))
        lay.addWidget(LabeledSlider(
            "RELEASE", "game_limiter_release", self._bridge, 0, 24, _fmt_lim_release,
        ))
        lay.addStretch()
        return grp

    # ── Virtual Surround ──────────────────────────────────────────────────────

    def _vsurround_group(self) -> QGroupBox:
        b = self._bridge
        grp = QGroupBox("VIRTUAL SURROUND")
        outer = QVBoxLayout(grp)
        outer.setContentsMargins(10, 6, 10, 10)
        outer.setSpacing(6)

        # Enable toggle (game_vsurround is 0=off, 2=on)
        enable_row = QHBoxLayout()
        enable_row.addWidget(QLabel("Enable"))
        enable_row.addStretch()
        self._vs_toggle = ToggleSwitch(bool(b.get_parameter("game_vsurround")))
        self._vs_toggle.toggled.connect(self._on_vs_toggled)
        enable_row.addWidget(self._vs_toggle)
        outer.addLayout(enable_row)

        # Output type selector
        out_cap = QLabel("OUTPUT TYPE")
        out_cap.setStyleSheet(
            "font-size: 10px; color: #7a7a82; letter-spacing: 0.04em;"
            " background-color: transparent;"
        )
        outer.addWidget(out_cap)

        self._rb_phones   = QRadioButton("Phones")
        self._rb_speakers = QRadioButton("Speakers")
        bg = QButtonGroup(self)
        bg.addButton(self._rb_phones,   0)
        bg.addButton(self._rb_speakers, 1)
        self._vs_out_bg = bg
        (self._rb_speakers if b.get_parameter("game_vsurround_output")
         else self._rb_phones).setChecked(True)
        # Connect after initial setChecked so _listen_w exists before signal fires
        bg.idToggled.connect(self._on_vs_output_selected)

        out_row = QHBoxLayout()
        out_row.addWidget(self._rb_phones)
        out_row.addWidget(self._rb_speakers)
        out_row.addStretch()
        outer.addLayout(out_row)

        # Sliders + canvas side-by-side
        body = QHBoxLayout()
        body.setSpacing(10)

        sliders_w = QWidget()
        sliders = QVBoxLayout(sliders_w)
        sliders.setContentsMargins(0, 0, 0, 0)
        sliders.setSpacing(4)

        sliders.addWidget(_AngleSlider(
            "FRONT ANGLE", "game_vsurround_front_angle",
            b, 1, 89, use_angle_method=False,
        ))
        sliders.addWidget(_AngleSlider(
            "SURROUND ANGLE", "game_vsurround_surround_angle",
            b, 91, 179, use_angle_method=True,
        ))
        sliders.addWidget(_AngleSlider(
            "SURROUND BACK ANGLE", "game_vsurround_back_angle",
            b, 91, 179, use_angle_method=True,
        ))

        # Listening angle — shown only in Speakers mode.  Retain its layout space
        # when hidden so the sliders column (and therefore the canvas circle) keeps
        # the same size in both Phones and Speakers modes.
        self._listen_w = _AngleSlider(
            "LISTENING ANGLE", "game_vsurround_listen_angle",
            b, 12, 78, use_angle_method=False,
        )
        _lsp = self._listen_w.sizePolicy()
        _lsp.setRetainSizeWhenHidden(True)
        self._listen_w.setSizePolicy(_lsp)
        sliders.addWidget(self._listen_w)
        sliders.addStretch()

        body.addWidget(sliders_w, stretch=3)

        self._canvas = SurroundCanvas(b)
        body.addWidget(self._canvas, stretch=2)

        outer.addLayout(body)

        self._update_listen_visibility(b.get_parameter("game_vsurround_output"))
        b.parameter_changed.connect(self._on_vs_param)
        return grp

    def _on_vs_toggled(self, checked: bool) -> None:
        self._bridge.set_parameter("game_vsurround", 2 if checked else 0)

    def _on_vs_output_selected(self, id_: int, checked: bool) -> None:
        if checked:
            self._bridge.set_parameter("game_vsurround_output", id_)
            self._update_listen_visibility(id_)

    def _update_listen_visibility(self, output: int) -> None:
        self._listen_w.setVisible(output == 1)

    def _on_vs_param(self, name: str, value: int) -> None:
        if name == "game_vsurround":
            self._vs_toggle.setChecked(bool(value))
        elif name == "game_vsurround_output":
            btn = self._rb_speakers if value else self._rb_phones
            # Block signals so reflecting the device state doesn't echo a write back.
            btn.blockSignals(True)
            btn.setChecked(True)
            btn.blockSignals(False)
            self._update_listen_visibility(value)

    # ── Game EQ ───────────────────────────────────────────────────────────────

    def _game_eq_group(self) -> QGroupBox:
        grp = QGroupBox("GAME MANUAL EQ")
        vlay = QVBoxLayout(grp)
        vlay.setContentsMargins(10, 6, 10, 10)
        vlay.addWidget(EqWidget("game_eq", self._bridge, title="EQ"))
        return grp

    # ── Game EQ preset slots (5 device slots + app-side library) ───────────────

    def _game_eq_preset_widget(self) -> ProfileWidget:
        b = self._bridge
        # Revert resets a slot to its factory default (opcode 0x16); Library opens
        # the app-side curve bank (factory curves + user-saved/imported).
        w = ProfileWidget(
            title="GAME EQ PRESETS",
            num_slots=5,
            load_filter=(
                "Roland Game EQ / BridgeMix (*.brdgcEfx *.brdgcProfile *.json);;"
                "All Files (*)"
            ),
            show_library=True,
            show_revert=True,
        )
        self._geq_preset = w
        w.set_current_slot(b.get_parameter("game_eq_preset"))
        w.slot_selected.connect(self._on_geq_slot_selected)
        w.params_loaded.connect(self._on_geq_params_loaded)
        w.write_requested.connect(self._on_geq_write)
        w.save_requested.connect(self._on_geq_save)
        w.revert_requested.connect(self._on_geq_revert)
        w.library_requested.connect(self._on_geq_library)
        b.game_eq_preset_names_updated.connect(w.set_slot_names)
        b.parameter_changed.connect(self._on_geq_param)
        return w

    def _on_geq_revert(self, slot: int) -> None:
        self._bridge.reset_game_eq_preset_to_defaults(slot)
        QTimer.singleShot(550, self._bridge.refresh_game_fx)

    def _on_geq_param(self, name: str, value: int) -> None:
        if name == "game_eq_preset":
            self._geq_preset.set_current_slot(value)

    def _on_geq_slot_selected(self, slot: int) -> None:
        # SELECT command loads the slot's curve; re-read the live EQ so the
        # graph updates (the device does not push it unsolicited).
        self._bridge.select_game_eq_preset(slot)
        QTimer.singleShot(150, self._bridge.refresh_game_fx)

    def _on_geq_params_loaded(self, slot: int, params: dict) -> None:
        applied = self._apply_curve(params)
        if applied:
            QMessageBox.information(
                self, "EQ Loaded",
                f"Loaded {applied} EQ parameter(s) into the live Game EQ.\n\n"
                'Use "Write" to store them to the selected device slot.',
            )
        else:
            QMessageBox.warning(self, "Nothing Loaded",
                                "No Game EQ parameters found in that file.")

    def _on_geq_write(self, slot: int, name: str) -> None:
        self._bridge.write_game_eq_preset_name(slot, name)

    def _on_geq_save(self, slot: int) -> None:
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save Game EQ Curve", "", "BridgeMix Game EQ (*.json)")
        if not path_str:
            return
        params = geq_lib.capture_live(self._bridge.state)
        Path(path_str).write_text(
            json.dumps({"ExportApp": "BridgeMix", "kind": "game_eq_preset",
                        "name": self._geq_preset.slot_display_name(slot),
                        "parameters": params}, indent=2),
            encoding="utf-8",
        )
        QMessageBox.information(self, "Saved", f"Game EQ curve saved to {Path(path_str).name}")

    def _on_geq_library(self) -> None:
        slot = self._geq_preset.current_slot()
        ADD = "➕  Add current EQ to Library…"
        items = geq_lib.list_library() + [ADD]
        choice, ok = QInputDialog.getItem(
            self, "Game EQ Library",
            f"Assign a library preset to slot {slot + 1} "
            "(applied live and written to the slot):",
            items, 0, False,
        )
        if not ok or not choice:
            return
        if choice == ADD:
            name, ok = QInputDialog.getText(self, "Add to Library", "Curve name:")
            if ok and name.strip():
                geq_lib.save_library_preset(name.strip(), geq_lib.capture_live(self._bridge.state))
            return
        try:
            params = geq_lib.load_library_preset(choice)
        except ValueError as exc:
            QMessageBox.critical(self, "Library Error", str(exc))
            return
        # Apply to the live EQ, then persist it (with its name) to the current
        # slot.  write_game_eq_preset_name sends the name pairs + save command
        # after the live writes above have gone out.
        self._apply_curve(params)
        if slot >= 0:
            self._bridge.write_game_eq_preset_name(slot, choice)

    def _apply_curve(self, params: dict) -> int:
        """Apply a stored Game FX preset (EQ + Limiter + Virtual Surround) to the
        live device.  The read-only surround/back angles use set_vsurround_angle().
        """
        applied = 0
        for name in geq_lib.CURVE_PARAM_NAMES:
            if name not in params:
                continue
            value = int(params[name])
            if name in geq_lib.ANGLE_PARAM_NAMES:
                self._bridge.set_vsurround_angle(name, value)
            else:
                self._bridge.set_parameter(name, value)
            applied += 1
        return applied
