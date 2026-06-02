"""
HomePage — the main mixer view.

Layout:
  ┌───────────────────────────────────────────────────────────────────┐
  │ INPUTS                                            [Mix Link]      │
  │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐             │
  │ │   MIC    │ │   AUX    │ │   CHAT   │ │   GAME   │             │
  │ │ HP ST RGB│ │ HP ST RGB│ │ HP ST RGB│ │ HP ST RGB│             │
  │ └──────────┘ └──────────┘ └──────────┘ └──────────┘             │
  │                                                                   │
  │ ┌── MORE INPUTS ────────────────┐  ┌── OUTPUT ──────────────────┐│
  │ │  MUSIC    SYS      SFX        │  │  Sub-Mix  Stream  Line  HP ││
  │ │  HP ST    HP ST    HP ST      │  │  [ACTIVE] [MUTED] ...      ││
  │ └───────────────────────────────┘  └────────────────────────────┘│
  └───────────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bridgemix.device import constants as C
from bridgemix.gui.icons import chain_pixmap
from bridgemix.gui.widgets.controls import PeakMeter, Slider
from bridgemix.gui.widgets.input_strip import InputStrip, MicInputStrip
from bridgemix.theme import ACCENT, CHANNEL_COLORS, TEXT_MUTED

if TYPE_CHECKING:
    from bridgemix.device.bridge_cast import BridgeCast

METER_MAX = C.METER_FULL_SCALE   # device 0 dBFS reference (not the raw 14-bit ceiling)

# All assignable logical channels (order determines combo display order).
ALL_CHANNELS = ["mic", "aux", "chat", "game", "music", "sys", "sfx"]

# Default physical-strip → channel mapping at startup.
_DEFAULT_HW = ["mic", "aux", "chat", "game"]

# ── Virtual strip colour pool ─────────────────────────────────────────────────
# Colours available for virtual strips (MUSIC/SYS/SFX). At render time the
# algorithm picks the subset that is maximally distant from the current HW
# strip LED colours, preventing visual duplicates.
_VIRTUAL_COLOR_POOL: list[str] = [
    "#e05c12",  # orange
    "#4a9eff",  # blue
    "#a78bfa",  # purple
    "#22c55e",  # green
    "#f59e0b",  # amber
    "#34d399",  # teal
    "#fb7185",  # pink
    "#06b6d4",  # cyan
    "#f43f5e",  # rose
    "#8b5cf6",  # violet
    "#84cc16",  # lime
]


def _css_to_rgb(css: str) -> tuple[int, int, int]:
    h = css.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _color_distance(a: str, b: str) -> float:
    r1, g1, b1 = _css_to_rgb(a)
    r2, g2, b2 = _css_to_rgb(b)
    return math.sqrt((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2)


def _pick_virtual_colors(hw_colors: list[str], n: int) -> list[str]:
    """
    Greedily pick n colors from _VIRTUAL_COLOR_POOL that are maximally
    distant from the given HW strip colors and from each other.
    """
    taken = list(hw_colors)
    assigned: list[str] = []
    for _ in range(n):
        best: str | None = None
        best_dist = -1.0
        for candidate in _VIRTUAL_COLOR_POOL:
            if candidate in taken:
                continue
            dist = min((_color_distance(candidate, t) for t in taken), default=999.0)
            if dist > best_dist:
                best_dist = dist
                best = candidate
        if best is None:
            # Pool exhausted — cycle through
            for c in _VIRTUAL_COLOR_POOL:
                if c not in assigned:
                    best = c
                    break
            else:
                best = _VIRTUAL_COLOR_POOL[len(assigned) % len(_VIRTUAL_COLOR_POOL)]
        assigned.append(best)
        taken.append(best)
    return assigned


# Per-channel parameter names.  st_mk / ps_mk are meter keys for bridge.meter_updated.
_CHANNEL_PARAMS: dict[str, dict] = {
    "mic":   dict(label="MIC",   st_vol="st_mic_vol",   ps_vol="ps_mic_vol",   st_mute="st_mic_mute",   ps_mute="ps_mic_mute",   st_mk="st_mic",   ps_mk="ps_mic"),
    "aux":   dict(label="AUX",   st_vol="st_aux_vol",   ps_vol="ps_aux_vol",   st_mute="st_aux_mute",   ps_mute="ps_aux_mute",   st_mk="st_aux",   ps_mk="ps_aux"),
    "chat":  dict(label="CHAT",  st_vol="st_chat_vol",  ps_vol="ps_chat_vol",  st_mute="st_chat_mute",  ps_mute="ps_chat_mute",  st_mk="st_chat",  ps_mk="ps_chat"),
    "game":  dict(label="GAME",  st_vol="st_game_vol",  ps_vol="ps_game_vol",  st_mute="st_game_mute",  ps_mute="ps_game_mute",  st_mk="st_game",  ps_mk="ps_game"),
    "music": dict(label="MUSIC", st_vol="st_music_vol", ps_vol="ps_music_vol", st_mute="st_music_mute", ps_mute="ps_music_mute", st_mk="st_music", ps_mk="ps_music"),
    "sys":   dict(label="SYSTEM",   st_vol="st_sys_vol",   ps_vol="ps_sys_vol",   st_mute="st_sys_mute",   ps_mute="ps_sys_mute",   st_mk="st_sys",   ps_mk="ps_sys"),
    "sfx":   dict(label="SFX",   st_vol="st_sfx_vol",   ps_vol="ps_sfx_vol",   st_mute=None,            ps_mute=None,            st_mk="ps_sfx",   ps_mk="ps_sfx"),
}


class _OutputStrip(QWidget):
    """Output bus strip: mute toggle + vertical fader + value label + bus name.

    read_only=True  → fader is disabled (hardware knob, display only, blue tint).
    read_only=False → fader is interactive (Sub-Mix; no confirmed write address yet).
    """

    def __init__(
        self,
        label: str,
        mute_param: str,
        vol_param: str | None,
        read_only: bool,
        meter_key: str | None,
        bridge: "BridgeCast",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._mute_param = mute_param
        self._vol_param = vol_param
        self._meter_key = meter_key
        self._block = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)

        # Mute button
        self._mute_btn = QPushButton("ACTIVE")
        self._mute_btn.setObjectName("BusMuteBtn")
        self._mute_btn.setCheckable(True)
        self._mute_btn.setFixedHeight(24)
        self._mute_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._mute_btn.setChecked(bridge.get_parameter(mute_param) == 0)
        self._mute_btn.toggled.connect(self._on_mute)
        self._sync_mute_label()
        lay.addWidget(self._mute_btn)

        # Fader + L/R peak meters side by side
        init_val = bridge.get_parameter(vol_param) if vol_param else 0x40
        self._fader = Slider(Qt.Orientation.Vertical)
        self._fader.setObjectName("OutputFaderRO" if read_only else "OutputFader")
        self._fader.setRange(0, 0x7F)
        self._fader.setValue(init_val)
        self._fader.setMinimumHeight(80)
        self._fader.setFixedWidth(22)
        self._fader.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        if read_only:
            self._fader.setEnabled(False)
        else:
            self._fader.valueChanged.connect(self._on_fader_moved)

        self._meter_l = PeakMeter(METER_MAX)
        self._meter_r = PeakMeter(METER_MAX)
        for bar in (self._meter_l, self._meter_r):
            bar.setFixedWidth(10)
            bar.setMinimumHeight(80)
            bar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        fader_meter = QHBoxLayout()
        fader_meter.setSpacing(3)
        fader_meter.setContentsMargins(0, 0, 0, 0)
        fader_meter.addWidget(self._fader, alignment=Qt.AlignmentFlag.AlignHCenter)
        meter_row = QHBoxLayout()
        meter_row.setSpacing(1)
        meter_row.setContentsMargins(0, 0, 0, 0)
        meter_row.addWidget(self._meter_l)
        meter_row.addWidget(self._meter_r)
        fader_meter.addLayout(meter_row)
        lay.addLayout(fader_meter)

        # Value label
        self._val_lbl = QLabel(str(init_val))
        self._val_lbl.setObjectName("FaderValue")
        self._val_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self._val_lbl)

        # Bus name
        name_lbl = QLabel(label)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        name_lbl.setStyleSheet("font-size: 10px; font-weight: 600; color: #7a7a82;")
        lay.addWidget(name_lbl)

        # Read-only badge — always present so all strips have identical layout height.
        # Non-RO strips get an unstyled empty label as a same-size placeholder.
        ro_lbl = QLabel("Read-only" if read_only else "")
        if read_only:
            ro_lbl.setObjectName("RoBadge")
            ro_lbl.setToolTip("Hardware Fader — volume is controlled by the device")
        ro_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(ro_lbl)

        bridge.parameter_changed.connect(self._on_param)
        bridge.meter_updated.connect(self._on_meters)

    def _on_mute(self, checked: bool) -> None:
        self._sync_mute_label()
        if not self._block:
            self._bridge.set_parameter(self._mute_param, 0 if checked else 1)

    def _sync_mute_label(self) -> None:
        self._mute_btn.setText("MUTED" if self._mute_btn.isChecked() else "ACTIVE")

    def _on_fader_moved(self, v: int) -> None:
        self._val_lbl.setText(str(v))
        if self._vol_param and not self._block:
            self._bridge.set_parameter(self._vol_param, v)

    def _on_meters(self, meters: dict) -> None:
        if self._meter_key and self._meter_key in meters:
            L, R = meters[self._meter_key]
            self._meter_l.setValue(L)
            self._meter_r.setValue(R)

    def _on_param(self, name: str, value: int) -> None:
        self._block = True
        if name == self._mute_param:
            self._mute_btn.setChecked(value == 0)
            self._sync_mute_label()
        elif self._vol_param and name == self._vol_param:
            self._fader.blockSignals(True)
            self._fader.setValue(value)
            self._fader.blockSignals(False)
            self._val_lbl.setText(str(value))
        self._block = False


class HomePage(QWidget):
    """Main mixer page — hardware strips, virtual strips, output section."""

    # (label, mute_param, vol_param, read_only, meter_key)
    _OUTPUTS = [
        ("Sub-Mix", "mute_submix_out", "submix_vol", False, "out_submix"),
        ("Stream",  "mute_stream_out", "stream_vol",  True, "out_stream"),
        ("Line Out","mute_line_out",   "line_out",    True, "out_line"),
        ("Phones",  "mute_phones_out", "phones_vol",  True, "out_phones"),
    ]

    def __init__(self, bridge: "BridgeCast", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        # Current logical channel assigned to each physical strip (index 0–3).
        self._hw_channels: list[str] = list(_DEFAULT_HW)
        # InputStrip widgets in physical order.
        self._hw_strip_widgets: list[InputStrip] = []
        # Current accent CSS color per HW strip index (empty string = not yet known).
        self._hw_strip_colors: list[str] = [""] * 4
        # Virtual strip widgets (rebuilt when HW assignments change).
        self._virtual_strip_widgets: list[InputStrip] = []
        # Inner HBoxLayout of the "MORE INPUTS" card — rebuilt on reassignment.
        self._more_inputs_row: QHBoxLayout | None = None

        # Scroll area wraps all content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("PageContent")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        scroll.setWidget(content)

        lay = QVBoxLayout(content)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(16)

        bridge.hw_strip_assignment_changed.connect(self._on_hw_assignment_from_device)

        lay.addWidget(self._inputs_block(bridge))

        lower = QHBoxLayout()
        lower.setSpacing(10)
        lower.addWidget(self._more_inputs_block(bridge), stretch=3)
        lower.addWidget(self._output_block(bridge), stretch=2)
        lay.addLayout(lower)

        lay.addStretch()

    # ── Section builders ──────────────────────────────────────────────────────

    def _inputs_block(self, bridge: "BridgeCast") -> QFrame:
        card = QFrame()
        card.setObjectName("HomeLowerBlock")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 8, 12, 10)
        lay.setSpacing(8)

        # Title row: Mix-Mode selector (left, primary) + ghost Mix-Link chip (far right)
        header = QHBoxLayout()
        title = QLabel("INPUTS")
        title.setObjectName("PageTitle")
        header.addWidget(title)
        header.addSpacing(16)

        # Mix-mode (Personal / Stream) — selects which bus the hardware knobs
        # control; InputStrip._update_selection() highlights the active column.
        self._mode_personal = QPushButton("Personal")
        self._mode_stream = QPushButton("Stream")
        self._mode_group = QButtonGroup(self)
        for btn, mode_id in ((self._mode_personal, 0), (self._mode_stream, 1)):
            btn.setObjectName("MicTypeBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedWidth(96)
            self._mode_group.addButton(btn, mode_id)
        (self._mode_stream if self._bridge.get_parameter("mix_mode") == 1
         else self._mode_personal).setChecked(True)
        self._mode_group.idToggled.connect(self._on_mix_mode_selected)
        header.addWidget(self._mode_personal)
        header.addWidget(self._mode_stream)

        header.addStretch()

        # Mix Link — independent on/off, so it gets a distinct ghost/outline chip
        # with a chain glyph rather than competing with the segmented selector.
        self._mix_link_btn = QPushButton("  Mix-Link")
        self._mix_link_btn.setObjectName("MixLinkBtn")
        self._mix_link_btn.setCheckable(True)
        self._mix_link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mix_link_btn.setIconSize(QSize(14, 14))
        self._mix_link_btn.setToolTip(
            "Link the Personal and Stream mixes so fader moves apply to both"
        )
        self._mix_link_btn.setChecked(self._bridge.get_parameter("mix_link") == 1)
        self._sync_link_icon()
        self._mix_link_btn.toggled.connect(self._on_mix_link)
        self._bridge.parameter_changed.connect(self._on_param_changed)
        header.addWidget(self._mix_link_btn)
        lay.addLayout(header)

        # Hardware strip row
        row = QHBoxLayout()
        row.setSpacing(10)
        for i, ch_key in enumerate(self._hw_channels):
            p = _CHANNEL_PARAMS[ch_key]
            strip = MicInputStrip(
                ch_key, p["label"], CHANNEL_COLORS[ch_key], bridge,
                p["st_vol"], p["ps_vol"], p["st_mute"], p["ps_mute"],
                p["st_mk"], p["ps_mk"],
                ALL_CHANNELS, i,
            )
            strip.channel_assignment_requested.connect(
                lambda ch, idx=i: self._on_hw_channel_changed(idx, ch)
            )
            strip.color_changed.connect(
                lambda css, idx=i: self._on_hw_strip_color(idx, css)
            )
            self._hw_strip_widgets.append(strip)
            row.addWidget(strip)
        lay.addLayout(row)
        return card

    def _more_inputs_block(self, bridge: "BridgeCast") -> QFrame:
        card = QFrame()
        card.setObjectName("HomeLowerBlock")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 8, 12, 10)
        lay.setSpacing(6)

        title = QLabel("MORE INPUTS")
        title.setObjectName("PageTitle")
        lay.addWidget(title)

        self._more_inputs_row = QHBoxLayout()
        self._more_inputs_row.setSpacing(10)
        lay.addLayout(self._more_inputs_row)

        self._rebuild_virtual_strips()
        return card

    def _rebuild_virtual_strips(self) -> None:
        """Clear and repopulate MORE INPUTS with channels not on hardware strips."""
        if self._more_inputs_row is None:
            return
        while self._more_inputs_row.count():
            item = self._more_inputs_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._virtual_strip_widgets = []
        virtual = [ch for ch in ALL_CHANNELS if ch not in self._hw_channels]
        for ch_key in virtual:
            p = _CHANNEL_PARAMS[ch_key]
            w = self._virtual_strip(
                ch_key, p["label"], CHANNEL_COLORS[ch_key], self._bridge,
                p["st_vol"], p["ps_vol"], p["st_mute"], p["ps_mute"],
                p["st_mk"], p["ps_mk"],
            )
            self._more_inputs_row.addWidget(w, stretch=1)
            self._virtual_strip_widgets.append(w)
        self._reassign_virtual_colors()

    def _output_block(self, bridge: "BridgeCast") -> QFrame:
        card = QFrame()
        card.setObjectName("HomeLowerBlock")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 8, 12, 10)
        lay.setSpacing(6)

        title = QLabel("OUTPUT")
        title.setObjectName("PageTitle")
        lay.addWidget(title)

        strips_row = QHBoxLayout()
        strips_row.setSpacing(20)
        for label, mute_p, vol_p, ro, mk in self._OUTPUTS:
            strips_row.addWidget(_OutputStrip(label, mute_p, vol_p, ro, mk, bridge), stretch=1)
        lay.addLayout(strips_row)
        return card

    def _virtual_strip(
        self,
        ch_key: str, label: str, color: str,
        bridge: "BridgeCast",
        st_v: str, ps_v: str,
        st_m: str | None, ps_m: str | None,
        st_mk: str, ps_mk: str,
    ) -> InputStrip:
        """Virtual channel strip — InputStrip without the LED column (strip_index=None)."""
        return InputStrip(
            ch_key, label, color, bridge,
            st_v, ps_v, st_m, ps_m, st_mk, ps_mk,
            ALL_CHANNELS,
        )

    # ── Hardware strip channel reassignment ───────────────────────────────────

    def _on_hw_channel_changed(self, hw_index: int, new_ch: str) -> None:
        """Handle a channel-assignment combo change on a hardware strip."""
        old_ch = self._hw_channels[hw_index]
        if new_ch == old_ch:
            return

        swap_idx = -1
        for other_idx, other_ch in enumerate(self._hw_channels):
            if other_idx != hw_index and other_ch == new_ch:
                swap_idx = other_idx
                self._hw_channels[other_idx] = old_ch
                p = _CHANNEL_PARAMS[old_ch]
                self._hw_strip_widgets[other_idx].rebind(
                    old_ch, p["label"], CHANNEL_COLORS[old_ch],
                    p["st_vol"], p["ps_vol"], p["st_mute"], p["ps_mute"],
                    p["st_mk"], p["ps_mk"],
                )
                break

        self._hw_channels[hw_index] = new_ch
        p = _CHANNEL_PARAMS[new_ch]
        self._hw_strip_widgets[hw_index].rebind(
            new_ch, p["label"], CHANNEL_COLORS[new_ch],
            p["st_vol"], p["ps_vol"], p["st_mute"], p["ps_mute"],
            p["st_mk"], p["ps_mk"],
        )
        self._rebuild_virtual_strips()

        self._bridge.set_hw_strip_channel(hw_index, new_ch)
        if swap_idx >= 0:
            self._bridge.set_hw_strip_channel(swap_idx, old_ch)

    def _on_hw_assignment_from_device(self, strip_index: int, ch_key: str) -> None:
        """Apply a strip assignment received from the device — no write-back."""
        if self._hw_channels[strip_index] == ch_key:
            return

        old_ch = self._hw_channels[strip_index]
        for other_idx, other_ch in enumerate(self._hw_channels):
            if other_idx != strip_index and other_ch == ch_key:
                self._hw_channels[other_idx] = old_ch
                p = _CHANNEL_PARAMS[old_ch]
                self._hw_strip_widgets[other_idx].rebind(
                    old_ch, p["label"], CHANNEL_COLORS[old_ch],
                    p["st_vol"], p["ps_vol"], p["st_mute"], p["ps_mute"],
                    p["st_mk"], p["ps_mk"],
                )
                break

        self._hw_channels[strip_index] = ch_key
        p = _CHANNEL_PARAMS[ch_key]
        self._hw_strip_widgets[strip_index].rebind(
            ch_key, p["label"], CHANNEL_COLORS[ch_key],
            p["st_vol"], p["ps_vol"], p["st_mute"], p["ps_mute"],
            p["st_mk"], p["ps_mk"],
        )
        self._rebuild_virtual_strips()

    # ── Colour management ─────────────────────────────────────────────────────

    def _on_hw_strip_color(self, strip_idx: int, css: str) -> None:
        """Record an HW strip's new accent color and reassign virtual strip colors."""
        self._hw_strip_colors[strip_idx] = css
        self._reassign_virtual_colors()

    def _reassign_virtual_colors(self) -> None:
        """Pick pool colors for virtual strips that don't clash with HW strip colors."""
        hw = [c for c in self._hw_strip_colors if c]
        colors = _pick_virtual_colors(hw, len(self._virtual_strip_widgets))
        for widget, color in zip(self._virtual_strip_widgets, colors):
            widget.set_color(color)

    # ── Signal handlers ───────────────────────────────────────────────────────

    def _sync_link_icon(self) -> None:
        """Tint the chain glyph: accent when linked, muted when off."""
        color = ACCENT if self._mix_link_btn.isChecked() else TEXT_MUTED
        self._mix_link_btn.setIcon(QIcon(chain_pixmap(color, 14)))

    def _on_mix_link(self, checked: bool) -> None:
        self._sync_link_icon()
        self._bridge.set_parameter("mix_link", 1 if checked else 0)

    def _on_mix_mode_selected(self, mode_id: int, checked: bool) -> None:
        if checked:
            self._bridge.set_parameter("mix_mode", mode_id)

    def _on_param_changed(self, name: str, value: int) -> None:
        if name == "mix_link":
            self._mix_link_btn.blockSignals(True)
            self._mix_link_btn.setChecked(value == 1)
            self._mix_link_btn.blockSignals(False)
            self._sync_link_icon()
        elif name == "mix_mode":
            btn = self._mode_stream if value == 1 else self._mode_personal
            btn.blockSignals(True)
            btn.setChecked(True)
            btn.blockSignals(False)
