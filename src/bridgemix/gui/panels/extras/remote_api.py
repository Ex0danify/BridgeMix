"""
Remote API (REST) extra — a self-contained widget for the System ▸ Extras panel.

Host-side feature, unrelated to the Bridge Cast device itself: it drives the
optional :class:`~bridgemix.api.server.ApiServer` (start/stop, live port change)
and, when the optional ``fastapi``/``uvicorn`` dependencies are missing, offers an
in-app install via :class:`~bridgemix.api.installer.DependencyInstaller`.
"""
from __future__ import annotations

from PyQt6.QtCore import QTimer, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from bridgemix import theme
from bridgemix.api.installer import DependencyInstaller, can_install
from bridgemix.api.server import ApiServer, dependencies_available
from bridgemix.api.settings import ApiSettings, load_settings, save_settings
from bridgemix.gui.widgets.controls import ToggleSwitch

# REST API status-bubble states → (bubble colour, label text).
_API_STATE_RUNNING = (theme.GREEN, "Running")
_API_STATE_STARTING = (theme.ACCENT, "Starting…")
_API_STATE_STOPPED = (theme.RED, "Stopped")


class RemoteApiWidget(QWidget):
    """Enable/configure the optional REST API server. Owns its own installer."""

    def __init__(self, api_server: ApiServer, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._api_server = api_server
        self._installer = DependencyInstaller(self)

        # Coalesce rapid port-spinbox changes into a single save / restart.
        self._port_debounce = QTimer(self)
        self._port_debounce.setSingleShot(True)
        self._port_debounce.setInterval(500)
        self._port_debounce.timeout.connect(self._apply_port_change)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._api_group())

    def _api_group(self) -> QGroupBox:
        grp = QGroupBox("REMOTE API (REST)")
        lay = QVBoxLayout(grp)
        lay.setContentsMargins(10, 6, 10, 10)
        lay.setSpacing(8)

        hint = QLabel(
            "Lets third-party tools (Stream Deck, OBS, scripts) read and set "
            "device parameters over HTTP."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            "font-size: 12px; color: #9a9aa2; background-color: transparent;"
        )
        lay.addWidget(hint)

        settings = load_settings()

        # Row 1 — Enable label + orange pill toggle (matches ParamToggle layout).
        enable_row = QHBoxLayout()
        enable_row.setSpacing(8)
        enable_row.addWidget(QLabel("Enable REST API"))
        enable_row.addStretch()
        self._api_toggle = ToggleSwitch(settings.enabled and self._api_server.is_running)
        self._api_toggle.toggled.connect(self._on_api_enable_toggled)
        enable_row.addWidget(self._api_toggle)
        lay.addLayout(enable_row)

        # Row 2 — Port (left) + status bubble (right), like the Connect button's dot.
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        status_row.addWidget(QLabel("Port:"))
        self._api_port = QSpinBox()
        self._api_port.setRange(1024, 65535)
        self._api_port.setValue(settings.port)
        self._api_port.valueChanged.connect(self._on_api_port_changed)
        status_row.addWidget(self._api_port)
        status_row.addStretch()
        self._api_bubble = QLabel("●")  # ●
        self._api_state_lbl = QLabel()
        self._api_state_lbl.setStyleSheet(
            "font-size: 12px; color: #c8c8d0; background-color: transparent;"
        )
        status_row.addWidget(self._api_bubble)
        status_row.addWidget(self._api_state_lbl)
        lay.addLayout(status_row)

        # Optional detail line — only shown for errors / install hints.
        self._api_status = QLabel()
        self._api_status.setWordWrap(True)
        self._api_status.setStyleSheet(
            "font-size: 12px; color: #9a9aa2; background-color: transparent;"
        )
        lay.addWidget(self._api_status)

        self._api_docs_btn = QPushButton("Open API Docs")
        self._api_docs_btn.clicked.connect(self._open_api_docs)
        lay.addWidget(self._api_docs_btn)

        # Shown only when the optional dependencies are missing and the running
        # environment lets us install into it.
        self._api_install_btn = QPushButton("Install Dependencies")
        self._api_install_btn.clicked.connect(self._on_install_clicked)
        lay.addWidget(self._api_install_btn)

        self._api_server.state_changed.connect(self._on_api_state)
        self._installer.finished.connect(self._on_install_finished)

        self._apply_deps_state()
        return grp

    def _apply_deps_state(self) -> None:
        """Enable/disable the API controls based on whether deps are importable."""
        available = dependencies_available()
        self._api_toggle.setEnabled(available)
        self._api_port.setEnabled(available and not self._api_server.is_running)
        self._api_docs_btn.setEnabled(available and self._api_server.is_running)
        self._api_install_btn.setVisible(not available and can_install())

        if available:
            self._refresh_api_status()
        elif can_install():
            self._set_api_state(
                _API_STATE_STOPPED,
                detail="Optional dependencies (fastapi, uvicorn) are not installed.",
            )
        else:
            self._set_api_state(
                _API_STATE_STOPPED,
                detail="Not available — install the optional dependencies with "
                "pip install bridgemix[api].",
            )

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
            host=load_settings().host,  # host is loopback by default; not exposed in UI
            port=self._api_port.value(),
        )

    def _on_api_enable_toggled(self, checked: bool) -> None:
        settings = self._current_api_settings()
        save_settings(settings)
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
        save_settings(settings)
        # Apply a new port live by restarting the running server.
        if self._api_server.is_running:
            self._set_api_state(_API_STATE_STARTING)
            self._api_server.stop()
            QTimer.singleShot(0, lambda: self._api_server.start(settings))

    def _open_api_docs(self) -> None:
        url = self._api_server.docs_url()
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _on_install_clicked(self) -> None:
        self._api_install_btn.setEnabled(False)
        self._api_install_btn.setText("Installing…")
        self._set_api_state(
            _API_STATE_STOPPED,
            detail="Installing fastapi and uvicorn — this may take a minute.",
        )
        self._installer.install()

    def _on_install_finished(self, success: bool, message: str) -> None:
        self._api_install_btn.setText("Install Dependencies")
        self._api_install_btn.setEnabled(True)
        if success:
            # Re-evaluate: the button hides and the API controls enable.
            self._apply_deps_state()
        else:
            self._set_api_state(_API_STATE_STOPPED, detail=message)

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
