"""
InputStrip — hardware channel strip card (MIC / AUX / CHAT / GAME).

Layout inside each card:
  ┌──────────────────────────────────────────┐
  │ ● CHANNEL                                │
  │  ┌──────┐  ┌──────┐  ┌────┐             │
  │  │Personal│ │Stream│  │RGB │             │
  │  │ [M]  │  │ [M]  │  │ ↕  │             │
  │  │  │   │  │  │   │  │    │             │
  │  │  ↕   │  │  ↕   │  │    │             │
  │  │  64  │  │  64  │  │    │             │
  │  └──────┘  └──────┘  └────┘             │
  └──────────────────────────────────────────┘
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QRectF, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bridgemix.device import constants as C
from bridgemix.gui.icons import dot_pixmap
from bridgemix.gui.widgets.controls import PeakMeter, ScrollGuardComboBox, Slider as _Slider

if TYPE_CHECKING:
    from bridgemix.device.bridge_cast import BridgeCast

FADER_MIN = 0
FADER_MAX = 0x7F
FADER_DEFAULT = 0x40
METER_MAX = C.METER_FULL_SCALE   # device 0 dBFS reference (not the raw 14-bit ceiling)

# Rainbow slider range: 0 = White, 1-192 = hue spectrum ending at Red
RAINBOW_MAX = 192

# How far to blend accent colors towards white for the pastel look (0 = no blend, 1 = pure white).
_PASTEL_BLEND = 0.52


def _to_pastel(css: str) -> str:
    """Blend a CSS hex color towards white to produce a soft pastel tint."""
    r = int(css[1:3], 16)
    g = int(css[3:5], 16)
    b = int(css[5:7], 16)
    r = round(r + (255 - r) * _PASTEL_BLEND)
    g = round(g + (255 - g) * _PASTEL_BLEND)
    b = round(b + (255 - b) * _PASTEL_BLEND)
    return f"#{r:02x}{g:02x}{b:02x}"

# Key colour stops for the rainbow slider (slider value, (R, G, B) in 0-255 space).
# Defines: 0=White → 32=Orange → 64=Yellow → 96=Green → 128=Blue → 160=Purple → 192=Red
_RAINBOW_VALUE_STOPS: list[tuple[int, tuple[int, int, int]]] = [
    (0,   (255, 255, 255)),  # White
    (32,  (255, 128,   0)),  # Orange
    (64,  (255, 255,   0)),  # Yellow
    (96,  (  0, 255,   0)),  # Green
    (128, (  0,   0, 255)),  # Blue
    (160, (160,   0, 255)),  # Purple
    (192, (255,   0,   0)),  # Red
]

# Override display names for channel keys where uppercase isn't the right label.
_CH_DISPLAY: dict[str, str] = {"sys": "SYSTEM"}

# (display label, STRIP_BUTTON_ACTION_* value) — ordered to match reference UI
_BUTTON_ACTION_ITEMS: list[tuple[str, int]] = [
    ("Channel Mute All",      C.STRIP_BUTTON_ACTION_CHANNEL_MUTE_ALL),
    ("Channel Mute Stream",   C.STRIP_BUTTON_ACTION_CHANNEL_MUTE_STREAM),
    ("Channel Mute Personal", C.STRIP_BUTTON_ACTION_CHANNEL_MUTE_PERS),
    ("SFX A",                 C.STRIP_BUTTON_ACTION_SFX_A),
    ("SFX B",                 C.STRIP_BUTTON_ACTION_SFX_B),
    ("SFX Beep",              C.STRIP_BUTTON_ACTION_SFX_BEEP),
    ("Mute Output All",       C.STRIP_BUTTON_ACTION_MUTE_OUT_ALL),
    ("Mute Output Stream",    C.STRIP_BUTTON_ACTION_MUTE_OUT_STREAM),
    ("Mute Output Line-Out",  C.STRIP_BUTTON_ACTION_MUTE_OUT_LINE),
    ("Mute Output Phones",    C.STRIP_BUTTON_ACTION_MUTE_OUT_PHONES),
    ("Profile 1",             C.STRIP_BUTTON_ACTION_PROFILE_1),
    ("Profile 2",             C.STRIP_BUTTON_ACTION_PROFILE_2),
    ("Profile 3",             C.STRIP_BUTTON_ACTION_PROFILE_3),
    ("Profile 4",             C.STRIP_BUTTON_ACTION_PROFILE_4),
    ("Profile 5",             C.STRIP_BUTTON_ACTION_PROFILE_5),
    ("Game EQ 1",             C.STRIP_BUTTON_ACTION_GAME_EQ_1),
    ("Game EQ 2",             C.STRIP_BUTTON_ACTION_GAME_EQ_2),
    ("Game EQ 3",             C.STRIP_BUTTON_ACTION_GAME_EQ_3),
    ("Game EQ 4",             C.STRIP_BUTTON_ACTION_GAME_EQ_4),
    ("Game EQ 5",             C.STRIP_BUTTON_ACTION_GAME_EQ_5),
    ("Game EQ Off",           C.STRIP_BUTTON_ACTION_GAME_EQ_OFF),
    ("Mic FX 1",              C.STRIP_BUTTON_ACTION_MIC_FX_1),
    ("Mic FX 2",              C.STRIP_BUTTON_ACTION_MIC_FX_2),
    ("Mic FX 3",              C.STRIP_BUTTON_ACTION_MIC_FX_3),
    ("Mic FX 4",              C.STRIP_BUTTON_ACTION_MIC_FX_4),
    ("Mic FX 5",              C.STRIP_BUTTON_ACTION_MIC_FX_5),
    ("MIDI CC 1",             C.STRIP_BUTTON_ACTION_MIDI_CC_1),
    ("MIDI CC 2",             C.STRIP_BUTTON_ACTION_MIDI_CC_2),
    ("MIDI CC 3",             C.STRIP_BUTTON_ACTION_MIDI_CC_3),
    ("MIDI CC 4",             C.STRIP_BUTTON_ACTION_MIDI_CC_4),
    ("BGM SFX A",             C.STRIP_BUTTON_ACTION_BGM_SFX_A),
    ("BGM SFX B",             C.STRIP_BUTTON_ACTION_BGM_SFX_B),
    ("BGM SFX C",             C.STRIP_BUTTON_ACTION_BGM_SFX_C),
    ("BGM SFX D",             C.STRIP_BUTTON_ACTION_BGM_SFX_D),
    ("Hot Key",               C.STRIP_BUTTON_ACTION_HOT_KEY),
    ("Reverb",                C.STRIP_BUTTON_ACTION_REVERB),
    ("BGM Cast Play/Stop",    C.STRIP_BUTTON_ACTION_BGM_CAST_PLAY_STOP),
    ("BGM Cast Next Song",    C.STRIP_BUTTON_ACTION_BGM_CAST_NEXT),
]


class _KnobToggle(QWidget):
    """Thin expanding toggle for PERS ↔ RAW knob-target selection.

    Orange track spanning full widget width, white pill knob slides left/right.
    Unchecked = RAW/Direct (knob left), Checked = PERS/Personal (knob right).
    """

    toggled = pyqtSignal(bool)

    _ACCENT  = QColor(0xe0, 0x5c, 0x12)
    _KNOB_W  = 16
    _H       = 10

    def __init__(self, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checked = bool(checked)
        self.setFixedHeight(self._H)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, v: bool) -> None:
        v = bool(v)
        if self._checked != v:
            self._checked = v
            self.update()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._checked = not self._checked
            self.update()
            self.toggled.emit(self._checked)

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        kw = self._KNOB_W

        # Thin orange track, vertically centred
        t_h = 4
        ty = (H - t_h) / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._ACCENT)
        p.drawRoundedRect(QRectF(0, ty, W, t_h), t_h / 2, t_h / 2)

        # White pill knob
        kx = float(W - kw) if self._checked else 0.0
        p.setBrush(QColor(230, 230, 232))
        p.setPen(QPen(QColor(80, 80, 86), 1))
        p.drawRoundedRect(QRectF(kx, 0, kw, H), H / 2, H / 2)
        p.end()


class _FaderCol(QWidget):
    """Single-bus column: bus label + mute button + fader + value label."""

    value_changed = pyqtSignal(int)
    mute_toggled = pyqtSignal(bool)  # True = muted

    def __init__(self, bus_label: str, has_mute: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._has_mute = has_mute
        self._block = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        hdr = QLabel(bus_label)
        hdr.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        hdr.setStyleSheet("color: #7a7a82; font-size: 10px; font-weight: 600; letter-spacing: 0.05em; background-color: transparent;")
        lay.addWidget(hdr)

        # Always created; hidden when the assigned channel has no mute param.
        self._mute_btn = QPushButton("M")
        self._mute_btn.setObjectName("BusMuteBtn")
        self._mute_btn.setCheckable(True)
        self._mute_btn.setFixedSize(44, 20)
        self._mute_btn.toggled.connect(lambda chk: self.mute_toggled.emit(chk))
        lay.addWidget(self._mute_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        self._mute_btn.setVisible(has_mute)

        self._fader = _Slider(Qt.Orientation.Vertical)
        self._fader.setObjectName("MixerFader")
        self._fader.setRange(FADER_MIN, FADER_MAX)
        self._fader.setValue(FADER_DEFAULT)
        self._fader.setMinimumHeight(132)
        self._fader.setMaximumWidth(22)
        self._fader.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        # L/R peak meters beside the fader
        self._meter_l = PeakMeter(METER_MAX)
        self._meter_r = PeakMeter(METER_MAX)
        for bar in (self._meter_l, self._meter_r):
            bar.setFixedWidth(10)
            bar.setMinimumHeight(132)
            bar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        fader_meter = QHBoxLayout()
        fader_meter.setSpacing(3)
        # Small right margin so the meters sit nearer their fader with a gap
        # before the selection (orange) border, rather than flush against it.
        fader_meter.setContentsMargins(0, 0, 5, 0)
        fader_meter.addWidget(self._fader, alignment=Qt.AlignmentFlag.AlignHCenter)
        meter_row = QHBoxLayout()
        meter_row.setSpacing(1)
        meter_row.setContentsMargins(0, 0, 0, 0)
        meter_row.addWidget(self._meter_l)
        meter_row.addWidget(self._meter_r)
        fader_meter.addLayout(meter_row)
        lay.addLayout(fader_meter)

        self._val_lbl = QLabel(str(FADER_DEFAULT))
        self._val_lbl.setObjectName("FaderValue")
        self._val_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._val_lbl.setFixedWidth(30)
        lay.addWidget(self._val_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._fader.valueChanged.connect(self._on_fader)

    def _on_fader(self, v: int) -> None:
        self._val_lbl.setText(str(v))
        if not self._block:
            self.value_changed.emit(v)

    def set_value(self, v: int) -> None:
        self._block = True
        self._fader.setValue(v)
        self._val_lbl.setText(str(v))
        self._block = False

    def set_muted(self, muted: bool) -> None:
        if self._has_mute:
            self._mute_btn.blockSignals(True)
            self._mute_btn.setChecked(muted)
            self._mute_btn.blockSignals(False)

    def set_fader_color(self, css: str) -> None:
        """Override this fader's accent color (sub-page fill + handle hover)."""
        r, g, b = int(css[1:3], 16), int(css[3:5], 16), int(css[5:7], 16)
        self._fader.setStyleSheet(
            f"QSlider::groove:vertical{{background-color:#1a1a1d;border-radius:4px;width:8px;}}"
            f"QSlider::handle:vertical{{background-color:#e7e7ea;border:1px solid rgba(255,255,255,0.22);border-radius:2px;width:16px;height:10px;margin:0 -7px;}}"
            f"QSlider::handle:vertical:hover{{background-color:{css};border-color:{css};}}"
            f"QSlider::sub-page:vertical{{background-color:#1a1a1d;border-radius:4px;}}"
            f"QSlider::add-page:vertical{{background-color:rgba({r},{g},{b},0.30);border-radius:4px;}}"
        )

    def set_mute_available(self, available: bool) -> None:
        self._has_mute = available
        self._mute_btn.setVisible(available)
        if not available:
            self._mute_btn.blockSignals(True)
            self._mute_btn.setChecked(False)
            self._mute_btn.blockSignals(False)

    def set_meter(self, L: int, R: int) -> None:
        self._meter_l.setValue(L)
        self._meter_r.setValue(R)


class _RainbowSlider(QWidget):
    """
    Vertical LED colour picker.

    Value 0 = White (bottom), 192 = Red (top).
    Gradient bottom → top: White → Orange → Yellow → Green → Blue → Purple → Red
    """

    value_changed = pyqtSignal(int)

    # Gradient stops (paint position 0.0=top → 1.0=bottom, QColor).
    # Top = high value (Red=192), Bottom = low value (White=0).
    _GRADIENT_STOPS = [
        (0.000, QColor(255,   0,   0)),  # Red    (value 192)
        (0.167, QColor(160,   0, 255)),  # Purple (value ~160)
        (0.333, QColor(  0,   0, 255)),  # Blue   (value ~128)
        (0.500, QColor(  0, 255,   0)),  # Green  (value  ~96)
        (0.667, QColor(255, 255,   0)),  # Yellow (value  ~64)
        (0.833, QColor(255, 128,   0)),  # Orange (value  ~32)
        (1.000, QColor(255, 255, 255)),  # White  (value    0)
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = 0
        self._dragging = False
        self.setFixedWidth(22)
        self.setMinimumHeight(132)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def value(self) -> int:
        return self._value

    def setValue(self, v: int) -> None:
        v = max(0, min(RAINBOW_MAX, v))
        if v != self._value:
            self._value = v
            self.update()
            self.value_changed.emit(v)

    def _groove_xywh(self) -> tuple[int, int, int, int]:
        gw = 14
        gx = (self.width() - gw) // 2
        return gx, 6, gw, self.height() - 12

    def _y_to_val(self, y: int) -> int:
        gx, gy, gw, gh = self._groove_xywh()
        frac = max(0.0, min(1.0, (gy + gh - y) / gh))
        return round(frac * RAINBOW_MAX)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self.setValue(self._y_to_val(e.position().toPoint().y()))

    def mouseMoveEvent(self, e) -> None:
        if self._dragging:
            self.setValue(self._y_to_val(e.position().toPoint().y()))

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = False

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        gx, gy, gw, gh = self._groove_xywh()
        groove = QRectF(gx, gy, gw, gh)

        grad = QLinearGradient(0, gy, 0, gy + gh)
        for stop, color in self._GRADIENT_STOPS:
            grad.setColorAt(stop, color)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawRoundedRect(groove, 5, 5)

        # Handle: position maps value→y (0 at bottom, RAINBOW_MAX at top)
        frac = self._value / RAINBOW_MAX
        hy = gy + gh - frac * gh
        hw = gw + 6
        hh = 8
        hx = (self.width() - hw) // 2
        handle = QRectF(hx, hy - hh / 2, hw, hh)
        p.setBrush(QColor(230, 230, 232))
        p.setPen(QPen(QColor(100, 100, 106), 1))
        p.drawRoundedRect(handle, 3, 3)
        p.end()

    @staticmethod
    def to_rgb(value: int) -> tuple[int, int, int]:
        """Map rainbow value 0-192 to (r, g, b) each in 0-32 device range."""
        stops = _RAINBOW_VALUE_STOPS
        if value <= stops[0][0]:
            r, g, b = stops[0][1]
        elif value >= stops[-1][0]:
            r, g, b = stops[-1][1]
        else:
            r, g, b = stops[-1][1]  # fallback; overwritten in loop
            for i in range(len(stops) - 1):
                v0, c0 = stops[i]
                v1, c1 = stops[i + 1]
                if v0 <= value <= v1:
                    t = (value - v0) / (v1 - v0)
                    r = round(c0[0] + t * (c1[0] - c0[0]))
                    g = round(c0[1] + t * (c1[1] - c0[1]))
                    b = round(c0[2] + t * (c1[2] - c0[2]))
                    break
        scale = 32 / 255
        return (round(r * scale), round(g * scale), round(b * scale))



class InputStrip(QFrame):
    """
    Hardware channel strip card. Manages its own bridge connections.

    The strip tracks two separate channel keys:
      _led_ch_key  — physical strip position (mic/aux/chat/game), never changes.
                     Drives the LED RGB slider regardless of channel assignment.
      _ch_key      — currently assigned logical channel; updated by rebind().
    """

    channel_assignment_requested = pyqtSignal(str)  # emits new channel key
    color_changed = pyqtSignal(str)                 # CSS hex — emitted when accent colour changes

    def __init__(
        self,
        ch_key: str,
        label: str,
        color: str,
        bridge: "BridgeCast",
        st_vol_param: str,
        ps_vol_param: str,
        st_mute_param: str | None,
        ps_mute_param: str | None,
        st_meter_key: str,
        ps_meter_key: str,
        all_channels: list[str],
        strip_index: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("InputCard")
        self.setMinimumWidth(180)
        self.setMaximumWidth(230)

        self._bridge = bridge
        self._ch_key = ch_key
        self._led_ch_key = ch_key          # physical strip position; never changes
        self._color = color                # current accent CSS color
        self._strip_index = strip_index
        self._btn_action_param = f"strip{strip_index + 1}_button_action" if strip_index is not None else None
        self._all_channels = all_channels
        self._st_vol = st_vol_param
        self._ps_vol = ps_vol_param
        self._st_mute = st_mute_param
        self._ps_mute = ps_mute_param
        self._st_meter_key = st_meter_key
        self._ps_meter_key = ps_meter_key

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(8)

        # ── Name row ──────────────────────────────────────────────────────────
        name_row = QHBoxLayout()
        name_row.setSpacing(6)

        self._dot_lbl = QLabel()
        self._dot_lbl.setPixmap(dot_pixmap(color, 12))
        self._dot_lbl.setFixedWidth(14)
        name_row.addWidget(self._dot_lbl)

        self._name_lbl = QLabel(label)
        self._name_lbl.setStyleSheet(
            f"color: {color}; font-size: 17px; font-weight: 700; letter-spacing: 0.02em; background-color: transparent;"
        )
        name_row.addWidget(self._name_lbl)
        name_row.addStretch()
        root.addLayout(name_row)

        # ── Faders row ────────────────────────────────────────────────────────
        faders = QHBoxLayout()
        faders.setSpacing(8)

        self._hp_col = _FaderCol("Personal", ps_mute_param is not None)
        self._st_col = _FaderCol("Stream", st_mute_param is not None)
        self._hp_col.set_value(bridge.get_parameter(ps_vol_param))
        self._st_col.set_value(bridge.get_parameter(st_vol_param))
        if ps_mute_param:
            self._hp_col.set_muted(bridge.get_parameter(ps_mute_param) == 0)
        if st_mute_param:
            self._st_col.set_muted(bridge.get_parameter(st_mute_param) == 0)

        self._build_pers_section(faders)
        self._add_stream_to_faders(faders)

        # LED rainbow column — hardware strips only
        self._led: _RainbowSlider | None = None
        if strip_index is not None:
            led_col = QVBoxLayout()
            led_col.setSpacing(4)
            rgb_lbl = QLabel("RGB")
            rgb_lbl.setObjectName("FaderValue")
            rgb_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            led_col.addWidget(rgb_lbl)
            self._led = _RainbowSlider()
            led_col.addWidget(self._led)
            faders.addLayout(led_col)

        root.addLayout(faders)
        self._build_post_faders(root)

        # ── Channel assignment combo — hardware strips only ───────────────────
        self._combo: ScrollGuardComboBox | None = None
        if strip_index is not None:
            self._combo = ScrollGuardComboBox()
            for ch in all_channels:
                self._combo.addItem(_CH_DISPLAY.get(ch, ch.upper()), ch)
            self._combo.setCurrentIndex(all_channels.index(ch_key))
            self._combo.currentIndexChanged.connect(self._on_combo_changed)
            root.addWidget(self._combo)

        # ── Button action combo — hardware strips only ────────────────────────
        self._btn_combo: ScrollGuardComboBox | None = None
        if strip_index is not None:
            btn_lbl = QLabel("Button Action")
            btn_lbl.setObjectName("StripActionLabel")
            root.addWidget(btn_lbl)

            self._btn_combo = ScrollGuardComboBox()
            self._btn_combo.setObjectName("StripActionCombo")
            for item_label, item_value in _BUTTON_ACTION_ITEMS:
                self._btn_combo.addItem(item_label, item_value)
            init_action = bridge.get_parameter(self._btn_action_param)
            self._btn_combo.setCurrentIndex(
                next((i for i, (_, v) in enumerate(_BUTTON_ACTION_ITEMS) if v == init_action), 0)
            )
            self._btn_combo.currentIndexChanged.connect(self._on_btn_action_changed)
            root.addWidget(self._btn_combo)

        # ── Signal wiring ─────────────────────────────────────────────────────
        # Connect unconditionally — handlers already guard against None params.
        self._hp_col.value_changed.connect(self._on_hp_vol)
        self._st_col.value_changed.connect(self._on_st_vol)
        self._hp_col.mute_toggled.connect(self._on_hp_mute)
        self._st_col.mute_toggled.connect(self._on_st_mute)
        bridge.parameter_changed.connect(self._on_param)
        bridge.meter_updated.connect(self._on_meters)

        # LED init — hardware strips only
        self._led_r = self._led_g = self._led_b = 0
        self._led_pending: tuple[int, int, int] | None = None
        self._led_timer: QTimer | None = None
        if strip_index is not None:
            # Debounce: only send LED SysEx 20 ms after the last slider movement.
            # This prevents flooding the device during rapid dragging.
            self._led_timer = QTimer(self)
            self._led_timer.setSingleShot(True)
            self._led_timer.setInterval(20)
            self._led_timer.timeout.connect(self._flush_led)

            self._led.value_changed.connect(self._on_led)
            self._led_r = bridge.get_parameter(f"led_{self._led_ch_key}_r")
            self._led_g = bridge.get_parameter(f"led_{self._led_ch_key}_g")
            self._led_b = bridge.get_parameter(f"led_{self._led_ch_key}_b")
            self._sync_led_slider()

        self._update_selection()

    def _build_pers_section(self, faders: QHBoxLayout) -> None:
        """Wrap the Personal fader in a selectable QFrame and add to faders."""
        self._ps_wrapper = QFrame()
        self._ps_wrapper.setObjectName("PsWrapper")
        self._ps_wrapper.setFrameShape(QFrame.Shape.NoFrame)
        ps_lay = QVBoxLayout(self._ps_wrapper)
        ps_lay.setContentsMargins(2, 2, 2, 2)
        ps_lay.setSpacing(0)
        ps_lay.addWidget(self._hp_col)
        faders.addWidget(self._ps_wrapper)

    def _add_stream_to_faders(self, faders: QHBoxLayout) -> None:
        """Wrap the Stream fader in a selectable QFrame and add to faders."""
        self._st_wrapper = QFrame()
        self._st_wrapper.setObjectName("StWrapper")
        self._st_wrapper.setFrameShape(QFrame.Shape.NoFrame)
        st_lay = QVBoxLayout(self._st_wrapper)
        st_lay.setContentsMargins(2, 2, 2, 2)
        st_lay.setSpacing(0)
        st_lay.addWidget(self._st_col)
        faders.addWidget(self._st_wrapper)

    def _build_post_faders(self, root: QVBoxLayout) -> None:
        """Hook called after the faders row is added to root. Override to inject rows."""

    def _update_selection(self) -> None:
        """Highlight whichever bus group the hardware knobs control.

        Kept deliberately soft — a faint accent tint plus a thin translucent
        border — so the indicator reads on every strip without the page filling
        up with hard orange boxes.  Both states use a 1px border so toggling the
        mix mode never shifts the layout.
        """
        stream_active = self._bridge.get_parameter("mix_mode") == 1
        self._ps_wrapper.setStyleSheet(self._selection_qss("PsWrapper", not stream_active))
        self._st_wrapper.setStyleSheet(self._selection_qss("StWrapper", stream_active))

    @staticmethod
    def _selection_qss(name: str, active: bool) -> str:
        if active:
            return (
                f"QFrame#{name} {{ background: rgba(224,92,18,0.06);"
                f" border: 1px solid rgba(224,92,18,0.38); border-radius: 4px; }}"
            )
        return (
            f"QFrame#{name} {{ background: transparent;"
            f" border: 1px solid transparent; border-radius: 4px; }}"
        )

    # ── User → bridge ──────────────────────────────────────────────────────────

    def _on_hp_vol(self, v: int) -> None:
        self._bridge.set_parameter(self._ps_vol, v)

    def _on_st_vol(self, v: int) -> None:
        self._bridge.set_parameter(self._st_vol, v)

    def _on_hp_mute(self, muted: bool) -> None:
        if self._ps_mute:
            self._bridge.set_parameter(self._ps_mute, 0 if muted else 1)

    def _on_st_mute(self, muted: bool) -> None:
        if self._st_mute:
            self._bridge.set_parameter(self._st_mute, 0 if muted else 1)

    def _on_combo_changed(self, combo_idx: int) -> None:
        if self._combo is None:
            return
        new_ch = self._all_channels[combo_idx]
        if new_ch != self._ch_key:
            self.channel_assignment_requested.emit(new_ch)

    def _on_btn_action_changed(self, combo_idx: int) -> None:
        value = _BUTTON_ACTION_ITEMS[combo_idx][1]
        self._bridge.set_parameter(self._btn_action_param, value)

    def _on_led(self, value: int) -> None:
        if self._led is None or self._led_timer is None:
            return
        # Store the latest RGB and (re)start the debounce timer.
        # The actual SysEx write only happens after 20 ms of no further changes.
        self._led_pending = _RainbowSlider.to_rgb(value)
        self._led_timer.start()

    def _flush_led(self) -> None:
        """Send the pending LED colour to the device (called by debounce timer)."""
        if self._led_pending is None:
            return
        r, g, b = self._led_pending
        self._led_pending = None
        self._bridge.set_parameter(f"led_{self._led_ch_key}_r", r)
        self._bridge.set_parameter(f"led_{self._led_ch_key}_g", g)
        self._bridge.set_parameter(f"led_{self._led_ch_key}_b", b)

    # ── Bridge → UI ───────────────────────────────────────────────────────────

    def _on_param(self, name: str, value: int) -> None:
        if name == self._ps_vol:
            self._hp_col.set_value(value)
        elif name == self._st_vol:
            self._st_col.set_value(value)
        elif name == self._ps_mute:
            self._hp_col.set_muted(value == 0)
        elif name == self._st_mute:
            self._st_col.set_muted(value == 0)
        elif self._btn_action_param and name == self._btn_action_param:
            idx = next((i for i, (_, v) in enumerate(_BUTTON_ACTION_ITEMS) if v == value), -1)
            if idx >= 0 and idx != self._btn_combo.currentIndex():
                self._btn_combo.blockSignals(True)
                self._btn_combo.setCurrentIndex(idx)
                self._btn_combo.blockSignals(False)
        elif self._led is not None and name == f"led_{self._led_ch_key}_r":
            self._led_r = value
            self._sync_led_slider()
        elif self._led is not None and name == f"led_{self._led_ch_key}_g":
            self._led_g = value
            self._sync_led_slider()
        elif self._led is not None and name == f"led_{self._led_ch_key}_b":
            self._led_b = value
            self._sync_led_slider()
        elif name == "mix_mode":
            self._update_selection()

    def _on_meters(self, meters: dict) -> None:
        if self._st_meter_key in meters:
            self._st_col.set_meter(*meters[self._st_meter_key])
        if self._ps_meter_key in meters:
            self._hp_col.set_meter(*meters[self._ps_meter_key])

    def set_color(self, css: str) -> None:
        """Apply a new accent color.

        ``css`` is the full-saturation source color (used for distance calculations
        and emitted via ``color_changed``).  All visual elements receive a pastel
        tint derived from it so the UI stays soft and readable.
        """
        self._color = css
        pastel = _to_pastel(css)
        self._name_lbl.setStyleSheet(
            f"color:{pastel}; font-size:17px; font-weight:700; letter-spacing:0.02em; background-color: transparent;"
        )
        self._dot_lbl.setPixmap(dot_pixmap(pastel, 12))
        self.color_changed.emit(css)  # emit full-saturation for distance maths

    def _apply_led_color(self) -> None:
        """Derive the strip accent color from cached LED RGB (0–32) and apply it."""
        r, g, b = self._led_r, self._led_g, self._led_b
        if r == 0 and g == 0 and b == 0:
            return  # LED off — leave current colour unchanged
        css = f"#{round(r * 255 / 32):02x}{round(g * 255 / 32):02x}{round(b * 255 / 32):02x}"
        self.set_color(css)

    def _sync_led_slider(self) -> None:
        """Convert cached R/G/B device values (0–32) to rainbow slider position and accent colour."""
        if self._led is None:
            return
        r, g, b = self._led_r, self._led_g, self._led_b
        # Find the slider position whose to_rgb() output is closest to the device values.
        best_pos, best_dist = 0, float("inf")
        for pos in range(RAINBOW_MAX + 1):
            tr, tg, tb = _RainbowSlider.to_rgb(pos)
            dist = (tr - r) ** 2 + (tg - g) ** 2 + (tb - b) ** 2
            if dist < best_dist:
                best_dist = dist
                best_pos = pos
        self._led.blockSignals(True)
        self._led.setValue(best_pos)
        self._led.blockSignals(False)
        # Sync strip accent colour to the current LED colour
        self._apply_led_color()

    # ── Channel reassignment ──────────────────────────────────────────────────

    def rebind(
        self,
        ch_key: str,
        label: str,
        color: str,
        st_vol_param: str,
        ps_vol_param: str,
        st_mute_param: str | None,
        ps_mute_param: str | None,
        st_meter_key: str,
        ps_meter_key: str,
    ) -> None:
        """Rebind this strip to a different logical channel (LED slider unaffected)."""
        self._ch_key = ch_key
        self._st_vol = st_vol_param
        self._ps_vol = ps_vol_param
        self._st_mute = st_mute_param
        self._ps_mute = ps_mute_param
        self._st_meter_key = st_meter_key
        self._ps_meter_key = ps_meter_key

        # Update visual identity
        self._dot_lbl.setPixmap(dot_pixmap(color, 12))
        self._name_lbl.setText(label)
        self._name_lbl.setStyleSheet(
            f"color: {color}; font-size: 17px; font-weight: 700; letter-spacing: 0.02em; background-color: transparent;"
        )

        # Update combo silently (hardware strips only)
        if self._combo is not None:
            self._combo.blockSignals(True)
            self._combo.setCurrentIndex(self._all_channels.index(ch_key))
            self._combo.blockSignals(False)

        # Reload fader values from bridge cache
        self._hp_col.set_value(self._bridge.get_parameter(ps_vol_param))
        self._st_col.set_value(self._bridge.get_parameter(st_vol_param))

        # Update mute availability and state
        self._hp_col.set_mute_available(ps_mute_param is not None)
        self._st_col.set_mute_available(st_mute_param is not None)
        if ps_mute_param:
            self._hp_col.set_muted(self._bridge.get_parameter(ps_mute_param) == 0)
        if st_mute_param:
            self._st_col.set_muted(self._bridge.get_parameter(st_mute_param) == 0)

        # Reset meters (will repopulate from next heartbeat)
        self._hp_col.set_meter(0, 0)
        self._st_col.set_meter(0, 0)

        # Re-apply LED colour so a channel rebind never resets back to the
        # hardcoded channel colour for HW strips.
        if self._strip_index is not None:
            self._apply_led_color()


class MicInputStrip(InputStrip):
    """InputStrip with a Direct fader + knob-target toggle for the physical MIC input.

    Use this for all hardware strips. The Direct section shows only when the strip
    is bound to the MIC channel and hides automatically on rebind.
    """

    _MIC_CH = "mic"

    # ── Template method override ───────────────────────────────────────────────

    def _build_pers_section(self, faders: QHBoxLayout) -> None:
        self._raw_col = _FaderCol("Direct", True)

        # QFrame so base-class _update_selection() can apply a stylesheet border.
        # objectName matches the base-class selector "PsWrapper".
        self._mic_grp = QFrame()
        self._mic_grp.setObjectName("PsWrapper")
        self._mic_grp.setFrameShape(QFrame.Shape.NoFrame)

        grp_lay = QHBoxLayout(self._mic_grp)
        grp_lay.setContentsMargins(2, 2, 2, 2)
        grp_lay.setSpacing(8)
        grp_lay.addWidget(self._raw_col)   # Direct on the left
        grp_lay.addWidget(self._hp_col)    # Personal on the right

        # Wire ps_wrapper so the base class knows which frame to highlight
        self._ps_wrapper = self._mic_grp

        faders.addWidget(self._mic_grp)

    def _build_post_faders(self, root: QVBoxLayout) -> None:
        self._knob_toggle = _KnobToggle()
        # Fixed-height container always reserves the same vertical space on every
        # hardware strip so fader heights stay equal across all strips.
        # Width is clamped to _mic_grp.width() in resizeEvent so the toggle never
        # visually extends past the Direct+Personal border box.
        self._toggle_row = QWidget()
        self._toggle_row.setFixedHeight(_KnobToggle._H)
        row_lay = QHBoxLayout(self._toggle_row)
        row_lay.setContentsMargins(0, 0, 0, 0)
        row_lay.setSpacing(0)
        row_lay.addWidget(self._knob_toggle)
        root.addWidget(self._toggle_row)

    # ── Construction ──────────────────────────────────────────────────────────

    def __init__(
        self,
        ch_key: str,
        label: str,
        color: str,
        bridge: "BridgeCast",
        st_vol_param: str,
        ps_vol_param: str,
        st_mute_param: str | None,
        ps_mute_param: str | None,
        st_meter_key: str,
        ps_meter_key: str,
        all_channels: list[str],
        strip_index: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        # _build_pers_section is called inside super().__init__, creating _raw_col etc.
        super().__init__(
            ch_key, label, color, bridge,
            st_vol_param, ps_vol_param, st_mute_param, ps_mute_param,
            st_meter_key, ps_meter_key, all_channels, strip_index, parent,
        )

        # Init Direct fader, mute, and toggle from bridge (self._bridge is now set)
        self._raw_col.set_value(self._bridge.get_parameter("mic_direct_vol"))
        self._raw_col.set_muted(self._bridge.get_parameter("mic_direct_mute") == 0)
        init_tgt = self._bridge.get_parameter("mic_knob_target")
        self._knob_toggle.blockSignals(True)
        self._knob_toggle.setChecked(init_tgt == 1)  # 1=PERS=checked (right)
        self._knob_toggle.blockSignals(False)

        # Direct fader + toggle only visible when this strip is assigned the MIC channel.
        # _mic_grp itself stays visible — it always contains Personal.
        is_mic = (ch_key == self._MIC_CH)
        self._raw_col.setVisible(is_mic)
        self._knob_toggle.setVisible(is_mic)

        self._raw_col.value_changed.connect(self._on_raw_vol)
        self._raw_col.mute_toggled.connect(self._on_raw_mute)
        self._knob_toggle.toggled.connect(self._on_knob_toggle)

    # ── Handlers ──────────────────────────────────────────────────────────────

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self._sync_toggle_width)

    def _sync_toggle_width(self) -> None:
        w = self._mic_grp.width()
        if w > 0:
            self._toggle_row.setMaximumWidth(w)

    def _on_raw_vol(self, v: int) -> None:
        self._bridge.set_parameter("mic_direct_vol", v)

    def _on_raw_mute(self, muted: bool) -> None:
        self._bridge.set_parameter("mic_direct_mute", 0 if muted else 1)

    def _on_knob_toggle(self, checked: bool) -> None:
        # checked=True → PERS (val=1), checked=False → RAW (val=0)
        self._bridge.set_parameter("mic_knob_target", 1 if checked else 0)

    def _on_meters(self, meters: dict) -> None:
        super()._on_meters(meters)
        # Raw/pre-bus mic meter (abs 109–110, confirmed 2026-05-26 rawonly.midilog).
        # slot2() returns a single mono int; expand to (L, R) for set_meter.
        if "raw_mic" in meters:
            v = meters["raw_mic"]
            db = (v / METER_MAX - 1.0) * 90.0
            frac = max(0.0, min(1.0, (db + 60.0) / 60.0))
            direct_vol = self._bridge.get_parameter("mic_direct_vol")
            frac = min(1.0, frac * direct_vol / FADER_DEFAULT)
            self._raw_col.set_meter(int(frac * METER_MAX), int(frac * METER_MAX))

    def _on_param(self, name: str, value: int) -> None:
        super()._on_param(name, value)
        if name == "mic_direct_vol":
            self._raw_col.set_value(value)
        elif name == "mic_direct_mute":
            self._raw_col.set_muted(value == 0)
        elif name == "mic_knob_target":
            self._knob_toggle.blockSignals(True)
            self._knob_toggle.setChecked(value == 1)
            self._knob_toggle.blockSignals(False)

    def set_color(self, css: str) -> None:
        super().set_color(css)

    def rebind(
        self,
        ch_key: str,
        label: str,
        color: str,
        st_vol_param: str,
        ps_vol_param: str,
        st_mute_param: str | None,
        ps_mute_param: str | None,
        st_meter_key: str,
        ps_meter_key: str,
    ) -> None:
        super().rebind(
            ch_key, label, color, st_vol_param, ps_vol_param,
            st_mute_param, ps_mute_param, st_meter_key, ps_meter_key,
        )
        is_mic = (ch_key == self._MIC_CH)
        self._raw_col.setVisible(is_mic)
        self._knob_toggle.setVisible(is_mic)
        QTimer.singleShot(0, self._sync_toggle_width)
        if is_mic:
            self._raw_col.set_value(self._bridge.get_parameter("mic_direct_vol"))
            self._raw_col.set_muted(self._bridge.get_parameter("mic_direct_mute") == 0)
            init_tgt = self._bridge.get_parameter("mic_knob_target")
            self._knob_toggle.blockSignals(True)
            self._knob_toggle.setChecked(init_tgt == 1)
            self._knob_toggle.blockSignals(False)
