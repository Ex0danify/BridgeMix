"""A wrapping flow layout with per-item full-width support.

Lays children left to right and wraps to a new row when the next item would
overflow, like the canonical Qt FlowLayout. The addition: an item whose widget
carries a truthy ``fullWidth`` Qt property is given the whole row and always sits
on its own line, so a layout can mix compact cards (natural width, packed side by
side) with full-span ones.
"""
from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtWidgets import QLayout, QLayoutItem, QWidget


class FlowLayout(QLayout):
    def __init__(self, parent: QWidget | None = None, spacing: int = 8) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._spacing = spacing

    # ── QLayout plumbing ──────────────────────────────────────────────────────

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    # ── Layout core ─────────────────────────────────────────────────────────────

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        margins = self.contentsMargins()
        area = rect.adjusted(
            margins.left(), margins.top(), -margins.right(), -margins.bottom()
        )
        x, y, line_height = area.x(), area.y(), 0
        gap = self._spacing

        def newline() -> None:
            nonlocal x, y, line_height
            x = area.x()
            y += line_height + gap
            line_height = 0

        for item in self._items:
            widget = item.widget()
            full = bool(widget and widget.property("fullWidth"))
            hint = item.sizeHint()
            item_w = area.width() if full else min(hint.width(), area.width())
            item_h = item.heightForWidth(item_w) if item.hasHeightForWidth() else hint.height()

            # A full-width item, and any item that would overflow, starts a new row.
            if x > area.x() and (full or x + item_w > area.right() + 1):
                newline()

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), QSize(item_w, item_h)))

            line_height = max(line_height, item_h)
            if full:
                newline()
            else:
                x += item_w + gap

        bottom = y + line_height
        return bottom - rect.y() + margins.bottom()
