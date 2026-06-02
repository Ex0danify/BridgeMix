"""
Mic FX panel — Low Cut, De-esser, Noise Suppressor, Compressor, Mic EQ.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from bridgemix.device.bridge_cast import BridgeCast

from bridgemix.gui.widgets.controls import LabeledSlider, ParamToggle, Slider
from bridgemix.gui.widgets.eq_widget import EqWidget


# ── Value-format helpers ───────────────────────────────────────────────────────

_LOW_CUT_FREQS = [
    "Flat", "20.0Hz", "25.0Hz", "31.5Hz", "40Hz", "50Hz", "63Hz", "80Hz",
    "100Hz", "125Hz", "160Hz", "200Hz", "250Hz", "315Hz", "400Hz", "500Hz",
]

_COMP_RATIOS = [
    "1.00:1", "1.12:1", "1.25:1", "1.40:1", "1.60:1", "1.80:1", "2.00:1",
    "2.50:1", "3.20:1", "4.00:1", "5.60:1", "8.00:1", "16.0:1", "Inf:1",
]

_RELEASE_MS = [
    50, 60, 80, 100, 130, 160, 200, 250, 320, 400, 500,
    640, 800, 1000, 1250, 1600, 2000, 2500, 3200, 4000, 5000,
]


def _fmt_low_cut(v: int) -> str:
    return _LOW_CUT_FREQS[v] if 0 <= v < len(_LOW_CUT_FREQS) else str(v)


def _fmt_attack(v: int) -> str:
    return "0.0ms" if v == 0 else f"{v * 10}ms"


def _fmt_release(v: int) -> str:
    ms = _RELEASE_MS[v] if 0 <= v < len(_RELEASE_MS) else v
    return f"{ms}ms"


def _fmt_ns_level(v: int) -> str:       # Gate:     0–96  → -96dB…0dB
    return f"{v - 96}dB"

def _fmt_ns_adp_level(v: int) -> str:  # Adaptive: 0–9   → "0"…"9"
    return str(v)

def _fmt_ns_exp_level(v: int) -> str:  # Expander: 39–99 → -60dB…0dB
    return f"{v - 99}dB"

def _fmt_ns_exp_release(v: int) -> str:  # Expander: 0–100 → 0ms…4000ms
    return f"{v * 40}ms"


def _fmt_threshold(v: int) -> str:
    return f"{v * 3 - 48}dB"


def _fmt_ratio(v: int) -> str:
    return _COMP_RATIOS[v] if 0 <= v < len(_COMP_RATIOS) else str(v)


def _fmt_post_gain(v: int) -> str:
    return f"+{v}dB"


# ── Main panel ────────────────────────────────────────────────────────────────

class MicFxPanel(QWidget):
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

        # Row 1: Low Cut | De-esser  (shallow boxes, one slider each)
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        row1.addWidget(self._low_cut_group(), stretch=1)
        row1.addWidget(self._de_esser_group(), stretch=1)
        vlay.addLayout(row1)

        # Row 2: Noise Suppressor | Compressor  (deeper content)
        row2 = QHBoxLayout()
        row2.setSpacing(10)
        row2.addWidget(self._noise_suppressor_group(), stretch=1)
        row2.addWidget(self._compressor_group(), stretch=1)
        vlay.addLayout(row2)

        vlay.addWidget(self._mic_eq_group_widget())
        vlay.addStretch()

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ── Low Cut ───────────────────────────────────────────────────────────────

    def _low_cut_group(self) -> QGroupBox:
        grp = QGroupBox("LOW CUT")
        lay = QVBoxLayout(grp)
        lay.setContentsMargins(10, 6, 10, 10)
        lay.setSpacing(6)
        lay.addWidget(ParamToggle("Enable", "mic_low_cut", self._bridge))
        lay.addWidget(LabeledSlider(
            "FREQUENCY", "mic_low_cut_freq", self._bridge, 0, 15, _fmt_low_cut,
        ))
        lay.addStretch()
        return grp

    # ── De-esser ──────────────────────────────────────────────────────────────

    def _de_esser_group(self) -> QGroupBox:
        grp = QGroupBox("DE-ESSER")
        lay = QVBoxLayout(grp)
        lay.setContentsMargins(10, 6, 10, 10)
        lay.setSpacing(6)
        lay.addWidget(ParamToggle("Enable", "mic_de_esser", self._bridge))
        lay.addWidget(LabeledSlider(
            "DEPTH", "mic_de_esser_depth", self._bridge, 0, 9, lambda v: str(v + 1),
        ))
        lay.addStretch()
        return grp

    # ── Noise Suppressor ──────────────────────────────────────────────────────

    def _noise_suppressor_group(self) -> QGroupBox:
        grp = QGroupBox("NOISE SUPPRESSOR")
        lay = QVBoxLayout(grp)
        lay.setContentsMargins(10, 6, 10, 10)
        lay.setSpacing(6)

        lay.addWidget(ParamToggle("Enable", "mic_ns", self._bridge))

        type_cap = QLabel("TYPE")
        type_cap.setStyleSheet("font-size: 10px; color: #7a7a82; letter-spacing: 0.04em; background-color: transparent;")
        lay.addWidget(type_cap)

        type_row = QHBoxLayout()
        self._rb_ns_gate     = QRadioButton("Gate")
        self._rb_ns_adaptive = QRadioButton("Adaptive")
        self._rb_ns_expander = QRadioButton("Expander")
        ns_bg = QButtonGroup(self)
        ns_bg.addButton(self._rb_ns_gate,     0)
        ns_bg.addButton(self._rb_ns_adaptive, 1)
        ns_bg.addButton(self._rb_ns_expander, 2)
        ns_bg.idToggled.connect(self._on_ns_type_selected)
        self._ns_type_bg = ns_bg
        type_row.addWidget(self._rb_ns_gate)
        type_row.addWidget(self._rb_ns_adaptive)
        type_row.addWidget(self._rb_ns_expander)
        type_row.addStretch()
        lay.addLayout(type_row)

        # Gate sliders
        self._ns_gate_w = QWidget()
        gate_lay = QVBoxLayout(self._ns_gate_w)
        gate_lay.setContentsMargins(0, 0, 0, 0)
        gate_lay.setSpacing(4)
        gate_lay.addWidget(LabeledSlider("LEVEL",   "mic_ns_level",   self._bridge, 0,    0x60, _fmt_ns_level))
        gate_lay.addWidget(LabeledSlider("ATTACK",  "mic_ns_attack",  self._bridge, 0,    0x0A, _fmt_attack))
        gate_lay.addWidget(LabeledSlider("RELEASE", "mic_ns_release", self._bridge, 0,    0x14, _fmt_release))
        lay.addWidget(self._ns_gate_w)

        # Adaptive sliders
        self._ns_adp_w = QWidget()
        adp_lay = QVBoxLayout(self._ns_adp_w)
        adp_lay.setContentsMargins(0, 0, 0, 0)
        adp_lay.setSpacing(4)
        adp_lay.addWidget(LabeledSlider("LEVEL", "mic_ns_adp_level", self._bridge, 0, 9, _fmt_ns_adp_level))
        lay.addWidget(self._ns_adp_w)

        # Expander sliders
        self._ns_exp_w = QWidget()
        exp_lay = QVBoxLayout(self._ns_exp_w)
        exp_lay.setContentsMargins(0, 0, 0, 0)
        exp_lay.setSpacing(4)
        exp_lay.addWidget(LabeledSlider("LEVEL",   "mic_ns_exp_level",   self._bridge, 0x27, 0x63, _fmt_ns_exp_level))
        exp_lay.addWidget(LabeledSlider("RELEASE", "mic_ns_exp_release", self._bridge, 0,    0x64, _fmt_ns_exp_release))
        lay.addWidget(self._ns_exp_w)

        # Set initial state
        ns_type = self._bridge.get_parameter("mic_ns_type")
        {0: self._rb_ns_gate, 1: self._rb_ns_adaptive, 2: self._rb_ns_expander}.get(
            ns_type, self._rb_ns_gate
        ).setChecked(True)
        self._update_ns_type_ui(ns_type)

        self._bridge.parameter_changed.connect(self._on_ns_type_param)
        lay.addStretch()
        return grp

    def _update_ns_type_ui(self, ns_type: int) -> None:
        self._ns_gate_w.setVisible(ns_type == 0)
        self._ns_adp_w.setVisible(ns_type == 1)
        self._ns_exp_w.setVisible(ns_type == 2)

    def _on_ns_type_selected(self, id_: int, checked: bool) -> None:
        if checked:
            self._bridge.set_parameter("mic_ns_type", id_)
            self._update_ns_type_ui(id_)

    def _on_ns_type_param(self, name: str, value: int) -> None:
        if name == "mic_ns_type":
            btn = {0: self._rb_ns_gate, 1: self._rb_ns_adaptive, 2: self._rb_ns_expander}.get(value)
            if btn:
                # Block signals so reflecting the device state doesn't echo a write back.
                btn.blockSignals(True)
                btn.setChecked(True)
                btn.blockSignals(False)
            self._update_ns_type_ui(value)

    # ── Compressor ────────────────────────────────────────────────────────────

    def _compressor_group(self) -> QGroupBox:
        grp = QGroupBox("COMPRESSOR")
        lay = QVBoxLayout(grp)
        lay.setContentsMargins(10, 6, 10, 10)
        lay.setSpacing(6)

        lay.addWidget(ParamToggle("Enable", "mic_compressor", self._bridge))

        mode_cap = QLabel("MODE")
        mode_cap.setStyleSheet(
            "font-size: 10px; color: #7a7a82; letter-spacing: 0.04em; background-color: transparent;"
        )
        lay.addWidget(mode_cap)

        mode_row = QHBoxLayout()
        self._rb_comp_legacy = QRadioButton("Legacy")
        self._rb_comp_modern = QRadioButton("Modern")
        comp_bg = QButtonGroup(self)
        comp_bg.addButton(self._rb_comp_legacy, 0)
        comp_bg.addButton(self._rb_comp_modern, 1)
        comp_bg.idToggled.connect(self._on_comp_mode_selected)
        self._comp_mode_bg = comp_bg
        mode_row.addWidget(self._rb_comp_legacy)
        mode_row.addWidget(self._rb_comp_modern)
        mode_row.addStretch()
        lay.addLayout(mode_row)

        # Legacy sliders
        self._comp_legacy_w = QWidget()
        leg_lay = QVBoxLayout(self._comp_legacy_w)
        leg_lay.setContentsMargins(0, 0, 0, 0)
        leg_lay.setSpacing(4)
        leg_lay.addWidget(LabeledSlider("THRESHOLD", "mic_compressor_threshold", self._bridge, 0, 0x10, _fmt_threshold))
        leg_lay.addWidget(LabeledSlider("RATIO",     "mic_compressor_ratio",     self._bridge, 0, 0x0D, _fmt_ratio))
        leg_lay.addWidget(LabeledSlider("ATTACK",    "mic_compressor_attack",    self._bridge, 0, 0x0A, _fmt_attack))
        leg_lay.addWidget(LabeledSlider("RELEASE",   "mic_compressor_release",   self._bridge, 0, 0x14, _fmt_release))
        leg_lay.addWidget(LabeledSlider("POST GAIN", "mic_compressor_post_gain", self._bridge, 0, 0x1E, _fmt_post_gain))
        lay.addWidget(self._comp_legacy_w)

        # Modern sliders
        self._comp_modern_w = QWidget()
        mod_lay = QVBoxLayout(self._comp_modern_w)
        mod_lay.setContentsMargins(0, 0, 0, 0)
        mod_lay.setSpacing(4)
        mod_lay.addWidget(LabeledSlider("AMOUNT",         "mic_comp_mod_amount", self._bridge, 0,    0x7F, str))
        mod_lay.addWidget(LabeledSlider("PEAK REDUCTION", "mic_comp_mod_peak",   self._bridge, 0,    100,  str))
        mod_lay.addWidget(LabeledSlider("GAIN",           "mic_comp_mod_gain",   self._bridge, 0,    100,  str))
        lay.addWidget(self._comp_modern_w)

        # Set initial state
        comp_mode = self._bridge.get_parameter("mic_comp_mode")
        (self._rb_comp_modern if comp_mode else self._rb_comp_legacy).setChecked(True)
        self._update_comp_mode_ui(comp_mode)

        self._bridge.parameter_changed.connect(self._on_comp_mode_param)
        return grp

    def _update_comp_mode_ui(self, mode: int) -> None:
        self._comp_legacy_w.setVisible(mode == 0)
        self._comp_modern_w.setVisible(mode == 1)

    def _on_comp_mode_selected(self, id_: int, checked: bool) -> None:
        if checked:
            self._bridge.set_parameter("mic_comp_mode", id_)
            self._update_comp_mode_ui(id_)

    def _on_comp_mode_param(self, name: str, value: int) -> None:
        if name == "mic_comp_mode":
            btn = self._rb_comp_modern if value else self._rb_comp_legacy
            btn.blockSignals(True)
            btn.setChecked(True)
            btn.blockSignals(False)
            self._update_comp_mode_ui(value)

    # ── Mic Manual EQ ─────────────────────────────────────────────────────────

    def _mic_eq_group_widget(self) -> QGroupBox:
        grp = QGroupBox("MIC MANUAL EQ")
        vlay = QVBoxLayout(grp)
        vlay.setContentsMargins(10, 6, 10, 10)
        vlay.addWidget(EqWidget("mic_eq", self._bridge, title="EQ"))
        return grp
