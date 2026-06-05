"""Geometry tests for FlowLayout: wrapping, and the per-item ``fullWidth`` rule.

Each test builds a layout with zero margins and a known spacing, fills it with
fixed-size boxes, then drives ``setGeometry`` over a fixed-width rect and reads
back where every child landed. Fixed-size widgets give deterministic size hints
(and no height-for-width), so the placement maths are exact.
"""
from __future__ import annotations

from PyQt6.QtCore import QRect, QSize
from PyQt6.QtWidgets import QWidget

from bridgemix.gui.widgets.flow_layout import FlowLayout

_SPACING = 10
_WIDTH = 100          # usable width of the layout rect (margins are zero)
_BOX = QSize(40, 20)  # every box reports the same hint so wrapping is predictable


class _Box(QWidget):
    """Fixed *hint* of 40x20 but no max width, so a full-width item can grow.

    A plain ``setFixedSize`` would cap ``maximumWidth`` and stop the layout from
    stretching a full-width box to the row, defeating the very thing under test.
    """

    def sizeHint(self) -> QSize:  # noqa: D102 - trivial override
        return QSize(_BOX)


def _layout(qapp) -> tuple[FlowLayout, QWidget]:
    host = QWidget()
    layout = FlowLayout(host, spacing=_SPACING)
    layout.setContentsMargins(0, 0, 0, 0)
    return layout, host


def _box(full: bool = False) -> QWidget:
    w = _Box()
    if full:
        w.setProperty("fullWidth", True)
    return w


def _apply(layout: FlowLayout, height: int = 1000) -> None:
    """Run the layout over a fixed-width rect so children get real geometry."""
    layout.setGeometry(QRect(0, 0, _WIDTH, height))


def _rects(widgets: list[QWidget]) -> list[tuple[int, int, int, int]]:
    return [(w.x(), w.y(), w.width(), w.height()) for w in widgets]


def test_empty_layout(qapp):
    layout, _host = _layout(qapp)
    assert layout.count() == 0
    # No items: nothing to lay out, and height-for-width collapses to the margins.
    assert layout.heightForWidth(_WIDTH) == 0
    _apply(layout)  # must not raise on an empty layout


def test_single_item_sits_top_left(qapp):
    layout, _host = _layout(qapp)
    box = _box()
    layout.addWidget(box)
    _apply(layout)
    assert layout.count() == 1
    # Compact item keeps its natural width, anchored at the origin.
    assert _rects([box]) == [(0, 0, 40, 20)]


def test_all_compact_pack_then_wrap(qapp):
    layout, _host = _layout(qapp)
    boxes = [_box() for _ in range(3)]
    for b in boxes:
        layout.addWidget(b)
    _apply(layout)
    # Two boxes fit on row one (40 + 10 + 40 = 90 <= 100); the third wraps.
    assert _rects(boxes) == [
        (0, 0, 40, 20),
        (50, 0, 40, 20),
        (0, 30, 40, 20),
    ]


def test_all_full_width_stack_each_on_its_own_row(qapp):
    layout, _host = _layout(qapp)
    boxes = [_box(full=True) for _ in range(3)]
    for b in boxes:
        layout.addWidget(b)
    _apply(layout)
    # Every full-width item spans the row and drops to the next line.
    assert _rects(boxes) == [
        (0, 0, 100, 20),
        (0, 30, 100, 20),
        (0, 60, 100, 20),
    ]


def test_mixed_full_width_breaks_the_row(qapp):
    layout, _host = _layout(qapp)
    compact_a, full, compact_b = _box(), _box(full=True), _box()
    for b in (compact_a, full, compact_b):
        layout.addWidget(b)
    _apply(layout)
    # The full-width item forces a new row even though the compact one before it
    # left room, and the trailing compact item starts a fresh row below it.
    assert _rects([compact_a, full, compact_b]) == [
        (0, 0, 40, 20),     # compact, top-left
        (0, 30, 100, 20),   # full-width, own row, spans width
        (0, 60, 40, 20),    # compact, below the full-width item
    ]


def test_height_for_width_tracks_row_count(qapp):
    layout, _host = _layout(qapp)
    for _ in range(3):
        layout.addWidget(_box())
    # Three compact boxes wrap to two rows: 20 + 10 + 20 = 50.
    assert layout.heightForWidth(_WIDTH) == 50
