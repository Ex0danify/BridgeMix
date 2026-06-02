"""
Shared reusable control widgets for BridgeMix panels.

Public classes
--------------
Slider               — QSlider that ignores scroll-wheel unless focused (clicked)
LimitSlider          — Slider that paints a fixed informational marker line
PeakMeter            — vertical level meter with a track-anchored colour scale
ScrollGuardComboBox  — QComboBox with the same focus-before-scroll guard
ScrollGuardSpinBox   — QSpinBox with the same focus-before-scroll guard
ToggleSwitch         — pill-shaped ON/OFF toggle drawn with QPainter
ParamToggle          — label + ToggleSwitch, bound to a BridgeCast bool parameter
LabeledSlider        — section caption + horizontal slider + right-side value label,
                       bound to a BridgeCast int parameter with a custom format function
ParamCheck           — plain QCheckBox bound to a BridgeCast bool parameter
"""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QStyle,
    QStyleOptionSlider,
    QVBoxLayout,
    QWidget,
)


# ── Scroll-safe widgets ───────────────────────────────────────────────────────
# All three classes share the same rule: wheel events only take effect once the
# widget has keyboard focus (i.e. the user clicked it first).  Without focus the
# event is passed up so parent QScrollAreas can scroll normally.

class Slider(QSlider):
    """QSlider that ignores wheel events unless it already has keyboard focus."""

    def wheelEvent(self, event) -> None:
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class ScrollGuardComboBox(QComboBox):
    """QComboBox that ignores wheel events unless it already has keyboard focus.

    QComboBox defaults to WheelFocus, which causes Qt to focus the widget
    *before* wheelEvent fires — making hasFocus() always True at that point.
    Switching to StrongFocus (click/tab only) restores the expected behaviour.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event) -> None:
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class ScrollGuardSpinBox(QSpinBox):
    """QSpinBox that ignores wheel events unless it already has keyboard focus.

    Same WheelFocus → StrongFocus fix as ScrollGuardComboBox.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event) -> None:
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()

from bridgemix import theme

if TYPE_CHECKING:
    from bridgemix.device.bridge_cast import BridgeCast


# ── LimitSlider ───────────────────────────────────────────────────────────────

class LimitSlider(Slider):
    """Horizontal Slider that paints a vertical marker line at a fixed value.

    Used to show a soft ceiling on a slider (e.g. the LED-brightness level above
    which the device needs extra bus power).  The marker is informational only —
    it does not constrain the slider's range.
    """

    def __init__(self, orientation, parent: QWidget | None = None) -> None:
        super().__init__(orientation, parent)
        self._limit: int | None = None
        self._limit_color = QColor("#f59e0b")   # amber warning marker

    def set_limit(self, value: int | None) -> None:
        self._limit = value
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._limit is None:
            return
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        groove = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, opt, QStyle.SubControl.SC_SliderGroove, self
        )
        handle = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, opt, QStyle.SubControl.SC_SliderHandle, self
        )
        span = groove.width() - handle.width()
        pos = QStyle.sliderPositionFromValue(self.minimum(), self.maximum(), self._limit, span)
        cx = groove.x() + pos + handle.width() / 2.0
        cy = groove.center().y()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(self._limit_color, 2))
        p.drawLine(int(cx), int(cy - 9), int(cx), int(cy + 9))
        p.end()


# ── PeakMeter ─────────────────────────────────────────────────────────────────

class PeakMeter(QWidget):
    """Vertical peak meter with a colour scale anchored to the full track.

    A gradient-filled QProgressBar maps its gradient to the *chunk* (the filled
    portion), so the green→amber→red ramp is squeezed into whatever is lit and
    red always shows at the tip.  Here the gradient is anchored to the whole
    track and the fill is clipped to the current level, so amber/red only appear
    once the signal actually climbs into those zones.  A peak-hold cap decays
    over a couple of seconds.
    """

    _WELL = QColor("#08080a")
    _RIM  = QColor(255, 255, 255, 28)    # ≈ rgba(255,255,255,0.11)
    _PEAK = QColor(255, 255, 255, 170)

    # Scale stops (0.0 = bottom of track, 1.0 = top).  Green floor, amber from
    # ~74%, red from ~90% — VU convention, deliberately not the brand orange.
    _STOPS = (
        (0.00, "#1f9d57"),
        (0.55, "#2bd46a"),
        (0.74, "#f5a524"),
        (0.90, "#f87171"),
        (1.00, "#ef4444"),
    )

    def __init__(self, max_value: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._max = max(1, int(max_value))
        self._value = 0
        self._peak = 0

    def setValue(self, v: int) -> None:
        v = max(0, min(self._max, int(v)))
        # Peak-hold: jump up instantly, decay slowly (called ~20×/s by the heartbeat).
        self._peak = v if v >= self._peak else max(v, self._peak - int(self._max * 0.02))
        if v != self._value:
            self._value = v
        self.update()

    def value(self) -> int:
        return self._value

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = float(self.width()), float(self.height())
        radius = 3.0

        outer = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._WELL)
        p.drawRoundedRect(outer, radius, radius)

        inner = outer.adjusted(1.0, 1.0, -1.0, -1.0)
        clip = QPainterPath()
        clip.addRoundedRect(inner, radius - 1.0, radius - 1.0)

        # Gradient in painter (logical) coordinates → fixed to the track, so the
        # fill reveals colours by height rather than restretching them.
        grad = QLinearGradient(0.0, inner.bottom(), 0.0, inner.top())
        for pos, col in self._STOPS:
            grad.setColorAt(pos, QColor(col))

        frac = self._value / self._max
        fill_h = inner.height() * frac
        if fill_h > 0.0:
            fill = QRectF(inner.left(), inner.bottom() - fill_h, inner.width(), fill_h)
            p.save()
            p.setClipPath(clip)
            p.fillRect(fill, grad)
            p.restore()

        # Peak-hold cap
        if self._peak > 0:
            py = inner.bottom() - inner.height() * (self._peak / self._max)
            p.setPen(QPen(self._PEAK, 1.0))
            p.drawLine(QPointF(inner.left(), py), QPointF(inner.right(), py))

        # Rim
        p.setPen(QPen(self._RIM, 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(outer, radius, radius)
        p.end()


# ── ToggleSwitch ──────────────────────────────────────────────────────────────

class ToggleSwitch(QWidget):
    """
    Pill-shaped toggle switch painted with QPainter.

      ON  → orange track  (#e05c12) + white knob slides to the right
      OFF → grey track    (#32323A) + white knob on the left

    Emits ``toggled(bool)`` whenever the user clicks.
    """

    toggled = pyqtSignal(bool)

    _W    = 40
    _H    = 22
    _C_ON  = theme.Q_ACCENT    # brand orange (#e05c12)
    _C_OFF = theme.Q_SURFACE_5 # inactive grey (#313136)

    def __init__(self, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checked = bool(checked)
        self.setFixedSize(self._W, self._H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ── public API ────────────────────────────────────────────────────────────

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, v: bool) -> None:
        v = bool(v)
        if self._checked != v:
            self._checked = v
            self.update()

    # ── events ────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._checked = not self._checked
            self.update()
            self.toggled.emit(self._checked)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self._W, self._H

        # Track — full-radius pill
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._C_ON if self._checked else self._C_OFF)
        p.drawRoundedRect(0, 0, W, H, H / 2, H / 2)

        # Knob — white circle, 2 px inset from track edge
        pad = 2
        d   = H - 2 * pad
        x   = (W - pad - d) if self._checked else pad
        p.setBrush(QColor(255, 255, 255))
        p.drawEllipse(x, pad, d, d)

        p.end()


# ── ParamToggle ───────────────────────────────────────────────────────────────

class ParamToggle(QWidget):
    """
    Label on the left, pill toggle on the right, bound to a bridge bool parameter.

    Usage::

        ParamToggle("Enable", "mic_low_cut", bridge)
        ParamToggle("",       "mic_ns",      bridge)   # no label → toggle only
    """

    def __init__(self, label: str, param: str, bridge: "BridgeCast",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._param  = param
        self._bridge = bridge
        self._block  = False

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        if label:
            row.addWidget(QLabel(label))

        row.addStretch()

        self._sw = ToggleSwitch(bool(bridge.get_parameter(param)))
        self._sw.toggled.connect(self._on_toggled)
        row.addWidget(self._sw)

        bridge.parameter_changed.connect(self._on_param)

    def _on_toggled(self, checked: bool) -> None:
        if not self._block:
            self._bridge.set_parameter(self._param, 1 if checked else 0)

    def _on_param(self, name: str, value: int) -> None:
        if name == self._param:
            self._block = True
            self._sw.setChecked(bool(value))
            self._block = False


# ── LabeledSlider ─────────────────────────────────────────────────────────────

class LabeledSlider(QWidget):
    """
    Compact slider row with a small uppercase caption and a formatted value label:

      CAPTION
      [═══════════════════════════════]  value_str

    ``format_fn`` converts the integer parameter value to a display string.
    Defaults to ``str``.  Example::

        LabeledSlider("THRESHOLD", "mic_compressor_threshold", bridge, 0, 16,
                      lambda v: f"{v * 3 - 48}dB")
    """

    def __init__(
        self,
        label: str,
        param: str,
        bridge: "BridgeCast",
        min_val: int,
        max_val: int,
        format_fn: Callable[[int], str] = str,
        parent: QWidget | None = None,
        *,
        limit: int | None = None,
        limit_tooltip: str = "",
        value_width: int = 58,
    ) -> None:
        super().__init__(parent)
        self._param  = param
        self._bridge = bridge
        self._fmt    = format_fn
        self._block  = False

        vlay = QVBoxLayout(self)
        vlay.setContentsMargins(0, 4, 0, 0)
        vlay.setSpacing(2)

        if label:
            cap = QLabel(label)
            cap.setStyleSheet("font-size: 10px; color: #7a7a82; letter-spacing: 0.04em; background-color: transparent;")
            vlay.addWidget(cap)

        row = QHBoxLayout()
        row.setSpacing(8)

        # Use a LimitSlider when a marker value is given (e.g. a soft power ceiling).
        if limit is not None:
            self._slider = LimitSlider(Qt.Orientation.Horizontal)
            self._slider.set_limit(limit)
        else:
            self._slider = Slider(Qt.Orientation.Horizontal)
        if limit_tooltip:
            self._slider.setToolTip(limit_tooltip)
        self._slider.setRange(min_val, max_val)
        self._slider.setValue(bridge.get_parameter(param))
        row.addWidget(self._slider, stretch=1)

        self._val_lbl = QLabel(format_fn(bridge.get_parameter(param)))
        self._val_lbl.setFixedWidth(value_width)
        self._val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._val_lbl.setStyleSheet(
            "font-family: 'Consolas', monospace; font-size: 11px; color: #e8e8ea;"
        )
        row.addWidget(self._val_lbl)
        vlay.addLayout(row)

        self._slider.valueChanged.connect(self._on_moved)
        bridge.parameter_changed.connect(self._on_param)

    def _on_moved(self, v: int) -> None:
        if self._block:
            return
        self._val_lbl.setText(self._fmt(v))
        self._bridge.set_parameter(self._param, v)

    def _on_param(self, name: str, value: int) -> None:
        if name == self._param:
            self._block = True
            self._slider.setValue(value)
            self._val_lbl.setText(self._fmt(value))
            self._block = False


# ── ParamCheck ────────────────────────────────────────────────────────────────

class ParamCheck(QCheckBox):
    """
    Plain QCheckBox bound to a bridge boolean parameter (0/1).

    Prefer ``ParamToggle`` for new UI panels; this is kept for panels that
    pre-date the pill-toggle design (e.g. the Mic Manual EQ enable checkbox).
    """

    def __init__(self, label: str, param: str, bridge: "BridgeCast",
                 parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self._param  = param
        self._bridge = bridge
        self._block  = False
        self.setChecked(bool(bridge.get_parameter(param)))
        self.toggled.connect(self._on_toggled)
        bridge.parameter_changed.connect(self._on_param)

    def _on_toggled(self, checked: bool) -> None:
        if not self._block:
            self._bridge.set_parameter(self._param, 1 if checked else 0)

    def _on_param(self, name: str, value: int) -> None:
        if name == self._param:
            self._block = True
            self.setChecked(bool(value))
            self._block = False
