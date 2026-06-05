"""Control widget for the Remote API plugin: enable/stop the server and set the port.

Subclasses the SDK's `PluginWidget`, so state (enabled, port) is read from and
written to `self.settings` (the per-plugin store) and the widget never touches
disk itself. Dependency handling lives in the host, so by the time this widget is
built the server's deps are present and it only deals with server state.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QTimer, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QWidget,
)

from bridgemix.plugins import CardWidth, PluginWidget, style
from bridgemix.plugins.builtins.remote_api.server import ApiServer
from bridgemix.plugins.builtins.remote_api.settings import ApiSettings, DEFAULT_HOST, from_store

if TYPE_CHECKING:
    from bridgemix.plugins import PluginContext

# Status-bubble states
_API_STATE_RUNNING = (style.GREEN, "Running")
_API_STATE_STARTING = (style.ACCENT, "Starting…")
_API_STATE_STOPPED = (style.RED, "Stopped")


class RemoteApiWidget(PluginWidget):
    """Enable/configure the REST API server."""

    def __init__(
        self,
        ctx: "PluginContext",
        api_server: ApiServer,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(ctx, parent)
        self._api_server = api_server

        # Coalesce rapid port-spinbox changes into a single save / restart.
        self._port_debounce = QTimer(self)
        self._port_debounce.setSingleShot(True)
        self._port_debounce.setInterval(500)
        self._port_debounce.timeout.connect(self._apply_port_change)

        self._build_controls()

    def header_widget(self) -> QWidget:
        # The enable toggle is the plugin's primary control, so the host shows it
        # in the card header rather than the body (see PluginWidget.header_widget).
        return self._api_toggle

    def card_width(self) -> CardWidth:
        # Few controls — don't stretch across the whole panel.
        return CardWidth.COMPACT

    def _build_controls(self) -> None:
        # The host card supplies the title, the enable toggle (header_widget) and a
        # details popup, so the body is just the few remaining controls.
        lay = self.body
        lay.setSpacing(6)
        settings = from_store(self.settings)

        self._api_toggle = style.ToggleSwitch(settings.enabled and self._api_server.is_running)
        self._api_toggle.toggled.connect(self._on_api_enable_toggled)

        # Row — Port (left) + status bubble (right).
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        status_row.addWidget(QLabel("Port:"))
        self._api_port = QSpinBox()
        self._api_port.setRange(1024, 65535)
        self._api_port.setValue(settings.port)
        self._api_port.valueChanged.connect(self._on_api_port_changed)
        status_row.addWidget(self._api_port)
        status_row.addStretch()
        self._api_bubble = QLabel("●")
        self._api_state_lbl = QLabel()
        self._api_state_lbl.setStyleSheet(
            "font-size: 12px; color: #c8c8d0; background-color: transparent;"
        )
        status_row.addWidget(self._api_bubble)
        status_row.addWidget(self._api_state_lbl)
        lay.addLayout(status_row)

        # Detail line — only shown for a genuine start failure.
        self._api_status = QLabel()
        self._api_status.setWordWrap(True)
        self._api_status.setStyleSheet(
            "font-size: 12px; color: #9a9aa2; background-color: transparent;"
        )
        lay.addWidget(self._api_status)

        self._api_docs_btn = QPushButton("Open API Docs")
        self._api_docs_btn.clicked.connect(self._open_api_docs)
        lay.addWidget(self._api_docs_btn)

        self._api_server.state_changed.connect(self._on_api_state)
        self._refresh_api_status()

    def _set_api_state(self, state: tuple[str, str], detail: str = "") -> None:
        """Paint the status bubble + word, and show an optional detail line."""
        colour, word = state
        self._api_bubble.setStyleSheet(
            f"color: {colour}; font-size: 14px; background-color: transparent;"
        )
        self._api_state_lbl.setText(word)
        self._api_status.setText(detail)
        self._api_status.setVisible(bool(detail))

    def _current_api_settings(self) -> ApiSettings:
        return ApiSettings(
            enabled=self._api_toggle.isChecked(),
            host=DEFAULT_HOST,  # loopback only; not exposed in the UI
            port=self._api_port.value(),
        )

    def _persist(self, settings: ApiSettings) -> None:
        self.settings.update({"enabled": settings.enabled, "port": settings.port})

    def _on_api_enable_toggled(self, checked: bool) -> None:
        settings = self._current_api_settings()
        self._persist(settings)
        if checked:
            # Show "Starting…" first, then start on the next tick so the orange
            # bubble paints before start() briefly blocks waiting for the bind.
            self._set_api_state(_API_STATE_STARTING)
            QTimer.singleShot(0, lambda: self._api_server.start(settings))
        else:
            self._api_server.stop()

    def _on_api_port_changed(self, _value: int) -> None:
        # Debounce: typing/scrolling the spinbox shouldn't thrash save + restart.
        if self._api_server.is_running:
            self._set_api_state(_API_STATE_STARTING)
        self._port_debounce.start()

    def _apply_port_change(self) -> None:
        settings = self._current_api_settings()
        self._persist(settings)
        # Apply a new port live by restarting the running server.
        if self._api_server.is_running:
            self._set_api_state(_API_STATE_STARTING)
            self._api_server.stop()
            QTimer.singleShot(0, lambda: self._api_server.start(settings))

    def _open_api_docs(self) -> None:
        url = self._api_server.docs_url()
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _on_api_state(self, running: bool, message: str) -> None:
        if running:
            self._set_api_state(_API_STATE_RUNNING)
        else:
            # Surface only genuine failures; a clean stop needs no detail line.
            detail = message if message and message != "Stopped." else ""
            self._set_api_state(_API_STATE_STOPPED, detail=detail)

        self._api_docs_btn.setEnabled(running)
        self._api_port.setEnabled(not running)
        # Reflect actual state without re-triggering the toggle handler.
        self._api_toggle.blockSignals(True)
        self._api_toggle.setChecked(running)
        self._api_toggle.blockSignals(False)

    def _refresh_api_status(self) -> None:
        self._on_api_state(self._api_server.is_running, "")
