"""Tests for the plugin styling kit (``bridgemix.plugins.style``)."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QLabel, QPushButton, QSlider

from bridgemix.plugins import style


# ── Tokens ────────────────────────────────────────────────────────────────────

def test_hex_tokens_are_strings():
    assert style.ACCENT.startswith("#")
    assert style.TEXT_MUTED.startswith("#")
    assert style.GREEN.startswith("#") and style.RED.startswith("#")


def test_accent_fill_tokens():
    # The tinted accent fills used for selected/checked states.
    assert "rgba" in style.ACCENT_SOFT
    assert "rgba" in style.ACCENT_GLOW


def test_channel_colours_present_and_copied():
    assert style.CHANNEL_COLORS["mic"].startswith("#")
    # A defensive copy — mutating it must not corrupt the shared theme.
    style.CHANNEL_COLORS["mic"] = "#000000"
    from bridgemix import theme
    assert theme.CHANNEL_COLORS["mic"] != "#000000"


def test_qcolor_tokens():
    assert isinstance(style.Q_ACCENT, QColor)
    assert isinstance(style.Q_TEXT_MUTED, QColor)
    assert isinstance(style.Q_BG, QColor)


# ── Role helpers ──────────────────────────────────────────────────────────────

def test_primary_button(qapp):
    btn = QPushButton("Save")
    assert style.primary_button(btn) is btn
    assert btn.objectName() == "btn_primary"


def test_danger_button(qapp):
    assert style.danger_button(QPushButton()).objectName() == "DangerBtn"


def test_page_title(qapp):
    assert style.page_title(QLabel("x")).objectName() == "PageTitle"


def test_fader(qapp):
    assert style.fader(QSlider(Qt.Orientation.Vertical)).objectName() == "MixerFader"


def test_readonly_fader(qapp):
    sl = style.fader(QSlider(Qt.Orientation.Vertical), readonly=True)
    assert sl.objectName() == "OutputFaderRO"


def test_segmented_button(qapp):
    assert style.segmented_button(QPushButton("Mic")).objectName() == "MicTypeBtn"


def test_section_and_value_labels(qapp):
    assert style.section_label(QLabel("OPTIONS")).objectName() == "StripActionLabel"
    assert style.value_label(QLabel("0 dB")).objectName() == "FaderValue"


def test_muted_sets_colour(qapp):
    lbl = style.muted(QLabel("hi"))
    assert style.TEXT_MUTED in lbl.styleSheet()


# ── Reusable controls ─────────────────────────────────────────────────────────

def test_toggle_switch(qapp):
    sw = style.ToggleSwitch(checked=True)
    assert sw.isChecked() is True


def test_scroll_guarded_inputs_and_meter_construct(qapp):
    style.ComboBox()
    style.SpinBox()
    style.PeakMeter(100)
    style.Slider(Qt.Orientation.Horizontal)
