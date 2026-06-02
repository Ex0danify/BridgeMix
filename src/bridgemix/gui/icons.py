"""
Icon helpers — tiny QPixmap factories, no external image files.
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap


def chain_pixmap(color: str, size: int = 14) -> QPixmap:
    """Two interlocking oval links (a 'chain' / link glyph) outlined in ``color``.

    Monochrome and theme-tinted on purpose — recolour per state by calling again
    with a different colour (e.g. muted when off, accent when linked).
    """
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(color), max(1.0, size / 9.0)))
    p.setBrush(Qt.BrushStyle.NoBrush)
    ring_w = size * 0.62
    ring_h = size * 0.42
    y = (size - ring_h) / 2.0
    # Two horizontal rings overlapping in the middle → reads as a chain link.
    p.drawEllipse(QRectF(0.0, y, ring_w, ring_h))
    p.drawEllipse(QRectF(size - ring_w, y, ring_w, ring_h))
    p.end()
    return px


def dot_pixmap(color: str, size: int = 10) -> QPixmap:
    """Filled anti-aliased circle in the given hex color."""
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    r = size // 2 - 1
    cx = size // 2
    p.drawEllipse(cx - r, cx - r, r * 2, r * 2)
    p.end()
    return px
