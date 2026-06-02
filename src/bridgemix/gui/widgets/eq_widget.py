"""
Graphical parametric EQ widget.

Shared by MicFxPanel (prefix='mic_eq') and any panel with an EQ section.
Usage::

    widget = EqWidget("mic_eq", bridge)
    layout.addWidget(widget)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from bridgemix import theme
from bridgemix.audio import SpectrumAnalyzer
from bridgemix.gui.widgets.controls import ParamToggle, Slider, ToggleSwitch

if TYPE_CHECKING:
    from bridgemix.device.bridge_cast import BridgeCast


# ── Band metadata ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _Band:
    n: int           # 1-based band number
    kind: str        # 'peak' | 'low_shelf' | 'high_shelf'
    f_min: float     # Hz at raw param = 0
    f_max: float     # Hz at raw param = f_steps
    f_steps: int     # max raw value for freq
    has_q: bool
    # Explicit raw->Hz table (index = raw value).  When given, the device uses a
    # fixed frequency list rather than a smooth log curve, so _raw_to_freq /
    # _freq_to_raw use the table instead of log interpolation.
    freqs: tuple[float, ...] | None = None


# Device frequency tables (index = raw value), captured from a full official-app
# sweep of every band 2026-06-01.  These are fixed discrete lists, NOT log/linear
# curves, so the EQ uses them directly.  Bands 2-4 share a 31-step 20Hz-470Hz table.
def _ftab(*hz: float) -> tuple[float, ...]:
    return tuple(float(x) for x in hz)

_FREQS_B1 = _ftab(20, 25, 30, 35, 40, 50, 62, 70, 78, 88, 100, 110, 125, 148,
                  176, 200, 220, 250, 300, 350, 400)
_FREQS_B234 = _ftab(20, 25, 30, 35, 40, 44, 50, 55, 62, 70, 74, 78, 83, 88, 93,
                    100, 110, 125, 148, 176, 200, 250, 300, 315, 330, 350, 375,
                    400, 420, 445, 470)
_FREQS_B567 = _ftab(315, 330, 350, 375, 400, 420, 445, 470, 500, 530, 560, 600,
                    630, 665, 700, 750, 800, 840, 900, 940, 1000, 1200, 1400,
                    1600, 1800, 2000, 2200, 2500, 2700, 3000, 3300)
_FREQS_B89 = _ftab(3000, 3300, 3600, 3800, 4000, 4200, 4500, 4800, 5000, 5300,
                   5700, 6000, 6300, 6700, 7000, 7600, 8000, 8500, 9000, 9500,
                   10000, 11000, 12000, 13000, 14000, 15000, 16000, 17000,
                   18000, 19000, 20000)
_FREQS_B10 = _ftab(800, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000,
                   10000, 11000, 12000, 13000, 14000, 15000, 16000, 17000,
                   18000, 19000, 20000)


def _band(n: int, kind: str, has_q: bool, freqs: tuple[float, ...]) -> _Band:
    return _Band(n, kind, freqs[0], freqs[-1], len(freqs) - 1, has_q, freqs)


_BANDS: list[_Band] = [
    _band(1,  'low_shelf',  False, _FREQS_B1),
    _band(2,  'peak',       True,  _FREQS_B234),
    _band(3,  'peak',       True,  _FREQS_B234),
    _band(4,  'peak',       True,  _FREQS_B234),
    _band(5,  'peak',       True,  _FREQS_B567),
    _band(6,  'peak',       True,  _FREQS_B567),
    _band(7,  'peak',       True,  _FREQS_B567),
    _band(8,  'peak',       True,  _FREQS_B89),
    _band(9,  'peak',       True,  _FREQS_B89),
    _band(10, 'high_shelf', False, _FREQS_B10),
]

_REGIONS: list[tuple[str, float, float]] = [
    ("SUB BASS",         20.0,    80.0),
    ("BOOM",             80.0,   200.0),
    ("BROADCAST",       200.0,   600.0),
    ("NASAL",           600.0,  1500.0),
    ("PRESENCE & ESSES",1500.0, 8000.0),
    ("AIR",            8000.0, 20000.0),
]

_DB_MAX  = 12.0       # ±dB visible on Y axis (device gain range is ±12 dB)

# Spectrum analyzer overlay (Game EQ): dBFS range mapped to the canvas height,
# and the number of horizontal buckets the FFT bins are reduced to for drawing.
_SPEC_DB_MIN  = -90.0
_SPEC_DB_MAX  = -20.0
_SPEC_BUCKETS = 256
_SPEC_SMOOTH3 = np.array([0.25, 0.5, 0.25])   # light edge-softening kernel
_C_SPECTRUM   = QColor(150, 152, 162)
_FS      = 48000.0    # sample rate for biquad math
_N_PLOT  = 300        # number of frequency points in curve
_LOG_RNG = math.log10(20000.0 / 20.0)

# Colors
_C_BG       = QColor(theme.BG)
_C_GRID     = QColor(theme.TEXT_FAINT)
_C_ZERO_LINE = QColor(theme.SURFACE_5)
_C_CURVE    = QColor(theme.ACCENT)
_C_NODE     = QColor(255, 255, 255)
_C_NODE_HOV = QColor(theme.ACCENT_HOVER)
_C_LABEL    = QColor(theme.TEXT_MUTED)

_NODE_R   = 5    # px radius of band dot
_NODE_HIT = 14   # px hit-test radius

# Max device-write rate while dragging a band.  Qt fires many move events per
# pixel; without coalescing, a fast EQ sweep bursts DT1 writes faster than the
# device's MIDI input buffer drains and overflows it.  The node still follows the
# mouse every frame (painted from pending values); only the TX is rate-limited,
# and the final value is always flushed on mouse release.
_TX_THROTTLE_MS = 40   # ~25 Hz


# ── Parameter ↔ physical value conversions ────────────────────────────────────

def _raw_to_freq(raw: int, band: _Band) -> float:
    """Map device integer to Hz (fixed table if the band has one, else log)."""
    if band.freqs is not None:
        return band.freqs[max(0, min(len(band.freqs) - 1, raw))]
    if raw <= 0:
        return band.f_min
    if raw >= band.f_steps:
        return band.f_max
    return band.f_min * (band.f_max / band.f_min) ** (raw / band.f_steps)


def _freq_to_raw(hz: float, band: _Band) -> int:
    hz = max(band.f_min, min(band.f_max, hz))
    if band.freqs is not None:
        return min(range(len(band.freqs)), key=lambda i: abs(band.freqs[i] - hz))
    t = math.log(hz / band.f_min) / math.log(band.f_max / band.f_min)
    return max(0, min(band.f_steps, int(round(t * band.f_steps))))


def _raw_to_db(raw: int) -> float:
    """0x00=−12 dB, 0x0C=0 dB, 0x18=+12 dB (1 dB per step, confirmed 2026-06-01)."""
    return float(raw - 12)


def _db_to_raw(db: float) -> int:
    return max(0, min(24, int(round(db + 12))))


# Device Q table (index = raw value), confirmed 2026-06-01 sweep — shared by all
# peak bands (2-9).  32 steps: 0.3 (widest) … 16.0 (narrowest).
_Q_TABLE: tuple[float, ...] = (
    0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2,
    2.5, 2.8, 3.1, 3.5, 4.0, 4.5, 5.0, 5.6, 6.3, 7.1, 8.0, 9.0, 10.0, 11.2,
    12.5, 14.0, 16.0,
)


def _raw_to_q(raw: int) -> float:
    """Map device integer to Q (fixed table, confirmed 2026-06-01 sweep)."""
    return _Q_TABLE[max(0, min(len(_Q_TABLE) - 1, raw))]


# ── Canvas coordinate helpers ─────────────────────────────────────────────────

def _fx(hz: float, w: float) -> float:
    """Frequency (Hz) → X pixel on [0, w], log scale."""
    return w * math.log10(max(20.0, hz) / 20.0) / _LOG_RNG


def _xf(x: float, w: float) -> float:
    """X pixel → frequency (Hz)."""
    return 20.0 * 10.0 ** (x / w * _LOG_RNG)


def _fy(db: float, h: float) -> float:
    """dB → Y pixel; 0 dB at centre, +DB_MAX at top."""
    return h * 0.5 * (1.0 - db / _DB_MAX)


def _yf(y: float, h: float) -> float:
    """Y pixel → dB."""
    return _DB_MAX * (1.0 - 2.0 * y / h)


# ── Biquad magnitude response ─────────────────────────────────────────────────

def _mag_db(f: float, b0: float, b1: float, b2: float,
            a0: float, a1: float, a2: float) -> float:
    """Evaluate a biquad's magnitude response in dB at frequency f Hz."""
    w = 2.0 * math.pi * f / _FS
    cw  = math.cos(w);   sw  = math.sin(w)
    c2w = math.cos(2*w); s2w = math.sin(2*w)
    nr = b0 + b1*cw + b2*c2w;  ni = -(b1*sw + b2*s2w)
    dr = a0 + a1*cw + a2*c2w;  di = -(a1*sw + a2*s2w)
    d2 = dr*dr + di*di
    if d2 < 1e-30:
        return 0.0
    return 10.0 * math.log10(max((nr*nr + ni*ni) / d2, 1e-20))


def _peak_db(f: float, f0: float, gain_db: float, Q: float) -> float:
    if abs(gain_db) < 0.01:
        return 0.0
    A    = 10.0 ** (gain_db / 40.0)
    w0   = 2.0 * math.pi * f0 / _FS
    alph = math.sin(w0) / (2.0 * max(0.1, Q))
    b1   = -2.0 * math.cos(w0)
    return _mag_db(f, 1.0+alph*A, b1, 1.0-alph*A,
                      1.0+alph/A, b1, 1.0-alph/A)


def _shelf_db(f: float, f0: float, gain_db: float, high: bool) -> float:
    if abs(gain_db) < 0.01:
        return 0.0
    A    = 10.0 ** (gain_db / 40.0)
    w0   = 2.0 * math.pi * f0 / _FS
    cw   = math.cos(w0); sw = math.sin(w0)
    alph = sw / 2.0 * math.sqrt(2.0)
    sqA  = math.sqrt(A)
    if not high:
        b0 =  A*((A+1)-(A-1)*cw+2*sqA*alph)
        b1 = 2*A*((A-1)-(A+1)*cw)
        b2 =  A*((A+1)-(A-1)*cw-2*sqA*alph)
        a0 =    (A+1)+(A-1)*cw+2*sqA*alph
        a1 = -2*((A-1)+(A+1)*cw)
        a2 =    (A+1)+(A-1)*cw-2*sqA*alph
    else:
        b0 =  A*((A+1)+(A-1)*cw+2*sqA*alph)
        b1 = -2*A*((A-1)+(A+1)*cw)
        b2 =  A*((A+1)+(A-1)*cw-2*sqA*alph)
        a0 =    (A+1)-(A-1)*cw+2*sqA*alph
        a1 =  2*((A-1)-(A+1)*cw)
        a2 =    (A+1)-(A-1)*cw-2*sqA*alph
    return _mag_db(f, b0, b1, b2, a0, a1, a2)


def _band_db(f: float, band: _Band, gain_db: float, f0: float, Q: float) -> float:
    if band.kind == 'peak':
        return _peak_db(f, f0, gain_db, Q)
    return _shelf_db(f, f0, gain_db, high=(band.kind == 'high_shelf'))


# ── EQ canvas (the painted widget) ────────────────────────────────────────────

class _EqCanvas(QWidget):
    """Dark canvas with grid, frequency response curve, and draggable band nodes."""

    def __init__(self, prefix: str, bridge: "BridgeCast") -> None:
        super().__init__()
        self._prefix = prefix
        self._bridge = bridge

        # Drag state
        self._drag_band:      int | None = None
        self._hover_band:     int | None = None
        self._drag_mouse_x:   float = 0.0
        self._drag_mouse_y:   float = 0.0
        self._drag_node_x:    float = 0.0
        self._drag_node_y:    float = 0.0
        self._drag_f_raw:     int   = 0

        self._curve: list[tuple[float, float]] = []
        # Spectrum overlay: per-bucket normalized level [0,1] (None = no data).
        self._spec_y: np.ndarray | None = None

        # Coalesced device writes while dragging: latest pending raw value per
        # parameter, flushed to the device on a throttle timer (see _TX_THROTTLE_MS).
        self._pending: dict[str, int] = {}
        self._tx_timer = QTimer(self)
        self._tx_timer.setInterval(_TX_THROTTLE_MS)
        self._tx_timer.timeout.connect(self._flush_pending)

        self.setFixedHeight(240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        bridge.parameter_changed.connect(self._on_param)
        self._recompute()

    # ── internal helpers ──────────────────────────────────────────────────────

    def _pname(self, n: int, kind: str) -> str:
        return f"{self._prefix}_band{n}_{kind}"

    def _eff(self, name: str) -> int:
        """Effective raw value: the pending (in-drag) value if any, else device."""
        return self._pending.get(name, self._bridge.get_parameter(name))

    def _gain_db(self, idx: int) -> float:
        return _raw_to_db(self._eff(self._pname(idx + 1, 'gain')))

    def _freq_hz(self, idx: int) -> float:
        return _raw_to_freq(self._eff(self._pname(idx + 1, 'freq')), _BANDS[idx])

    def _q_val(self, idx: int) -> float:
        if not _BANDS[idx].has_q:
            return 0.707
        return _raw_to_q(self._bridge.get_parameter(self._pname(idx + 1, 'q')))

    def _node_pos(self, idx: int) -> tuple[float, float]:
        w, h = float(self.width()), float(self.height())
        return _fx(self._freq_hz(idx), w), _fy(self._gain_db(idx), h)

    def _hit_test(self, px: float, py: float) -> int | None:
        best_d2, best_i = float(_NODE_HIT * _NODE_HIT), None
        for i in range(10):
            nx, ny = self._node_pos(i)
            d2 = (px - nx) ** 2 + (py - ny) ** 2
            if d2 < best_d2:
                best_d2, best_i = d2, i
        return best_i

    def _recompute(self) -> None:
        w = max(1, self.width())
        h = max(1, self.height())
        log_step = _LOG_RNG / (_N_PLOT - 1)
        pts: list[tuple[float, float]] = []
        for k in range(_N_PLOT):
            f = 20.0 * 10.0 ** (k * log_step)
            db_sum = sum(
                _band_db(f, _BANDS[i], self._gain_db(i), self._freq_hz(i), self._q_val(i))
                for i in range(10)
            )
            pts.append((_fx(f, w), _fy(db_sum, h)))
        self._curve = pts

    def _on_param(self, name: str, _v: int) -> None:
        prefix = self._prefix + '_band'
        if name.startswith(prefix):
            self._recompute()
            self.update()

    # ── spectrum overlay ───────────────────────────────────────────────────────

    def set_spectrum(self, freqs, db) -> None:
        """Bin an FFT (freqs Hz, magnitude dB) onto the log axis and repaint.

        Each log bucket takes the max of the FFT bins that fall in it (so the
        dense high end stays granular like the device app); empty buckets at the
        sparse low end are filled by interpolation (smooth hump). No frequency
        smoothing — only light temporal smoothing for stable motion.
        """
        freqs = np.asarray(freqs, dtype=np.float64)
        db = np.asarray(db, dtype=np.float64)
        m = (freqs >= 20.0) & (freqs <= 20000.0)
        if int(m.sum()) < 2:
            return
        xf = np.log10(freqs[m] / 20.0) / _LOG_RNG               # 0..1 across the axis
        idx = np.clip((xf * _SPEC_BUCKETS).astype(int), 0, _SPEC_BUCKETS - 1)
        filled = np.full(_SPEC_BUCKETS, -np.inf)
        np.maximum.at(filled, idx, db[m])
        has = np.isfinite(filled)
        if int(has.sum()) < 2:
            return
        allx = np.arange(_SPEC_BUCKETS)
        bucket_db = np.interp(allx, allx[has], filled[has])     # fill empty buckets
        level = np.clip(
            (bucket_db - _SPEC_DB_MIN) / (_SPEC_DB_MAX - _SPEC_DB_MIN), 0.0, 1.0
        )
        # Light edge-softening (3-tap) — rounds hard bucket steps, keeps detail.
        level = np.convolve(level, _SPEC_SMOOTH3, mode="same")
        # Light temporal smoothing: instant attack, moderate release.
        if self._spec_y is None or self._spec_y.shape != level.shape:
            self._spec_y = level
        else:
            rising = level > self._spec_y
            self._spec_y = np.where(rising, level, self._spec_y * 0.55 + level * 0.45)
        self.update()

    def clear_spectrum(self) -> None:
        if self._spec_y is not None:
            self._spec_y = None
            self.update()

    def resizeEvent(self, event) -> None:
        self._recompute()
        super().resizeEvent(event)

    # ── mouse events ──────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        px, py = event.position().x(), event.position().y()
        i = self._hit_test(px, py)
        if i is not None:
            self._drag_band    = i
            self._drag_mouse_x = px
            self._drag_mouse_y = py
            self._drag_node_x, self._drag_node_y = self._node_pos(i)
            self._drag_f_raw = self._bridge.get_parameter(self._pname(i + 1, 'freq'))
            self.setCursor(Qt.CursorShape.SizeAllCursor)
            self._tx_timer.start()       # begin rate-limited device writes

    def mouseMoveEvent(self, event) -> None:
        px, py = event.position().x(), event.position().y()
        if self._drag_band is not None:
            i = self._drag_band
            w, h = float(self.width()), float(self.height())
            # Queue the target values; the throttle timer flushes them to the
            # device.  Each axis is independent, so a purely vertical (gain) drag
            # queues no frequency change (and vice versa).
            new_gain = _db_to_raw(_yf(self._drag_node_y + (py - self._drag_mouse_y), h))
            self._queue_param(self._pname(i + 1, 'gain'), new_gain)
            band   = _BANDS[i]
            new_f  = max(band.f_min, min(band.f_max,
                         _xf(self._drag_node_x + (px - self._drag_mouse_x), w)))
            self._queue_param(self._pname(i + 1, 'freq'), _freq_to_raw(new_f, band))
            self.update()                # node follows the mouse every frame
        else:
            prev = self._hover_band
            self._hover_band = self._hit_test(px, py)
            if self._hover_band != prev:
                self.setCursor(
                    Qt.CursorShape.SizeAllCursor
                    if self._hover_band is not None
                    else Qt.CursorShape.CrossCursor
                )
                self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drag_band is not None:
            self._tx_timer.stop()
            self._flush_pending()        # guarantee the final value reaches the device
            self._drag_band = None
            self.setCursor(Qt.CursorShape.CrossCursor)

    # ── throttled device writes ────────────────────────────────────────────────

    def _queue_param(self, name: str, value: int) -> None:
        """Record the latest target for *name*, or drop it if already on-device."""
        if value != self._bridge.get_parameter(name):
            self._pending[name] = value
        else:
            self._pending.pop(name, None)

    def _flush_pending(self) -> None:
        if not self._pending:
            return
        # Snapshot then clear so writes (which emit parameter_changed) don't race.
        pending, self._pending = self._pending, {}
        for name, value in pending.items():
            if value != self._bridge.get_parameter(name):
                self._bridge.set_parameter(name, value)

    def leaveEvent(self, event) -> None:
        if self._hover_band is not None:
            self._hover_band = None
            self.update()

    # ── painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = float(self.width()), float(self.height())
        RGN_H = 22.0   # region label strip height

        # Background
        p.fillRect(self.rect(), _C_BG)

        # Region alternating strips + labels
        fnt_rgn = QFont()
        fnt_rgn.setPixelSize(9)
        fnt_rgn.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.7)
        p.setFont(fnt_rgn)
        for k, (label, f_lo, f_hi) in enumerate(_REGIONS):
            x0 = _fx(f_lo, w)
            x1 = _fx(f_hi, w)
            shade = QColor(24, 24, 28) if k % 2 == 0 else QColor(18, 18, 22)
            p.fillRect(QRectF(x0, 0.0, x1 - x0, h), shade)
            p.setPen(QPen(_C_LABEL))
            p.drawText(
                QRectF(x0 + 4.0, 4.0, x1 - x0 - 8.0, RGN_H),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                label,
            )

        # Horizontal dB grid lines
        p.setPen(QPen(_C_GRID, 0.5))
        for db in (-12, -9, -6, -3, 3, 6, 9, 12):
            y = _fy(float(db), h)
            p.drawLine(QPointF(0.0, y), QPointF(w, y))
        # 0 dB centre line (brighter)
        p.setPen(QPen(_C_ZERO_LINE, 1.0))
        y0 = _fy(0.0, h)
        p.drawLine(QPointF(0.0, y0), QPointF(w, y0))

        # Vertical frequency grid + axis labels
        fnt_ax = QFont()
        fnt_ax.setPixelSize(9)
        p.setFont(fnt_ax)
        p.setPen(QPen(_C_GRID, 0.5))
        for freq in (50, 100, 200, 500, 1000, 2000, 5000, 10000):
            x = _fx(float(freq), w)
            p.drawLine(QPointF(x, RGN_H), QPointF(x, h))

        p.setPen(QPen(_C_LABEL))
        for freq, lbl in ((50,"50"), (100,"100"), (200,"200"),
                          (500,"500"), (1000,"1k"), (2000,"2k"),
                          (5000,"5k"), (10000,"10k")):
            x = _fx(float(freq), w)
            p.drawText(QRectF(x - 16.0, h - 15.0, 32.0, 13.0),
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, lbl)

        # Spectrum analyzer overlay (filled, drawn behind the EQ curve)
        if self._spec_y is not None and len(self._spec_y) > 1:
            n = len(self._spec_y)
            span = h - RGN_H
            top = QPainterPath()
            for i in range(n):
                x = (i + 0.5) / n * w
                y = h - float(self._spec_y[i]) * span
                top.moveTo(QPointF(x, y)) if i == 0 else top.lineTo(QPointF(x, y))
            fill = QPainterPath(top)
            fill.lineTo(QPointF(w, h))
            fill.lineTo(QPointF(0.0, h))
            fill.closeSubpath()
            fc = QColor(_C_SPECTRUM)
            fc.setAlpha(55)
            p.fillPath(fill, fc)
            p.setPen(QPen(_C_SPECTRUM, 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(top)

        # EQ response curve
        if len(self._curve) >= 2:
            path = QPainterPath()
            path.moveTo(QPointF(*self._curve[0]))
            for pt in self._curve[1:]:
                path.lineTo(QPointF(*pt))

            # Subtle fill under the curve
            fill = QPainterPath(path)
            fill.lineTo(QPointF(w, y0))
            fill.lineTo(QPointF(0.0, y0))
            fill.closeSubpath()
            fc = QColor(_C_CURVE)
            fc.setAlpha(28)
            p.fillPath(fill, fc)

            # Curve stroke
            p.setPen(QPen(_C_CURVE, 2.0, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)

        # Band nodes
        for i in range(10):
            nx, ny = self._node_pos(i)
            hot = (i == self._hover_band or i == self._drag_band)
            r = float(_NODE_R)
            if hot:
                glow = QColor(theme.ACCENT)
                glow.setAlpha(70)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(glow)
                p.drawEllipse(QPointF(nx, ny), r + 5.0, r + 5.0)
            p.setPen(QPen(QColor(40, 40, 50), 1.0))
            p.setBrush(_C_NODE_HOV if hot else _C_NODE)
            p.drawEllipse(QPointF(nx, ny), r, r)

        # Drag tooltip
        if self._drag_band is not None:
            self._draw_drag_tooltip(p, w, h, self._drag_band)

        p.end()

    def _draw_drag_tooltip(self, p: QPainter, w: float, h: float, idx: int) -> None:
        band   = _BANDS[idx]
        f_hz   = self._freq_hz(idx)
        db     = self._gain_db(idx)

        freq_str = f"{f_hz/1000:.2f} kHz" if f_hz >= 1000.0 else f"{int(round(f_hz))} Hz"
        db_str   = "0 dB" if db == 0.0 else f"{db:+.0f} dB"
        lines: list[tuple[str, bool]] = [
            (freq_str, False),
            (db_str,   True),   # bold
        ]
        if band.has_q:
            lines.append((f"Q  {self._q_val(idx):.1f}", False))

        PAD   = 8.0
        GAP   = 3.0
        CORNER = 6.0

        fnt_reg = QFont()
        fnt_reg.setPixelSize(11)
        fnt_bold = QFont()
        fnt_bold.setPixelSize(11)
        fnt_bold.setWeight(QFont.Weight.DemiBold)

        p.setFont(fnt_reg)
        fm     = p.fontMetrics()
        lh     = float(fm.height())
        ascent = float(fm.ascent())

        fm_bold = QFontMetrics(fnt_bold)
        box_w = float(max(
            fm_bold.horizontalAdvance(t) if bold else fm.horizontalAdvance(t)
            for t, bold in lines
        )) + PAD * 2.0 + 4.0
        box_h = len(lines) * lh + (len(lines) - 1) * GAP + PAD * 2.0

        # Prefer right of node; flip left if it would overflow
        nx, ny = self._node_pos(idx)
        bx = nx + _NODE_R + 10.0
        if bx + box_w > w - 4.0:
            bx = nx - _NODE_R - 10.0 - box_w
        by = ny - box_h * 0.5
        by = max(4.0, min(by, h - box_h - 4.0))

        # Box background
        box = QRectF(bx, by, box_w, box_h)
        bg  = QColor(theme.SURFACE_3)
        bg.setAlpha(230)
        p.setBrush(bg)
        border = QColor(theme.ACCENT)
        border.setAlpha(120)
        p.setPen(QPen(border, 1.0))
        p.drawRoundedRect(box, CORNER, CORNER)

        # Text lines
        ty = by + PAD + ascent
        for text, bold in lines:
            p.setFont(fnt_bold if bold else fnt_reg)
            color = QColor(theme.ACCENT) if bold else QColor(theme.TEXT)
            p.setPen(QPen(color))
            p.drawText(QPointF(bx + PAD, ty), text)
            ty += lh + GAP


# ── Advanced detail section ────────────────────────────────────────────────────

class _AdvancedSection(QWidget):
    """
    Four-row band detail grid shown when ADVANCED is toggled on:
      Row 0 — frequency labels
      Row 1 — gain dB labels
      Row 2 — Q value labels  (peak bands only; shelf positions are blank)
      Row 3 — Q sliders       (peak bands only)
    """

    def __init__(self, prefix: str, bridge: "BridgeCast") -> None:
        super().__init__()
        self._prefix = prefix
        self._bridge = bridge
        self._block  = False

        self._freq_lbls: list[QLabel]        = []
        self._db_lbls:   list[QLabel]        = []
        self._q_lbls:    list[QLabel | None] = []
        self._q_sls:     list[Slider | None] = []

        vlay = QVBoxLayout(self)
        vlay.setContentsMargins(0, 8, 0, 0)
        vlay.setSpacing(3)

        # Row 0: frequency labels
        freq_row = QHBoxLayout()
        freq_row.setSpacing(2)
        for i in range(10):
            lbl = QLabel(self._fmt_freq(i))
            lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            lbl.setStyleSheet(
                "font-size: 10px; color: #7a7a82; background-color: transparent;"
            )
            freq_row.addWidget(lbl, stretch=1)
            self._freq_lbls.append(lbl)
        vlay.addLayout(freq_row)

        # Row 1: dB value labels
        db_row = QHBoxLayout()
        db_row.setSpacing(2)
        for i in range(10):
            lbl = QLabel(self._fmt_db(i))
            lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            lbl.setStyleSheet(
                "font-size: 11px; font-weight: 600; color: #e8e8ea;"
                " background-color: transparent;"
            )
            db_row.addWidget(lbl, stretch=1)
            self._db_lbls.append(lbl)
        vlay.addLayout(db_row)

        # Row 2: Q value labels
        q_val_row = QHBoxLayout()
        q_val_row.setSpacing(2)
        for i, band in enumerate(_BANDS):
            if band.has_q:
                lbl = QLabel(self._fmt_q(i))
                lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
                lbl.setStyleSheet(
                    "font-size: 10px; color: #7a7a82; background-color: transparent;"
                )
                q_val_row.addWidget(lbl, stretch=1)
                self._q_lbls.append(lbl)
            else:
                placeholder = QLabel()
                placeholder.setStyleSheet("background-color: transparent;")
                q_val_row.addWidget(placeholder, stretch=1)
                self._q_lbls.append(None)
        vlay.addLayout(q_val_row)

        # Row 3: Q sliders
        slider_row = QHBoxLayout()
        slider_row.setSpacing(4)
        for i, band in enumerate(_BANDS):
            if band.has_q:
                sl = Slider(Qt.Orientation.Horizontal)
                sl.setRange(0, 31)
                sl.setValue(bridge.get_parameter(f"{prefix}_band{band.n}_q"))
                sl.valueChanged.connect(
                    lambda v, ii=i, bn=band.n: self._on_q_slider(v, ii, bn)
                )
                slider_row.addWidget(sl, stretch=1)
                self._q_sls.append(sl)
            else:
                ph = QWidget()
                ph.setFixedHeight(18)
                slider_row.addWidget(ph, stretch=1)
                self._q_sls.append(None)
        vlay.addLayout(slider_row)

        bridge.parameter_changed.connect(self._on_param)

    # ── formatting helpers ────────────────────────────────────────────────────

    def _fmt_freq(self, idx: int) -> str:
        f = _raw_to_freq(
            self._bridge.get_parameter(f"{self._prefix}_band{idx+1}_freq"),
            _BANDS[idx],
        )
        return f"{f/1000:.1f}k" if f >= 1000.0 else f"{int(round(f))}Hz"

    def _fmt_db(self, idx: int) -> str:
        db = _raw_to_db(
            self._bridge.get_parameter(f"{self._prefix}_band{idx+1}_gain")
        )
        if db == 0.0:
            return "0 dB"
        return f"{db:+.0f} dB"

    def _fmt_q(self, idx: int) -> str:
        if not _BANDS[idx].has_q:
            return ""
        return f"{_raw_to_q(self._bridge.get_parameter(f'{self._prefix}_band{idx+1}_q')):.1f}"

    # ── signal handlers ───────────────────────────────────────────────────────

    def _on_q_slider(self, v: int, band_idx: int, band_n: int) -> None:
        if self._block:
            return
        self._bridge.set_parameter(f"{self._prefix}_band{band_n}_q", v)
        q_lbl = self._q_lbls[band_idx]
        if q_lbl:
            q_lbl.setText(self._fmt_q(band_idx))

    def _on_param(self, name: str, value: int) -> None:
        pfx = self._prefix + '_band'
        if not name.startswith(pfx):
            return
        # Determine which band changed (fast path: update only that band)
        suffix = name[len(pfx):]          # e.g. "3_gain" or "7_q"
        try:
            band_n = int(suffix.split('_')[0])
            idx = band_n - 1
        except (ValueError, IndexError):
            return

        self._freq_lbls[idx].setText(self._fmt_freq(idx))
        self._db_lbls[idx].setText(self._fmt_db(idx))
        q_lbl = self._q_lbls[idx]
        if q_lbl:
            q_lbl.setText(self._fmt_q(idx))
        q_sl = self._q_sls[idx]
        if q_sl and name.endswith('_q'):
            self._block = True
            q_sl.setValue(value)
            self._block = False


# ── Public EQ widget ──────────────────────────────────────────────────────────

class EqWidget(QWidget):
    """
    Complete EQ section: enable toggle + canvas + ADVANCED toggle + detail rows.

    Parameters
    ----------
    prefix : str
        Parameter name prefix — ``'mic_eq'`` or ``'game_eq'``.
    bridge : BridgeCast
        Device facade.
    title : str
        Section heading shown above the toggle (default ``"EQ"``).
    """

    def __init__(
        self,
        prefix: str,
        bridge: "BridgeCast",
        title: str = "EQ",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._prefix = prefix
        self._bridge = bridge

        vlay = QVBoxLayout(self)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        # Header: title + enable toggle
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 8)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #e8e8ea;"
            " background-color: transparent;"
        )
        hdr.addWidget(title_lbl)
        hdr.addStretch()

        # Live spectrum overlay — Mic EQ only, always-on from the dedicated MIC
        # capture endpoint (started/stopped with panel visibility).  The Game EQ
        # has no analyzer: it would need the SUB MIX (USB) capture, whose channel
        # mapping is unresolved on Linux (see PROTOCOL.md).
        self._analyzer: SpectrumAnalyzer | None = None

        hdr.addWidget(ParamToggle("", f"{prefix}_enable", bridge))
        vlay.addLayout(hdr)

        # EQ canvas
        self._canvas = _EqCanvas(prefix, bridge)
        vlay.addWidget(self._canvas)

        if prefix == "mic_eq":
            self._analyzer = SpectrumAnalyzer(device_hint="mic")
            self._analyzer.spectrum_ready.connect(self._canvas.set_spectrum)
            self._analyzer.error.connect(self._on_analyzer_error)

        # ADVANCED toggle bar
        adv_bar = QHBoxLayout()
        adv_bar.setContentsMargins(0, 8, 0, 0)
        adv_lbl = QLabel("ADVANCED")
        adv_lbl.setStyleSheet(
            "font-size: 10px; font-weight: 600; color: #7a7a82;"
            " letter-spacing: 0.08em; background-color: transparent;"
        )
        adv_bar.addWidget(adv_lbl)
        adv_bar.addStretch()
        self._adv_sw = ToggleSwitch(False)
        self._adv_sw.toggled.connect(self._on_advanced)
        adv_bar.addWidget(self._adv_sw)
        vlay.addLayout(adv_bar)

        # Advanced detail section (hidden by default)
        self._adv = _AdvancedSection(prefix, bridge)
        self._adv.setVisible(False)
        vlay.addWidget(self._adv)

    def _on_advanced(self, checked: bool) -> None:
        self._adv.setVisible(checked)

    # ── Spectrum analyzer (Mic EQ, always-on) ───────────────────────────────────

    def _start_capture(self) -> None:
        if self._analyzer is not None and not self._analyzer.running:
            self._analyzer.start()

    def _stop_capture(self) -> None:
        if self._analyzer is not None:
            self._analyzer.stop()
        self._canvas.clear_spectrum()

    def _on_analyzer_error(self, message: str) -> None:
        # Capture failed (device not found / busy) — leave the overlay clear.
        self._canvas.clear_spectrum()

    def showEvent(self, event) -> None:
        self._start_capture()        # always-on while the panel is visible
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self._stop_capture()
        super().hideEvent(event)
