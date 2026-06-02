"""
Mic input panel — type selector, preamp gain, and real-time input level display.

Navigation label: MIC
Displays:
  - Segmented MIC TYPE selector (Dynamic / Condenser +48V / Headset)
  - Vertical gain slider with live dB readout
  - Scrolling peak-level waveform driven by the BridgeCast raw-mic MIDI meter
    (METER_IDX_RAW_MIC, abs 109–110 in the 137-byte heartbeat state vector).
    This is the pre-bus, un-bussed mic signal — unaffected by stream or personal
    bus faders/mutes.
"""
from __future__ import annotations

import collections
import json
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bridgemix import theme
from bridgemix.gui.widgets.controls import Slider
from bridgemix.gui.widgets.profile_widget import ProfileWidget

if TYPE_CHECKING:
    from bridgemix.device.bridge_cast import BridgeCast


# ── palette (sourced from theme.py) ───────────────────────────────────────────
_C_BG     = theme.Q_BG           # #0e0e0f
_C_ORANGE = theme.Q_ACCENT        # #e05c12
_C_HOT    = theme.Q_ACCENT_HOVER  # #f0702a
_C_CLIP   = theme.Q_RED           # #f87171
_C_GRID   = QColor(255, 255, 255, 14)   # no named token — semi-transparent white
_C_FAINT  = theme.Q_TEXT_FAINT    # #48484f
_C_PEAK   = QColor(255, 255, 255, 200)  # no named token — near-opaque white

_DB_MARKS        = (0, -15, -30, -45, -60)
_DB_RANGE        = 60.0   # display window: -60 dB … 0 dB
_DEVICE_DB_SCALE = 84.0   # BridgeCast meter scale (empirical: raw=5722→-45 dB idle; raw≈12288→0 dB peak)
_LABEL_W         = 34     # right-side dB-label strip (px)

# Level-zone bands drawn behind the waveform.
# Each entry: (db_top, db_bottom, fill_color, label)
# db_top is the louder boundary (closer to 0 dB = higher on canvas).
_ZONES: list[tuple[float, float, QColor, str]] = [
    (  0.0,  -3.0, QColor(248, 113, 113, 22), "CLIP"),     # red   — will distort
    ( -3.0, -12.0, QColor(245, 158,  11, 14), "HOT"),      # amber — getting loud
    (-12.0, -30.0, QColor( 34, 197,  94, 14), "OPTIMAL"),  # green — sweet spot for voice
    (-30.0, -60.0, QColor(255, 255, 255,  5), "LOW"),      # white — too quiet / noise floor
]


# ── helpers ───────────────────────────────────────────────────────────────────

def _peak_to_db(peak: float) -> float:
    return max(-_DB_RANGE, min(0.0, (peak - 1.0) * _DEVICE_DB_SCALE))


def _db_to_y(db: float, h: int) -> int:
    """Map dB in [-60, 0] → pixel y; 0 dB at top, -60 dB at bottom."""
    t = 1.0 - (db + _DB_RANGE) / _DB_RANGE
    return max(0, min(h - 1, int(t * (h - 1))))


# ── waveform widget ───────────────────────────────────────────────────────────

class MicWaveformWidget(QWidget):
    """
    Scrolling peak-level display driven by BridgeCast raw-mic MIDI meter.

    Feed via push_raw_mic(v) where v is the 14-bit integer from
    METER_IDX_RAW_MIC (0–16383).  Shows 'no signal' until the first value
    arrives (i.e. until the device is connected).
    """

    _MAX_14BIT     = 12288.0   # practical device peak for voice (75% of 14-bit range ≈ 0 dB reference)
    _COLS_PER_TICK = 4      # columns appended per 33 ms tick → ~120 px/s scroll

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(180, 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._pending:  list[float] = []
        self._last_val: float       = 0.0
        self._has_data: bool        = False   # stays False until first push

        self._history:       collections.deque[float] = collections.deque(maxlen=800)
        self._peak_hold:     float = 0.0
        self._peak_hold_ttl: int   = 0
        self._clip_flash:    int   = 0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)   # ~30 fps

    # ── data feed ─────────────────────────────────────────────────────────────

    def push_raw_mic(self, v: int) -> None:
        """Accept a 14-bit raw-mic value (0–16383) from the BridgeCast meter."""
        self._pending.append(v / self._MAX_14BIT)
        self._has_data = True

    # ── display tick ─────────────────────────────────────────────────────────

    def _tick(self) -> None:
        pending, self._pending = self._pending, []

        if pending:
            self._last_val = pending[-1]
            step = max(1, len(pending) // self._COLS_PER_TICK)
            cols = [pending[min(i * step, len(pending) - 1)]
                    for i in range(self._COLS_PER_TICK)]
        else:
            # No new data — sustain last value so the waveform keeps scrolling
            cols = [self._last_val] * self._COLS_PER_TICK

        tick_peak = max(cols)
        for c in cols:
            self._history.append(c)

        if tick_peak >= self._peak_hold:
            self._peak_hold     = tick_peak
            self._peak_hold_ttl = 60
        else:
            self._peak_hold_ttl -= 1
            if self._peak_hold_ttl <= 0:
                self._peak_hold = max(0.0, self._peak_hold - 0.008)

        if tick_peak >= 0.99:
            self._clip_flash = 20
        elif self._clip_flash:
            self._clip_flash -= 1

        self.update()

    # ── sizing ────────────────────────────────────────────────────────────────

    def resizeEvent(self, event) -> None:
        cols = max(1, self.width() - _LABEL_W)
        self._history = collections.deque(self._history, maxlen=cols)
        super().resizeEvent(event)

    # ── painting ─────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        p  = QPainter(self)
        W  = self.width()
        H  = self.height()
        cw = W - _LABEL_W   # canvas width (label strip on the right)

        # Background
        p.fillRect(0, 0, W, H, _C_BG)

        # ── level zone bands (behind everything else) ─────────────────────
        zone_font = QFont(p.font())
        zone_font.setPointSizeF(7.0)
        zone_font.setWeight(QFont.Weight.DemiBold)
        zone_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
        p.setFont(zone_font)
        for db_top, db_bot, fill, label in _ZONES:
            y1 = _db_to_y(db_top, H)
            y2 = _db_to_y(db_bot, H)
            bh = y2 - y1
            if bh <= 0:
                continue
            p.fillRect(0, y1, cw, bh, fill)
            lc = QColor(fill.red(), fill.green(), fill.blue(), 90)
            p.setPen(lc)
            p.drawText(5, y1, cw - 10, bh,
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       label)

        # dB grid lines + right-side axis labels
        axis_font = QFont(p.font())
        axis_font.setPointSizeF(7.0)
        p.setFont(axis_font)
        p.setPen(QPen(_C_GRID, 1))
        for db in _DB_MARKS:
            y = _db_to_y(db, H)
            p.drawLine(0, y, cw - 1, y)
            p.setPen(_C_FAINT)
            p.drawText(cw + 2, y - 7, _LABEL_W - 4, 14,
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       f"{db}dB")
            p.setPen(QPen(_C_GRID, 1))

        # Scrolling peak columns (newest on the right)
        hist = list(self._history)
        n    = len(hist)
        for i, raw_peak in enumerate(hist):
            x = cw - n + i
            if x < 0:
                continue
            db    = _peak_to_db(raw_peak)
            y_top = _db_to_y(db, H)
            bh    = H - y_top
            if bh <= 0:
                continue

            top_col = (
                _C_CLIP   if db >= -3.0  else
                _C_HOT    if db >= -9.0  else
                _C_ORANGE
            )
            grad = QLinearGradient(x, y_top, x, H)
            grad.setColorAt(0.0, top_col)
            grad.setColorAt(1.0, QColor(top_col.red(), top_col.green(), top_col.blue(), 20))
            p.fillRect(x, y_top, 1, bh, grad)

        # Peak hold dash
        if self._peak_hold > 1e-6:
            phy   = _db_to_y(_peak_to_db(self._peak_hold), H)
            color = _C_CLIP if self._clip_flash else _C_PEAK
            p.setPen(QPen(color, 1))
            p.drawLine(0, phy, cw - 1, phy)

        # Clip flash band (top 3 px)
        if self._clip_flash:
            p.fillRect(0, 0, cw, 3, _C_CLIP)

        # No-signal badge (shown until first BridgeCast heartbeat arrives)
        if not self._has_data:
            p.setPen(_C_FAINT)
            p.drawText(0, 0, cw, H, Qt.AlignmentFlag.AlignCenter, "no signal")

        # Canvas border
        p.setPen(QPen(QColor(255, 255, 255, 18), 1))
        p.drawRect(0, 0, cw - 1, H - 1)
        p.end()


# ── mic type definitions ──────────────────────────────────────────────────────
# Each entry: (display label, mic_source value, mic_phantom value)
_MIC_TYPES: list[tuple[str, int, int]] = [
    ("Dynamic",        0, 0),
    ("Condenser +48V", 0, 1),
    ("Headset",        1, 0),
]

# Fixed height shared by both lists in the top row.
_LIST_H = 210


def _type_idx(source: int, phantom: int) -> int:
    if source == 1:
        return 2          # Headset
    return 1 if phantom else 0   # Condenser or Dynamic


# ── main panel ────────────────────────────────────────────────────────────────

class MicSetupPanel(QWidget):
    """INPUT page: mic type, preamp gain, and live input monitor."""

    def __init__(self, bridge: "BridgeCast", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._busy   = False      # re-entrancy guard

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # Top row: mic type selector + profile list side by side, equal height
        top_row = QHBoxLayout()
        top_row.setSpacing(12)
        top_row.addWidget(self._make_type_group(), stretch=1)
        top_row.addWidget(self._make_profile_group(), stretch=1)
        root.addLayout(top_row)

        root.addWidget(self._make_gain_group(), stretch=1)

        bridge.parameter_changed.connect(self._on_param)
        bridge.meter_updated.connect(self._on_meters)
        bridge.profile_names_updated.connect(self._on_profile_names_updated)

    # ── mic type group ────────────────────────────────────────────────────────

    def _make_type_group(self) -> QGroupBox:
        grp = QGroupBox("MIC TYPE")
        lay = QVBoxLayout(grp)
        lay.setContentsMargins(8, 4, 8, 8)
        lay.setSpacing(0)

        self._type_list = QListWidget()
        self._type_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._type_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._type_list.setStyleSheet(
            "QListWidget::item { padding: 3px 10px; font-size: 12px; }"
        )
        self._type_list.setFixedHeight(_LIST_H)

        for i, (label, *_) in enumerate(_MIC_TYPES):
            self._type_list.addItem(QListWidgetItem(f"{i + 1}  {label}"))

        src     = self._bridge.get_parameter("mic_source")
        phantom = self._bridge.get_parameter("mic_phantom")
        self._type_list.setCurrentRow(_type_idx(src, phantom))
        self._type_list.currentRowChanged.connect(self._on_type_selected)

        lay.addWidget(self._type_list)
        return grp

    def _on_type_selected(self, row: int) -> None:
        if row < 0 or self._busy:
            return
        _, src, phantom = _MIC_TYPES[row]
        self._busy = True
        self._bridge.set_parameter("mic_source",  src)
        self._bridge.set_parameter("mic_phantom", phantom)
        # Reload the gain slider for the newly-selected source's gain param
        # (XLR vs headset) — otherwise it keeps showing the previous source's value.
        param = "mic_gain_headset" if src == 1 else "mic_gain_xlr"
        self._gain_slider.setValue(self._bridge.get_parameter(param))
        self._busy = False
        self._refresh_gain_label()

    # ── profile group ─────────────────────────────────────────────────────────

    def _make_profile_group(self) -> ProfileWidget:
        self._profile_widget = ProfileWidget("PROFILE", num_slots=5, parent=self)
        self._profile_widget._list.setFixedHeight(_LIST_H)

        current = self._bridge.get_parameter("active_profile")
        self._profile_widget.set_current_slot(current)

        self._profile_widget.slot_selected.connect(self._on_profile_selected)
        self._profile_widget.params_loaded.connect(self._on_params_loaded)
        self._profile_widget.write_requested.connect(self._on_write_to_bank)
        self._profile_widget.save_requested.connect(self._on_save_to_disk)
        self._profile_widget.revert_requested.connect(self._on_reset_defaults)

        return self._profile_widget

    def _on_profile_selected(self, row: int) -> None:
        if row < 0 or self._busy:
            return
        self._busy = True
        self._bridge.set_parameter("active_profile", row)
        self._busy = False

    def _on_profile_names_updated(self, names: list) -> None:
        self._profile_widget.set_slot_names(names)

    # ── profile button handlers ───────────────────────────────────────────────

    def _on_write_to_bank(self, slot: int, name: str) -> None:
        """Save current device state to the selected slot under the given name."""
        # Sequence confirmed from official app MIDI capture (2026-05-27):
        #   0 ms  — write name to SECTION_CHANNEL (9 pair writes × 5 ms = ~40 ms)
        #  50 ms  — save_profile_to_slot copies CHANNEL state (incl. name) to slot
        # 300 ms  — re-fetch all profile names so the list reflects the new name
        self._bridge.write_profile_name(slot, name)
        QTimer.singleShot(50, lambda s=slot: self._bridge.save_profile_to_slot(s))
        QTimer.singleShot(300, self._bridge.sync_profile_names)

    def _on_save_to_disk(self, slot: int) -> None:
        """Prompt for a name then export the current device state to a file."""
        current_name = self._profile_widget.slot_display_name(slot)
        name, ok = QInputDialog.getText(
            self,
            "Export Profile",
            "Profile name to embed in the file (max 18 characters):",
            text=current_name,
        )
        if not ok:
            return
        name = name.strip()[:18]
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Profile",
            "",
            "BridgeMix Profile (*.brdgcProfile);;JSON (*.json);;All Files (*)",
        )
        if not path:
            return
        data = self._bridge.export_profile(slot)
        data["profile_name"] = name
        try:
            Path(path).write_text(json.dumps(data, indent=4), encoding="utf-8")
            QMessageBox.information(
                self, "Exported",
                f'Profile "{name}" saved to {Path(path).name}',
            )
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))

    def _on_reset_defaults(self, slot: int) -> None:
        """Reset the selected profile slot to factory defaults (confirmed by ProfileWidget)."""
        self._bridge.reset_profile_to_defaults(slot)

    def _on_params_loaded(self, slot: int, params: dict) -> None:
        """Apply parameters parsed from a file to the live device state."""
        applied = self._bridge.import_profile({"parameters": params})
        if applied:
            QMessageBox.information(
                self, "Loaded",
                f"Applied {applied} parameters to the current device state.\n\n"
                'Use "Write" to save these settings to a profile slot.',
            )
        else:
            QMessageBox.warning(
                self, "Nothing Loaded",
                "No recognised parameters found in the file.",
            )

    # ── gain + waveform group ─────────────────────────────────────────────────

    def _make_gain_group(self) -> QGroupBox:
        grp = QGroupBox("GAIN")
        lay = QHBoxLayout(grp)
        lay.setContentsMargins(12, 16, 12, 12)
        lay.setSpacing(14)

        # Left column: dB value + vertical slider
        col = QWidget()
        col.setFixedWidth(68)
        cv = QVBoxLayout(col)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(6)

        self._gain_lbl = QLabel("0 dB")
        self._gain_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._gain_lbl.setStyleSheet(
            "color: #e05c12; font-size: 13px; font-weight: 700;"
            "font-family: 'Consolas', monospace; background: transparent;"
        )
        cv.addWidget(self._gain_lbl)

        self._gain_slider = Slider(Qt.Orientation.Vertical)
        self._gain_slider.setRange(0, 25)

        src   = self._bridge.get_parameter("mic_source")
        param = "mic_gain_headset" if src == 1 else "mic_gain_xlr"
        self._gain_slider.setValue(self._bridge.get_parameter(param))
        self._gain_slider.valueChanged.connect(self._on_gain_moved)

        cv.addWidget(
            self._gain_slider, stretch=1,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        lay.addWidget(col)

        # Right: waveform canvas
        self._wave = MicWaveformWidget()
        lay.addWidget(self._wave, stretch=1)

        self._refresh_gain_label()
        return grp

    def _on_gain_moved(self, val: int) -> None:
        if self._busy:
            return
        src   = self._bridge.get_parameter("mic_source")
        param = "mic_gain_headset" if src == 1 else "mic_gain_xlr"
        self._busy = True
        self._bridge.set_parameter(param, val)
        self._busy = False
        self._refresh_gain_label()

    def _refresh_gain_label(self) -> None:
        val = self._gain_slider.value()
        src = self._bridge.get_parameter("mic_source")
        # XLR (Dynamic / Condenser): 0–25 steps → 0–75 dB (3 dB / step)
        # Headset:                    0–25 steps → 0–38 dB (~1.52 dB / step)
        db = val * 1.52 if src == 1 else val * 3.0
        self._gain_lbl.setText(f"{db:.0f} dB")

    # ── bridge feedback ───────────────────────────────────────────────────────

    def _on_meters(self, meters: dict) -> None:
        if "raw_mic" in meters:
            self._wave.push_raw_mic(meters["raw_mic"])

    def _on_param(self, name: str, value: int) -> None:
        if self._busy:
            return
        self._busy = True

        if name in ("mic_source", "mic_phantom"):
            src     = self._bridge.get_parameter("mic_source")
            phantom = self._bridge.get_parameter("mic_phantom")
            self._type_list.setCurrentRow(_type_idx(src, phantom))
            param = "mic_gain_headset" if src == 1 else "mic_gain_xlr"
            self._gain_slider.setValue(self._bridge.get_parameter(param))
            self._refresh_gain_label()

        elif name == "mic_gain_xlr":
            if self._bridge.get_parameter("mic_source") == 0:
                self._gain_slider.setValue(value)
                self._refresh_gain_label()

        elif name == "mic_gain_headset":
            if self._bridge.get_parameter("mic_source") == 1:
                self._gain_slider.setValue(value)
                self._refresh_gain_label()

        elif name == "active_profile":
            self._profile_widget.set_current_slot(value)

        self._busy = False
