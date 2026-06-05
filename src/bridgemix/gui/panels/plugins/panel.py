"""Plugins panel: the host UI for plugins.

The PluginManager does discovery and lifecycle; this file only renders one card
per plugin (loaded, disabled, awaiting-consent, missing-deps, incompatible or
error) and wires the enable/consent/install actions back to the manager. Every
plugin — built-in or third-party — gets the same card: a header (name, a clickable
version that opens a details popup, a "Built-in" marker, and any primary control
the plugin surfaces) over a body that is either the live plugin widget or a status
message.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bridgemix import theme
from bridgemix.gui.widgets.controls import ToggleSwitch
from bridgemix.gui.widgets.flow_layout import FlowLayout
from bridgemix.plugins import CardWidth
from bridgemix.plugins.installer import DependencyInstaller, can_install
from bridgemix.plugins.manager import PluginManager, PluginRecord, PluginStatus
from bridgemix.paths import plugins_dir

# User-plugin statuses that still show an enable toggle (so it can be turned off).
_USER_TOGGLE_STATES = {
    PluginStatus.LOADED,
    PluginStatus.DISABLED,
    PluginStatus.MISSING_DEPS,
    PluginStatus.CONFLICT,
}


class PluginsPanel(QWidget):
    """Renders the plugin cards and wires enable/consent actions."""

    def __init__(self, manager: PluginManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._manager = manager
        # Keep installers alive while their background pip run is in flight.
        self._installers: dict[str, DependencyInstaller] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        col = QVBoxLayout(content)
        col.setContentsMargins(12, 10, 12, 10)
        col.setSpacing(12)
        scroll.setWidget(content)

        col.addWidget(self._header())

        # Thin rule that visually separates the header from the cards below.
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {theme.SURFACE_4}; border: none;")
        col.addWidget(divider)

        # Cards live in a wrapping flow so compact ones pack side by side while
        # full-width ones span the row (see _make_card / FlowLayout). The host
        # reports height-for-width so the scroll area sizes the column correctly.
        cards_host = QWidget()
        policy = cards_host.sizePolicy()
        policy.setHeightForWidth(True)
        policy.setVerticalPolicy(QSizePolicy.Policy.Minimum)
        cards_host.setSizePolicy(policy)
        self._cards = FlowLayout(cards_host, spacing=12)
        col.addWidget(cards_host)
        col.addStretch()

        self._manager.discover()
        self._rebuild()

    # ── Header ────────────────────────────────────────────────────────────────

    def _header(self) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        title = QLabel("PLUGINS")
        title.setStyleSheet("font-weight: 600; letter-spacing: 0.5px;")
        row.addWidget(title)

        # The folder hint sits inline next to the title — one tidy header row
        # instead of a separate line under it.
        hint = QLabel(f"Drop a plugin folder into  {plugins_dir()}  and Rescan.")
        hint.setStyleSheet(
            f"font-size: 11px; color: {theme.TEXT_MUTED}; background: transparent;"
        )
        row.addWidget(hint)

        row.addStretch()
        open_folder = QPushButton("Open Folder")
        open_folder.setToolTip("Open the plugins folder in your file manager.")
        open_folder.clicked.connect(self._on_open_folder)
        row.addWidget(open_folder)
        rescan = QPushButton("Rescan")
        rescan.setToolTip("Re-scan the plugins folder for newly added plugins.")
        rescan.clicked.connect(self._on_rescan)
        row.addWidget(rescan)
        return box

    # ── Rebuild ───────────────────────────────────────────────────────────────

    def _rebuild(self) -> None:
        """Re-render every card from the manager's current records.

        Live plugin widgets are detached first, so clearing the old chrome doesn't
        destroy a widget the plugin instance still owns; they are re-parented into
        fresh cards below.
        """
        for record in self._manager.records:
            if record.widget is not None:
                record.widget.setParent(None)
                # The plugin's header control lives in the card chrome, not under
                # its widget, so detach it too, or it dies with the old card.
                ctrl = self._plugin_header_widget(record)
                if ctrl is not None:
                    ctrl.setParent(None)

        while self._cards.count():
            item = self._cards.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        records = self._manager.records
        if not records:
            empty = QLabel("No plugins found.")
            empty.setStyleSheet(
                f"color: {theme.TEXT_MUTED}; background: transparent;"
            )
            empty.setProperty("fullWidth", True)
            self._cards.addWidget(empty)
            return

        for record in records:
            self._cards.addWidget(self._make_card(record))

    # ── Card construction ─────────────────────────────────────────────────────

    def _make_card(self, record: PluginRecord) -> QWidget:
        card = QFrame()
        card.setObjectName("pluginCard")
        card.setStyleSheet(
            "#pluginCard {"
            f" background: {theme.SURFACE_2};"
            f" border: 1px solid {theme.SURFACE_4};"
            " border-radius: 8px; }"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(8)

        lay.addLayout(self._card_header(record))

        body = self._card_body(record)
        if body is not None:
            lay.addWidget(body)

        # Compact only applies to a running plugin that asks for it; status cards
        # (consent, errors, missing deps) span the row so their text stays legible.
        card.setProperty("fullWidth", not self._card_is_compact(record))
        return card

    @staticmethod
    def _card_is_compact(record: PluginRecord) -> bool:
        if record.status is not PluginStatus.LOADED or record.widget is None:
            return False
        getter = getattr(record.widget, "card_width", None)
        return callable(getter) and getter() is CardWidth.COMPACT

    def _card_header(self, record: PluginRecord) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        title = QLabel(record.name)
        title.setStyleSheet("font-weight: 600; background: transparent;")
        row.addWidget(title)

        if record.manifest is not None:
            # Clickable version → details popup; carries the description and the
            # rest of the manifest so the card itself stays uncluttered.
            ver = QPushButton(f"v{record.manifest.version}")
            ver.setFlat(True)
            ver.setCursor(Qt.CursorShape.PointingHandCursor)
            ver.setToolTip("Show plugin details")
            ver.setStyleSheet(
                "QPushButton {"
                f" font-size: 11px; color: {theme.TEXT_MUTED};"
                " border: none; background: transparent; padding: 0; text-align: left; }"
                " QPushButton:hover { text-decoration: underline; }"
            )
            ver.clicked.connect(lambda _=False, r=record: self._show_details(r))
            row.addWidget(ver)

        if record.is_builtin:
            badge = QLabel("Built-in")
            badge.setStyleSheet(
                "font-size: 10px; font-weight: 600; letter-spacing: 0.3px;"
                f" color: {theme.TEXT_MUTED}; background: {theme.SURFACE_4};"
                " border-radius: 4px; padding: 1px 6px;"
            )
            row.addWidget(badge)

        row.addStretch()

        # A loaded plugin may surface its primary control (e.g. an on/off toggle)
        # into the header to keep its card compact.
        ctrl = self._plugin_header_widget(record)
        if ctrl is not None:
            row.addWidget(ctrl)

        # An enable toggle, for user plugins past the consent gate — including
        # ones stuck on missing deps or a conflict, so they can be turned back off.
        if record.source == "user" and record.status in _USER_TOGGLE_STATES:
            toggle = ToggleSwitch(record.status is not PluginStatus.DISABLED)
            toggle.toggled.connect(lambda on, r=record: self._on_toggle(r, on))
            row.addWidget(toggle)

        return row

    @staticmethod
    def _plugin_header_widget(record: PluginRecord) -> QWidget | None:
        """The control a loaded plugin wants shown in its card header, if any."""
        widget = record.widget
        if widget is None:
            return None
        getter = getattr(widget, "header_widget", None)
        return getter() if callable(getter) else None

    def _card_body(self, record: PluginRecord) -> QWidget | None:
        manifest = record.manifest

        if record.status is PluginStatus.LOADED:
            return record.widget  # user plugin widget under the header

        if record.status is PluginStatus.NEEDS_CONSENT:
            return self._consent_body(record)

        if record.status is PluginStatus.DISABLED:
            return self._muted("Disabled.")

        if record.status is PluginStatus.MISSING_DEPS:
            return self._deps_body(record)

        if record.status is PluginStatus.CONFLICT:
            return self._error(
                "Dependency conflict — "
                + (record.conflict or "clashes with another enabled plugin")
                + ". Disable one of them to resolve."
            )

        if record.status is PluginStatus.INCOMPATIBLE:
            need = manifest.host_api if manifest else "?"
            return self._muted(
                f"Not compatible with this BridgeMix version "
                f"(needs host API {need})."
            )

        # ERROR
        return self._error(record.error or "Failed to load.")

    def _show_details(self, record: PluginRecord) -> None:
        """Popup with the plugin's manifest metadata, opened from the version."""
        manifest = record.manifest
        if manifest is None:
            return

        rows: list[str] = []
        if manifest.description:
            rows.append(f"<p>{manifest.description}</p>")

        details = [("Source", "Built-in" if record.is_builtin else "Third-party")]
        if manifest.maintainer:
            details.append(("Maintainer", manifest.maintainer))
        if manifest.license:
            details.append(("License", manifest.license))
        if manifest.permissions:
            details.append(("Access", ", ".join(manifest.permissions)))
        details.append(("ID", manifest.id))
        rows.append(
            "<table cellspacing='0' cellpadding='2'>"
            + "".join(
                f"<tr><td style='color:{theme.TEXT_MUTED}'>{key}</td>"
                f"<td>&nbsp;&nbsp;{value}</td></tr>"
                for key, value in details
            )
            + "</table>"
        )
        if manifest.homepage:
            rows.append(f'<p><a href="{manifest.homepage}">{manifest.homepage}</a></p>')

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.NoIcon)
        box.setWindowTitle("Plugin details")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(
            f"<b>{manifest.name}</b> "
            f"<span style='color:{theme.TEXT_MUTED}'>v{manifest.version}</span>"
        )
        box.setInformativeText("".join(rows))
        box.setStandardButtons(QMessageBox.StandardButton.Close)
        box.exec()

    def _consent_body(self, record: PluginRecord) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        warn = QLabel(
            "⚠ This is a third-party plugin. Enabling it runs its code with full "
            "access to your files and network. Only enable plugins you trust."
        )
        warn.setWordWrap(True)
        warn.setStyleSheet(
            f"font-size: 11px; color: {theme.RED}; background: transparent;"
        )
        lay.addWidget(warn)

        btn = QPushButton("Enable…")
        btn.clicked.connect(lambda _=False, r=record: self._on_consent(r))
        lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)
        return box

    def _deps_body(self, record: PluginRecord) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        reqs = " ".join(record.missing_deps)
        lay.addWidget(self._muted(f"Needs: {', '.join(record.missing_deps)}"))

        if can_install():
            btn = QPushButton("Install dependencies")
            btn.clicked.connect(
                lambda _=False, r=record, b=btn: self._on_install(r, b)
            )
            lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)
        else:
            lay.addWidget(self._muted(f"Install them, then Rescan:  pip install {reqs}"))
        return box

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _muted(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"font-size: 12px; color: {theme.TEXT_MUTED}; background: transparent;"
        )
        return lbl

    def _error(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"font-size: 12px; color: {theme.RED}; background: transparent;"
        )
        return lbl

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_open_folder(self) -> None:
        # Create it first so the file manager has something to open — the folder
        # only exists once a plugin has been dropped in otherwise.
        path = plugins_dir()
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _on_rescan(self) -> None:
        self._manager.discover()
        self._rebuild()

    def _on_toggle(self, record: PluginRecord, on: bool) -> None:
        if on:
            self._manager.enable(record)
        else:
            self._manager.disable(record)
        self._rebuild()

    def _on_consent(self, record: PluginRecord) -> None:
        if not self._confirm_consent(record):
            return
        self._manager.grant_consent(record)
        self._rebuild()

    def _on_install(self, record: PluginRecord, btn: QPushButton) -> None:
        btn.setEnabled(False)
        btn.setText("Installing…")
        # Install the union of every active plugin's requires so pip resolves
        # them together rather than clobbering an already-installed version.
        installer = DependencyInstaller(self._manager.dependency_install_set(record), self)
        self._installers[record.id] = installer

        def done(ok: bool, msg: str) -> None:
            self._installers.pop(record.id, None)
            if ok:
                # Deps are importable now — retry the load and re-render.
                self._manager.enable(record)
                self._rebuild()
            else:
                btn.setEnabled(True)
                btn.setText("Install dependencies")
                QMessageBox.warning(self, "Install failed", msg)

        installer.finished.connect(done)
        installer.install()

    def _confirm_consent(self, record: PluginRecord) -> bool:
        manifest = record.manifest
        name = record.name
        perms = ", ".join(manifest.permissions) if manifest and manifest.permissions else "—"
        maintainer = manifest.maintainer if manifest else ""
        homepage = manifest.homepage if manifest else ""

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Enable plugin?")
        box.setText(f"<b>{name}</b>")
        info = (
            f"<p>Maintainer: {maintainer or 'unknown'}</p>"
            f"<p>Declared access: {perms}</p>"
            "<p>This plugin runs with full access to your files and network. "
            "Only enable it if you trust the source.</p>"
        )
        if homepage:
            info += f'<p><a href="{homepage}">{homepage}</a></p>'
        box.setInformativeText(info)
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setStandardButtons(QMessageBox.StandardButton.Cancel)
        enable_btn = box.addButton("Enable", QMessageBox.ButtonRole.AcceptRole)
        box.exec()
        return box.clickedButton() is enable_btn
