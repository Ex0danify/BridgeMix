"""
MIDI Monitor panel — live TX/RX log and raw SysEx sender.

This is the primary debug tool. Shows all frames in both directions with
decoded parameter labels, and lets the user send arbitrary raw SysEx.
"""
from __future__ import annotations

import time
from collections import deque
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from bridgemix.device.parameters import lookup_by_address
from bridgemix.midi.sysex import parse, parse_identity_reply

if TYPE_CHECKING:
    from bridgemix.device.bridge_cast import BridgeCast

MAX_LOG_LINES = 2000

_SEC_NAMES  = {0x01: "STATUS", 0x02: "GLOBAL", 0x03: "CHAN", 0x7F: "VOICEFX"}
_TYPE_NAMES = {0x00: "SW", 0x01: "MIC_FX", 0x02: "VOICE", 0x04: "CHAT_FX",
               0x05: "GAME_FX", 0x06: "DELAY", 0x07: "FADER", 0x08: "LED",
               0x09: "HOTKEY", 0x7F: "VFX_T"}
_CMD_NAMES  = {0x11: "RQ1", 0x12: "DT1"}

# Fallback block labels when no specific parameter matches the address.
# Used for bulk reads/writes whose start address doesn't map to a registered param.
_BLOCK_NAMES: dict[tuple[int, int], str] = {
    (0x02, 0x00): "Global settings",
    (0x02, 0x01): "SFX A",
    (0x02, 0x02): "SFX B",
    (0x03, 0x00): "Channel switches",
    (0x03, 0x01): "Mic Clean Up + EQ",
    (0x03, 0x02): "Voice FX + Reverb",
    (0x03, 0x04): "Chat FX",
    (0x03, 0x05): "Game EQ + FX",
    (0x03, 0x06): "Output delay",
    (0x03, 0x07): "Faders + mutes",
    (0x03, 0x08): "Strip config + LED",
    (0x03, 0x09): "Hot Keys",
    (0x7F, 0x7F): "Voice FX preset",
    (0x01, 0x00): "Firmware echo",
}

_COLOR_TX  = "#60a5fa"   # blue  — host → device
_COLOR_RX  = "#4ade80"   # green — device → host
_COLOR_ERR = "#f87171"   # red   — errors


def _is_heartbeat(data: tuple[int, ...]) -> bool:
    """Return True for routine STATUS-section poll frames that clutter the log.

    Excluded from suppression (always shown):
      - Frames that fail Roland parsing (identity request, unknown)
      - RX enable / disable writes (DT1 to ADDR_STATUS_10 = 0x10)
    """
    frame = parse(data)
    if frame is None:
        return False
    if frame["section"] != 0x01:
        return False
    # RX enable/disable: DT1 write to ADDR_STATUS_10 (addr_hi=0x10)
    if frame["cmd"] == 0x12 and frame["addr_hi"] == 0x10:
        return False
    return True


def _describe(data: tuple[int, ...], direction: str, show_payload: bool = False) -> str:
    ts = time.strftime("%H:%M:%S")

    # Universal MIDI Identity Request — not a Roland frame, handle before parse()
    if data[:4] == (0x7E, 0x7F, 0x06, 0x01):
        return f"[{ts}] {direction} Universal Identity Request"

    # Universal MIDI Identity Reply
    if len(data) >= 13 and data[0] == 0x7E and data[2] == 0x06 and data[3] == 0x02:
        info = parse_identity_reply(data)
        if info:
            fw = ".".join(f"{b:02X}" for b in info["firmware"])
            return (
                f"[{ts}] {direction} Identity Reply"
                f"  mfr=0x{info['manufacturer']:02X}"
                f"  family=0x{info['family']:04X}"
                f"  member=0x{info['member']:04X}"
                f"  fw={fw}"
            )
        return f"[{ts}] {direction} Identity Reply (unparsed)"

    frame = parse(data)
    if frame is None:
        hex_str = " ".join(f"{b:02X}" for b in data[:8])
        return f"[{ts}] {direction} ??? {hex_str}…"

    # Firmware echo: STATUS type=0x00 addr_hi=0x00 — always expand with raw bytes
    if (frame["section"] == 0x01 and frame["type"] == 0x00
            and frame["addr_hi"] == 0x00 and "payload" in frame):
        payload = frame["payload"]
        major = frame["addr_lo"]
        raw = " ".join(f"{b:02X}" for b in payload)
        if len(payload) >= 4:
            minor = payload[0]
            if len(payload) >= 8:
                build, model_code = payload[2], payload[4]
            else:
                build, model_code = (payload[1] << 7) | payload[2], payload[3]
            return (
                f"[{ts}] {direction} Firmware echo"
                f"  v{major}.{minor:02d} build={build}"
                f"  model=0x{model_code:02X}"
                f"  raw=[{raw}]"
            )
        return f"[{ts}] {direction} Firmware echo  addr_lo={major:02X}  raw=[{raw}]"

    cmd = _CMD_NAMES.get(frame["cmd"], f"{frame['cmd']:02X}")
    sec = _SEC_NAMES.get(frame["section"], f"{frame['section']:02X}")
    typ = _TYPE_NAMES.get(frame["type"], f"{frame['type']:02X}")
    hi  = f"{frame['addr_hi']:02X}"
    lo  = f"{frame['addr_lo']:02X}"

    # Exact parameter name, then block-level fallback for bulk start addresses
    name = lookup_by_address(frame["section"], frame["type"], frame["addr_hi"], frame["addr_lo"])
    if name is None:
        name = _BLOCK_NAMES.get((frame["section"], frame["type"]))
    label = f"  [{name}]" if name else ""

    if frame["cmd"] == 0x11:
        # RQ1: indices 13-15 are [0x00, 0x00, size] — show the requested byte count
        req_size = data[15] if len(data) > 15 else 0
        val_str = f"req={req_size}b"
    elif "payload" in frame and len(frame["payload"]) > 1:
        payload = frame["payload"]
        if show_payload:
            val_str = "[" + " ".join(f"{b:02X}" for b in payload) + "]"
        else:
            val_str = f"({len(payload)} bytes)"
    elif "value" in frame:
        val_str = f"val={frame['value']:02X}({frame['value']})"
    else:
        val_str = ""

    return f"[{ts}] {direction} {cmd} sec={sec} type={typ} addr={hi}/{lo} {val_str}{label}"


class MidiMonitor(QWidget):
    def __init__(self, bridge: "BridgeCast", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._pending: deque[str] = deque(maxlen=MAX_LOG_LINES)
        self._paused = False
        self._frame_count = 0
        self._setup_ui()
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(100)
        self._flush_timer.timeout.connect(self._flush)
        self._flush_timer.start()
        bridge.sysex_tx.connect(self._on_tx)
        bridge.sysex_rx.connect(self._on_rx)
        bridge.device_info_updated.connect(self._on_device_info)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── Toolbar ───────────────────────────────────────────────────────────
        toolbar = QHBoxLayout()

        self._btn_pause = QPushButton("Pause")
        self._btn_pause.setCheckable(True)
        self._btn_pause.toggled.connect(self._toggle_pause)
        toolbar.addWidget(self._btn_pause)

        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(self._clear)
        toolbar.addWidget(btn_clear)

        toolbar.addSpacing(12)

        self._hide_hb = QCheckBox("Hide heartbeat")
        self._hide_hb.setChecked(True)
        toolbar.addWidget(self._hide_hb)

        self._show_payload = QCheckBox("Show payload")
        self._show_payload.setChecked(False)
        toolbar.addWidget(self._show_payload)

        toolbar.addStretch()

        self._lbl_count = QLabel("0 frames")
        self._lbl_count.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        toolbar.addWidget(self._lbl_count)

        layout.addLayout(toolbar)

        # ── Log view ──────────────────────────────────────────────────────────
        self._log = QTextEdit()
        self._log.setObjectName("MidiLog")
        self._log.setReadOnly(True)
        self._log.document().setMaximumBlockCount(MAX_LOG_LINES)
        self._log.document().setDefaultStyleSheet("p, body { margin: 0; padding: 0; }")
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._log.setFont(font)
        layout.addWidget(self._log, stretch=1)

        # ── Raw sender ────────────────────────────────────────────────────────
        send_row = QHBoxLayout()
        send_label = QLabel("Raw SysEx (hex, no F0/F7):")
        self._hex_edit = QLineEdit()
        self._hex_edit.setPlaceholderText("41 10 00 00 00 00 11 12 7F …")
        self._hex_edit.returnPressed.connect(self._send_raw)
        btn_send = QPushButton("Send")
        btn_send.setObjectName("btn_primary")
        btn_send.clicked.connect(self._send_raw)
        send_row.addWidget(send_label)
        send_row.addWidget(self._hex_edit, stretch=1)
        send_row.addWidget(btn_send)
        layout.addLayout(send_row)

    # ── Frame callbacks ───────────────────────────────────────────────────────

    def _on_tx(self, data: tuple[int, ...]) -> None:
        if self._hide_hb.isChecked() and _is_heartbeat(data):
            return
        line = _describe(data, "TX→", self._show_payload.isChecked())
        self._pending.append(f'<span style="color:{_COLOR_TX};">{line}</span>')
        self._frame_count += 1

    def _on_rx(self, data: tuple[int, ...]) -> None:
        if self._hide_hb.isChecked() and _is_heartbeat(data):
            return
        line = _describe(data, "←RX", self._show_payload.isChecked())
        self._pending.append(f'<span style="color:{_COLOR_RX};">{line}</span>')
        self._frame_count += 1

    def _on_device_info(self, model: str, firmware: str) -> None:
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] ── Device: {model}  FW: {firmware} ──"
        self._pending.append(f'<span style="color:#fbbf24;">{line}</span>')
        self._frame_count += 1

    # ── Flush to widget ───────────────────────────────────────────────────────

    def _flush(self) -> None:
        if self._paused or not self._pending:
            return
        lines = list(self._pending)
        self._pending.clear()
        for html in lines:
            self._log.append(html)
        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._log.setTextCursor(cursor)
        self._lbl_count.setText(f"{self._frame_count} frames")

    # ── Controls ──────────────────────────────────────────────────────────────

    def _toggle_pause(self, paused: bool) -> None:
        self._paused = paused
        self._btn_pause.setText("Resume" if paused else "Pause")

    def _clear(self) -> None:
        self._log.clear()
        self._frame_count = 0
        self._lbl_count.setText("0 frames")

    def _send_raw(self) -> None:
        text = self._hex_edit.text().strip()
        if not text:
            return
        try:
            data = tuple(int(b, 16) for b in text.split())
        except ValueError:
            self._log.append(f'<span style="color:{_COLOR_ERR};">[ERROR] Invalid hex bytes</span>')
            return
        self._bridge.send_raw_sysex(data)
        self._hex_edit.clear()
