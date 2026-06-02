"""
SurroundCanvas — circular speaker-placement diagram for Virtual Surround.

Draws a ring, a head icon in the centre, and speaker chevrons at the
positions defined by front/surround/back angles.  Updates live as sliders move.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import (
    QColor, QPainter, QPainterPath, QPen, QPolygonF,
)
from PyQt6.QtWidgets import QSizePolicy, QWidget

if TYPE_CHECKING:
    from bridgemix.device.bridge_cast import BridgeCast

_C_RING   = QColor("#2a2a32")
_C_RING_B = QColor("#3a3a44")
_C_SPK    = QColor("#e8e8ea")
_C_HEAD   = QColor("#7a7a82")
_C_LISTEN = QColor("#e05c12")


def _chevron(cx: float, cy: float, angle_deg: float, size: float) -> QPolygonF:
    """Return a filled chevron (speaker symbol) centred at (cx,cy), pointing
    *toward* the origin (inward).  angle_deg is the clockwise angle from 12 o'clock."""
    a = math.radians(angle_deg)
    # Unit vector pointing inward (toward centre).  The speaker is placed at
    # (sin a, -cos a) relative to centre, so the inward direction is the negation
    # of that: (-sin a, +cos a).  (The y sign must match paintEvent's placement,
    # otherwise the chevron is vertically mirrored and appears to spin backwards.)
    ix = -math.sin(a)
    iy =  math.cos(a)
    # perpendicular (90° rotation of the inward vector)
    px =  math.cos(a)
    py =  math.sin(a)

    tip_x = cx + ix * size * 0.55
    tip_y = cy + iy * size * 0.55
    # two wings
    wl_x = cx - ix * size * 0.35 + px * size * 0.55
    wl_y = cy - iy * size * 0.35 + py * size * 0.55
    wr_x = cx - ix * size * 0.35 - px * size * 0.55
    wr_y = cy - iy * size * 0.35 - py * size * 0.55
    # inner notch
    nl_x = cx - ix * size * 0.05 + px * size * 0.25
    nl_y = cy - iy * size * 0.05 + py * size * 0.25
    nr_x = cx - ix * size * 0.05 - px * size * 0.25
    nr_y = cy - iy * size * 0.05 - py * size * 0.25

    return QPolygonF([
        QPointF(tip_x, tip_y),
        QPointF(wl_x, wl_y),
        QPointF(nl_x, nl_y),
        QPointF(nr_x, nr_y),
        QPointF(wr_x, wr_y),
    ])


def _head_path(cx: float, cy: float, r: float) -> QPainterPath:
    """Simple headphone silhouette: circle + two small ear-cups."""
    path = QPainterPath()
    # skull
    path.addEllipse(QPointF(cx, cy), r * 0.55, r * 0.55)
    # left ear cup
    path.addEllipse(QPointF(cx - r * 0.58, cy + r * 0.18), r * 0.22, r * 0.28)
    # right ear cup
    path.addEllipse(QPointF(cx + r * 0.58, cy + r * 0.18), r * 0.22, r * 0.28)
    return path


class SurroundCanvas(QWidget):
    """Read-only circular diagram; call update_angles() to repaint."""

    def __init__(self, bridge: "BridgeCast", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        self._output  = bridge.get_parameter("game_vsurround_output")
        self._front   = bridge.get_parameter("game_vsurround_front_angle")
        self._surr    = bridge.get_parameter("game_vsurround_surround_angle")
        self._back    = bridge.get_parameter("game_vsurround_back_angle")
        self._listen  = bridge.get_parameter("game_vsurround_listen_angle")

        self.setMinimumSize(130, 130)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        bridge.parameter_changed.connect(self._on_param)

    def _on_param(self, name: str, value: int) -> None:
        changed = True
        if name == "game_vsurround_output":
            self._output = value
        elif name == "game_vsurround_front_angle":
            self._front = value
        elif name == "game_vsurround_surround_angle":
            self._surr = value
        elif name == "game_vsurround_back_angle":
            self._back = value
        elif name == "game_vsurround_listen_angle":
            self._listen = value
        else:
            changed = False
        if changed:
            self.update()

    # ── painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        R = min(w, h) / 2 - 6          # outer ring radius
        spk_r = R * 0.88               # distance from centre to speaker icon
        spk_sz = R * 0.22              # chevron half-size

        # ── ring ──────────────────────────────────────────────────────────────
        p.setPen(QPen(_C_RING_B, 2))
        p.setBrush(_C_RING)
        p.drawEllipse(QPointF(cx, cy), R, R)

        # ── listening angle arc (speakers mode only) ──────────────────────────
        if self._output == 1:
            pen = QPen(_C_LISTEN, 1.5, Qt.PenStyle.DotLine)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            la = self._listen
            p.drawArc(
                int(cx - spk_r * 0.55), int(cy - spk_r * 0.55),
                int(spk_r * 1.1), int(spk_r * 1.1),
                int((90 - la) * 16), int(la * 2 * 16),
            )

        # ── head / headphone icon ─────────────────────────────────────────────
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_C_HEAD)
        p.drawPath(_head_path(cx, cy, R * 0.35))

        # ── speaker chevrons ──────────────────────────────────────────────────
        p.setBrush(_C_SPK)
        p.setPen(Qt.PenStyle.NoPen)

        def draw_speaker(angle_deg: float) -> None:
            rad = math.radians(angle_deg)
            sx = cx + spk_r * math.sin(rad)
            sy = cy - spk_r * math.cos(rad)
            p.drawPolygon(_chevron(sx, sy, angle_deg, spk_sz))

        # Always draw all three symmetric pairs regardless of output mode
        for a in ( self._front, -self._front):
            draw_speaker(a)
        for a in ( self._surr,  -self._surr):
            draw_speaker(a)
        for a in ( self._back,  360 - self._back):
            draw_speaker(a)

        p.end()
