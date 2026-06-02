"""
Application routing panel — a collapsible strip on the right edge.

Collapsed it is a thin vertical "APPLICATIONS" bar; expanded it lists every
application currently producing audio with a dropdown to route it onto a Bridge
Cast channel (Chat / Game / Music / System).  Choices are persisted as rules and
re-applied automatically by RoutingMonitor as apps come and go.

The panel is independent of the MIDI connection — audio routing works whether or
not the Bridge Cast is "Connected" for device control.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bridgemix import theme
from bridgemix.gui.widgets.controls import ScrollGuardComboBox
from bridgemix.routing import backend, store

if TYPE_CHECKING:
    from bridgemix.routing.backend import Stream, Target
    from bridgemix.routing.monitor import RoutingMonitor

_PANEL_WIDTH = 268
_NO_TARGET = "Default"   # combo entry (italic): don't route to a Bridge Cast channel
_UNSET = object()        # sentinel: combo not yet built for any sink
_ICON_SIZE = 18
_FALLBACK_ICON = "application-x-executable"


def _parse_desktop_entry(text: str) -> tuple[str | None, str | None]:
    """Return (Icon, StartupWMClass) from a .desktop file's [Desktop Entry] group.

    Only the main group is read — trailing action groups (e.g. "[Desktop Action …]")
    carry their own Name/Icon keys we must not pick up.
    """
    icon = wmclass = None
    in_main = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            in_main = line == "[Desktop Entry]"
        elif in_main and line.startswith("Icon="):
            icon = line[5:].strip()
        elif in_main and line.startswith("StartupWMClass="):
            wmclass = line[15:].strip()
    return icon, wmclass


def _build_icon_index(dirs: list[Path]) -> dict[str, str]:
    """Map lowercased app keys → icon name, from installed .desktop files.

    Each entry is indexed by both its filename stem (e.g. "com.spotify.Client")
    and its StartupWMClass (e.g. "zen"), so a PulseAudio process binary or app id
    can be resolved to the real icon name even when they differ.
    """
    index: dict[str, str] = {}
    for d in dirs:
        for path in d.glob("*.desktop"):
            try:
                icon, wmclass = _parse_desktop_entry(path.read_text(encoding="utf-8"))
            except OSError:
                continue
            if not icon:
                continue
            index.setdefault(path.stem.lower(), icon)
            if wmclass:
                index.setdefault(wmclass.lower(), icon)
    return index


def _desktop_dirs() -> list[Path]:
    """XDG application directories plus Flatpak export dirs, de-duplicated."""
    data_home = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    data_dirs = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    bases = [data_home, *data_dirs.split(":"),
             os.path.expanduser("~/.local/share/flatpak/exports/share"),
             "/var/lib/flatpak/exports/share"]
    out: list[Path] = []
    for base in bases:
        path = Path(base) / "applications"
        if path.is_dir() and path not in out:
            out.append(path)
    return out


_icon_paths_ready = False


def _ensure_icon_search_paths() -> None:
    """Add Flatpak export icon dirs to the theme search path (idempotent).

    Qt derives its search paths from XDG_DATA_DIRS, which already covers the
    system theme dirs on a real desktop session.  Flatpak app icons live under
    its export dirs, which are only searched if Flatpak injected them into
    XDG_DATA_DIRS at login — so we add them explicitly to be safe.
    """
    global _icon_paths_ready
    if _icon_paths_ready:
        return
    _icon_paths_ready = True
    extra = [p for p in (
        os.path.expanduser("~/.local/share/flatpak/exports/share/icons"),
        "/var/lib/flatpak/exports/share/icons",
    ) if os.path.isdir(p)]
    if extra:
        QIcon.setThemeSearchPaths(list(dict.fromkeys(QIcon.themeSearchPaths() + extra)))


_icon_index_cache: dict[str, str] | None = None


def _icon_index() -> dict[str, str]:
    global _icon_index_cache
    if _icon_index_cache is None:
        _icon_index_cache = _build_icon_index(_desktop_dirs())
    return _icon_index_cache


def _app_icon(stream: "Stream") -> QIcon:
    """Best themed icon for a stream.

    Tries, in order: the PulseAudio icon-name hint; the icon mapped from a
    matching .desktop entry (by binary/StartupWMClass or app id); the raw
    binary/app name as an icon-theme key; finally a generic placeholder.
    """
    index = _icon_index()
    candidates = [stream.icon]
    candidates += [index.get(stream.app_key.lower()), index.get(stream.label.lower())]
    candidates += [stream.app_key, stream.app_key.lower(), stream.label.lower()]

    seen: set[str] = set()
    for cand in candidates:
        if cand and cand not in seen:
            seen.add(cand)
            icon = QIcon.fromTheme(cand)
            if not icon.isNull():
                return icon
    return QIcon.fromTheme(_FALLBACK_ICON)


class _StreamRow(QWidget):
    """One application: name + a target dropdown, bound to a routing rule."""

    def __init__(
        self, stream: "Stream", targets: list["Target"], monitor: "RoutingMonitor",
        on_changed: Callable[[], None], parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._stream = stream
        self._targets = targets
        self._monitor = monitor
        self._on_changed = on_changed
        self._block = False
        self._combo_sink: str | None | object = _UNSET   # what the combo was last built for

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self._icon = QLabel()
        self._icon.setFixedSize(_ICON_SIZE, _ICON_SIZE)
        self._icon.setStyleSheet("background: transparent;")
        row.addWidget(self._icon)

        self._name = QLabel(stream.label)
        self._name.setMaximumWidth(118)
        self._name.setStyleSheet("font-size: 12px; color: #e8e8ea; background: transparent;")
        row.addWidget(self._name)
        row.addStretch()

        self._refresh_appearance()

        self._combo = ScrollGuardComboBox()
        self._combo.setFixedWidth(108)
        self._combo.currentIndexChanged.connect(self._on_pick)
        self._populate_combo()
        row.addWidget(self._combo)

    def update_stream(self, stream: "Stream") -> None:
        """Refresh in place (same app, possibly moved/renamed) without a write-back."""
        self._stream = stream
        self._refresh_appearance()
        if stream.sink_name != self._combo_sink:
            self._populate_combo()   # only rebuild when the routed sink changed

    def _refresh_appearance(self) -> None:
        self._icon.setPixmap(_app_icon(self._stream).pixmap(QSize(_ICON_SIZE, _ICON_SIZE)))
        self._name.setText(self._stream.label)
        self._name.setToolTip(self._stream.media or self._stream.label)

    def _populate_combo(self) -> None:
        """Rebuild the dropdown for the stream's current routing state.

        The italic "Default" (unrouted) entry is offered only while the stream is
        not on one of our channels; once it is routed, only the channels appear.
        """
        on_target = any(t.sink_name == self._stream.sink_name for t in self._targets)
        self._block = True
        self._combo.clear()
        if not on_target:
            self._combo.addItem(_NO_TARGET, None)
            italic = QFont(self._combo.font())
            italic.setItalic(True)
            self._combo.setItemData(0, italic, Qt.ItemDataRole.FontRole)   # italic in the list
        for t in self._targets:
            self._combo.addItem(t.label, t.sink_name)
        idx = self._combo.findData(self._stream.sink_name)
        self._combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._combo_sink = self._stream.sink_name
        self._block = False
        self._sync_italic()

    def _sync_italic(self) -> None:
        """Italicise the closed combo when the 'Default' (unrouted) entry is shown."""
        font = self._combo.font()
        font.setItalic(self._combo.currentData() is None)
        self._combo.setFont(font)

    def _on_pick(self, _i: int) -> None:
        if self._block:
            return
        self._sync_italic()
        sink = self._combo.currentData()
        key = self._stream.app_key
        if sink is None:
            store.remove_rule(key)          # stop auto-routing this app
        else:
            store.set_rule(key, sink)
            backend.move(self._stream.index, sink)
            self._monitor.note_manual(self._stream.index)
        self._on_changed()   # ask the panel to regroup this app under its new channel


class _CollapseStrip(QWidget):
    """Thin clickable bar with vertical brand-orange label + state chevrons.

    Reads "❯ App Audio Routing ❯" when collapsed (chevrons point right) and
    "❮ App Audio Routing ❮" when expanded (point left).  The label is painted
    rotated; the chevrons are drawn upright in screen space so they always point
    the intended way regardless of the text rotation.
    """

    clicked = pyqtSignal()

    _WIDTH = 26
    _ARROW_BAND = 20   # px height of a chevron's draw band
    _ARROW_INSET = 14  # gap from each end to the chevron band (pulls them inward)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._expanded = False
        self._hover = False
        self.setFixedWidth(self._WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Show / hide application audio routing")

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self.update()

    def enterEvent(self, _e) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, _e) -> None:
        self._hover = False
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        if self._hover:
            bg = theme.SURFACE_4   # subtle lighter-grey wash across the whole bar
        else:
            bg = theme.SURFACE if self._expanded else theme.SURFACE_2
        p.fillRect(self.rect(), QColor(bg))

        accent = theme.Q_ACCENT_HOVER if self._hover else theme.Q_ACCENT
        chevron = "❮" if self._expanded else "❯"   # left when open, right when collapsed

        # Rotated label, clear of the chevron bands at top/bottom.
        p.save()
        p.translate(w / 2.0, h / 2.0)
        p.rotate(-90)   # reads bottom-to-top
        font = p.font()
        font.setPointSizeF(9.5)
        font.setBold(True)
        p.setFont(font)
        p.setPen(accent)
        band = self._ARROW_BAND
        margin = self._ARROW_INSET + band   # keep the label clear of the inset chevrons
        label_rect = QRectF(-h / 2.0 + margin, -w / 2.0, h - 2 * margin, w)
        p.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, "App Audio Routing")
        p.restore()

        # Upright chevrons at both ends.
        afont = p.font()
        afont.setPointSizeF(11.0)
        afont.setBold(True)
        p.setFont(afont)
        p.setPen(accent)
        inset = self._ARROW_INSET
        p.drawText(QRectF(0, inset, w, band), Qt.AlignmentFlag.AlignCenter, chevron)
        p.drawText(QRectF(0, h - band - inset, w, band), Qt.AlignmentFlag.AlignCenter, chevron)
        p.end()


class RoutingPanel(QWidget):
    expandedChanged = pyqtSignal(bool)   # emitted when the panel opens / closes

    def __init__(self, monitor: "RoutingMonitor", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        _ensure_icon_search_paths()
        self._expanded = False
        self._monitor = monitor
        self._targets: list["Target"] = backend.list_targets()
        self._rows: dict[int, _StreamRow] = {}
        self._headers: list[QWidget] = []
        self._render_sig: tuple | None = None

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._make_strip())
        outer.addWidget(self._make_body())

        # Slide animation: drive the clipper's width 0 ⇄ _PANEL_WIDTH.
        self._anim = QPropertyAnimation(self._body, b"maximumWidth", self)
        self._anim.setDuration(190)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.finished.connect(self._on_anim_finished)

        self._body.setVisible(False)   # start collapsed
        monitor.streams_changed.connect(self._on_streams)

        # Collapse when the user clicks anywhere outside the panel.
        QApplication.instance().installEventFilter(self)

    # ── collapse strip ────────────────────────────────────────────────────────

    def _make_strip(self) -> _CollapseStrip:
        strip = _CollapseStrip()
        strip.clicked.connect(self._toggle)
        self._strip = strip
        return strip

    def _toggle(self) -> None:
        self._set_expanded(not self._expanded)

    def _set_expanded(self, expanded: bool) -> None:
        if expanded == self._expanded:
            return
        self._expanded = expanded
        self._strip.set_expanded(expanded)
        self.expandedChanged.emit(expanded)

        self._anim.stop()
        if expanded:
            if not self._targets:
                self._targets = backend.list_targets()   # device may have appeared
            self._body.setVisible(True)
            self._on_streams(backend.list_streams())     # build rows before sliding in
            self._anim.setStartValue(self._body.maximumWidth())
            self._anim.setEndValue(_PANEL_WIDTH)
        else:
            self._anim.setStartValue(self._body.maximumWidth())
            self._anim.setEndValue(0)
        self._anim.start()

    def _on_anim_finished(self) -> None:
        if not self._expanded:
            self._body.setVisible(False)   # fully collapsed → drop from layout

    def eventFilter(self, obj: object, event: QEvent) -> bool:
        """Collapse the panel on a mouse press outside it (click-away to dismiss).

        Clicks on the panel's own combo-box dropdowns surface as a separate popup
        window, so an active popup is treated as "inside" and never collapses.
        """
        if (
            self._expanded
            and event.type() == QEvent.Type.MouseButtonPress
            and QApplication.activePopupWidget() is None
        ):
            clicked = QApplication.widgetAt(event.globalPosition().toPoint())
            if not self._contains(clicked):
                self._set_expanded(False)
        return super().eventFilter(obj, event)

    def _contains(self, widget: QWidget | None) -> bool:
        """True if widget is the panel or one of its descendants (else outside)."""
        return widget is self or self.isAncestorOf(widget)

    # ── body ──────────────────────────────────────────────────────────────────

    def _make_body(self) -> QWidget:
        # `body` is a fixed-height, width-animated clipper. Its content lives in a
        # fixed-width inner widget so that animating the clipper's width slides the
        # content into / out of view without reflowing any labels or combos.
        body = QFrame()
        body.setMinimumWidth(0)
        body.setMaximumWidth(0)   # start collapsed; width is driven by the animation
        clip = QHBoxLayout(body)
        clip.setContentsMargins(0, 0, 0, 0)
        clip.setSpacing(0)

        content = QFrame()
        content.setObjectName("routing_body")
        content.setFixedWidth(_PANEL_WIDTH)
        content.setStyleSheet(
            "#routing_body { background: #141416; border-left: 1px solid #28282d; }"
        )
        clip.addWidget(content, alignment=Qt.AlignmentFlag.AlignRight)

        lay = QVBoxLayout(content)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        title = QLabel("APPLICATIONS")
        title.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #e8e8ea;"
            " letter-spacing: 0.08em; background: transparent;"
        )
        lay.addWidget(title)

        hint = QLabel("Route each app to a Bridge Cast channel.")
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 10px; color: #7a7a82; background: transparent;")
        lay.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list = QWidget()
        self._list_lay = QVBoxLayout(self._list)
        self._list_lay.setContentsMargins(0, 4, 0, 0)
        self._list_lay.setSpacing(10)
        self._empty = QLabel("Nothing is playing audio.")
        self._empty.setStyleSheet("font-size: 11px; color: #48484f; background: transparent;")
        self._list_lay.addWidget(self._empty)
        self._list_lay.addStretch()
        scroll.setWidget(self._list)
        lay.addWidget(scroll, stretch=1)

        self._body = body
        return body

    # ── stream updates ────────────────────────────────────────────────────────

    def _schedule_refresh(self) -> None:
        """Re-read streams after the current event unwinds (regroups a just-moved app)."""
        QTimer.singleShot(0, lambda: self._on_streams(backend.list_streams()))

    def _group_key(self, stream) -> str | None:
        """The sink_name of the stream's channel, or None for the Default group."""
        for t in self._targets:
            if t.sink_name == stream.sink_name:
                return t.sink_name
        return None

    def _grouped(self, streams: list) -> list[tuple]:
        """Streams bucketed by channel, ordered Default-first then by channel index.

        Returns a list of ``(group_key, [streams])`` for non-empty groups only;
        within each group apps are sorted by name.
        """
        buckets: dict[str | None, list] = {}
        for s in streams:
            buckets.setdefault(self._group_key(s), []).append(s)
        order: list[str | None] = [None, *[t.sink_name for t in self._targets]]
        result = []
        for key in order:
            group = buckets.get(key)
            if group:
                group.sort(key=lambda s: (s.label.lower(), s.index))
                result.append((key, group))
        return result

    def _on_streams(self, streams: list) -> None:
        if not self._expanded:
            return   # don't churn the UI while collapsed; rebuilt when reopened
        if not self._targets:
            self._targets = backend.list_targets()

        grouped = self._grouped(streams)
        sig = tuple((key, tuple(s.index for s in group)) for key, group in grouped)
        if sig == self._render_sig:
            for _key, group in grouped:          # layout unchanged → update in place
                for s in group:
                    self._rows[s.index].update_stream(s)
            return
        self._render_sig = sig
        self._render(grouped, streams)

    def _render(self, grouped: list[tuple], streams: list) -> None:
        present = {s.index for s in streams}
        for idx in list(self._rows):                 # drop rows for gone streams
            if idx not in present:
                self._rows.pop(idx).deleteLater()
        for s in streams:                            # reuse rows; create the new ones
            if s.index in self._rows:
                self._rows[s.index].update_stream(s)
            else:
                self._rows[s.index] = _StreamRow(
                    s, self._targets, self._monitor, self._schedule_refresh
                )

        self._clear_list_layout()
        self._empty.setVisible(not streams)
        if not streams:
            self._list_lay.addWidget(self._empty)
        else:
            for key, group in grouped:
                header = self._make_group_header(key)
                self._headers.append(header)
                self._list_lay.addWidget(header)
                for s in group:
                    self._list_lay.addWidget(self._rows[s.index])
        self._list_lay.addStretch()

    def _clear_list_layout(self) -> None:
        """Detach everything from the list; delete headers, keep reusable rows."""
        while self._list_lay.count():
            widget = self._list_lay.takeAt(0).widget()
            if widget in self._headers:
                widget.deleteLater()
            elif widget is not None:                 # _empty or a reused _StreamRow
                widget.setParent(None)
        self._headers.clear()

    def _make_group_header(self, key: str | None) -> QLabel:
        if key is None:
            label = QLabel("Default")
            style = "font-style: italic;"
        else:
            label = QLabel(next(t.label for t in self._targets if t.sink_name == key).upper())
            style = "letter-spacing: 0.08em;"
        label.setStyleSheet(
            "font-size: 10px; font-weight: 700; color: #7a7a82;"
            " background: transparent; margin-top: 4px;" + style
        )
        return label
