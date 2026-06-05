"""Styling kit for plugins — a stable window onto the app's look.

The global stylesheet (set on the QApplication) already cascades to plugin
widgets, so a plain ``QPushButton``/``QComboBox``/``QListWidget``/``QGroupBox``
already matches the app. This module fills the three gaps a plugin can't reach
otherwise:

  * **tokens** — the colour palette (hex for stylesheets, ``Q_*`` QColors for
    QPainter), so custom drawing matches the theme;
  * **role helpers** — apply a named look (primary/danger/segmented button, page
    title, section/value/muted label, mixer fader) without hardcoding the app's
    internal object names;
  * **controls** — the signature custom widgets (the orange ``ToggleSwitch``, the
    ``PeakMeter``, scroll-guarded inputs).

Usage::

    from bridgemix.plugins import style

    save = style.primary_button(QPushButton("Save"))
    toggle = style.ToggleSwitch(checked=True)
    label.setStyleSheet(f"color: {style.ACCENT};")
"""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from bridgemix import theme
# Re-exported under stable names; internals may move, these won't.
from bridgemix.gui.widgets.controls import (  # noqa: F401
    PeakMeter,
    ScrollGuardComboBox as ComboBox,
    ScrollGuardSpinBox as SpinBox,
    Slider,
    ToggleSwitch,
)

# ── Tokens (hex strings — use in setStyleSheet / f-strings) ─────────────────────
BG = theme.BG
SURFACE = theme.SURFACE
SURFACE_2 = theme.SURFACE_2
SURFACE_3 = theme.SURFACE_3
SURFACE_4 = theme.SURFACE_4
SURFACE_5 = theme.SURFACE_5

TEXT = theme.TEXT
TEXT_MUTED = theme.TEXT_MUTED
TEXT_FAINT = theme.TEXT_FAINT

ACCENT = theme.ACCENT
ACCENT_HOVER = theme.ACCENT_HOVER
ACCENT_SOFT = theme.ACCENT_SOFT    # rgba — accent-tinted fill (selected / checked)
ACCENT_GLOW = theme.ACCENT_GLOW    # rgba — stronger accent fill / glow

GREEN = theme.GREEN
RED = theme.RED
BLUE = theme.BLUE

# Per-channel accent colours, e.g. CHANNEL_COLORS["mic"] == "#e05c12".
CHANNEL_COLORS: dict[str, str] = dict(theme.CHANNEL_COLORS)

# ── Tokens (QColor — use in QPainter-based widgets) ─────────────────────────────
Q_BG = theme.Q_BG
Q_ACCENT = theme.Q_ACCENT
Q_ACCENT_HOVER = theme.Q_ACCENT_HOVER
Q_TEXT = theme.Q_TEXT
Q_TEXT_MUTED = theme.Q_TEXT_MUTED
Q_TEXT_FAINT = theme.Q_TEXT_FAINT
Q_RED = theme.Q_RED
Q_GREEN = theme.Q_GREEN
Q_SURFACE_4 = theme.Q_SURFACE_4
Q_SURFACE_5 = theme.Q_SURFACE_5


# ── Role helpers ────────────────────────────────────────────────────────────────


def _role(widget: QWidget, object_name: str) -> QWidget:
    """Tag *widget* with an object name the global stylesheet styles, and refresh.

    Re-polishing is needed because the object name is set after construction, so
    the QSS rule wouldn't otherwise re-evaluate.
    """
    widget.setObjectName(object_name)
    s = widget.style()
    s.unpolish(widget)
    s.polish(widget)
    widget.update()
    return widget


def primary_button(button: QWidget) -> QWidget:
    """Style a button as the filled orange primary action. Returns it."""
    return _role(button, "btn_primary")


def danger_button(button: QWidget) -> QWidget:
    """Style a button as a red destructive action. Returns it."""
    return _role(button, "DangerBtn")


def segmented_button(button: QWidget) -> QWidget:
    """Style a (checkable) button as a segmented selector — uppercase, accent when
    checked. Use a group of these for mutually-exclusive choices. Returns it.

    (A plain checkable ``QPushButton`` already turns accent when checked; this is
    the more refined segmented look.)
    """
    return _role(button, "MicTypeBtn")


def page_title(label: QWidget) -> QWidget:
    """Style a label as a large page title. Returns it."""
    return _role(label, "PageTitle")


def section_label(label: QWidget) -> QWidget:
    """Style a label as a small uppercase section caption. Returns it."""
    return _role(label, "StripActionLabel")


def value_label(label: QWidget) -> QWidget:
    """Style a label as a small monospace value readout (pairs with fader()). Returns it."""
    return _role(label, "FaderValue")


def fader(slider: QWidget, *, readonly: bool = False) -> QWidget:
    """Give a vertical slider the wide mixer-fader look — orange, or grey when
    *readonly* (a non-interactive level display). Returns it."""
    return _role(slider, "OutputFaderRO" if readonly else "MixerFader")


def muted(label: QWidget) -> QWidget:
    """Style a label as secondary/muted text. Returns it."""
    label.setStyleSheet(f"color: {TEXT_MUTED}; background: transparent;")
    return label
