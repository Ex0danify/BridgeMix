"""
MainWindow — sidebar navigation + stacked content area.

Layout:
  ┌──────────────────────────────────────────────────────────────┐
  │ Header: BridgeMix title + status + preset bar + connect btn  │
  ├──────────┬───────────────────────────────────────────────────┤
  │ Sidebar  │  Content (stacked widget)                         │
  │ [MIXER]  │  0: HomePage (hw strips + virtual + output)       │
  │ [MIC]    │  1: MicSetupPanel (mic type + profile + gain + waveform) │
  │ [MIC FX] │  2: MicFxPanel (low cut, de-esser, NS, compressor, EQ) │
  │ [MIC SFX]│  3: MicSfxPanel (voice changer + reverb)         │
  │ [GAME FX]│  4: GameFxPanel (limiter, virtual surround, game EQ) │
  │ [CHAT FX]│  5: ChatFxPanel (de-esser + compressor)          │
  │ [OUTPUT] │  6: OutputPanel                                   │
  │ [SYSTEM] │  7: SystemPanel                                   │
  │ [EXTRAS] │  8: ExtrasPanel (host-side extras, e.g. REST API) │
  │ [MIDI]   │  9: MidiMonitor                                   │
  └──────────┴───────────────────────────────────────────────────┘
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsBlurEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)


class _DisconnectOverlay(QWidget):
    """Semi-transparent overlay drawn over the content area when disconnected."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(10)

        title = QLabel("Not Connected")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        title.setStyleSheet(
            "color: #e8e8ea; font-size: 18px; font-weight: 700; background: transparent;"
        )

        sub = QLabel("Connect your Bridge Cast to continue")
        sub.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        sub.setStyleSheet("color: #e05c12; font-size: 12px; background: transparent;")

        lay.addWidget(title)
        lay.addWidget(sub)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(10, 10, 12, 200))
        p.end()

from bridgemix.api.gateway import BridgeGateway
from bridgemix.api.server import ApiServer
from bridgemix.api.settings import load_settings
from bridgemix.device.bridge_cast import BridgeCast
from bridgemix.midi.detector import find_device
from bridgemix.gui.panels.home_page import HomePage
from bridgemix.gui.panels.extras import ExtrasPanel
from bridgemix.gui.panels.chat_fx_panel import ChatFxPanel
from bridgemix.gui.panels.game_fx_panel import GameFxPanel
from bridgemix.gui.panels.mic_fx_panel import MicFxPanel
from bridgemix.gui.panels.mic_setup_panel import MicSetupPanel
from bridgemix.gui.panels.mic_sfx_panel import MicSfxPanel
from bridgemix.gui.panels.midi_monitor import MidiMonitor
from bridgemix.gui.panels.output_panel import OutputPanel
from bridgemix.gui.widgets.preset_bar import PresetBar
from bridgemix.gui.panels.routing_panel import RoutingPanel
from bridgemix.gui.panels.system_panel import SystemPanel
from bridgemix.routing.backend import is_supported as routing_is_supported
from bridgemix.routing.monitor import RoutingMonitor


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("BridgeMix — Roland Bridge Cast Controller")
        self.setMinimumSize(960, 700)
        self.resize(1088, 850)

        _icon = Path(__file__).parents[3] / "assets" / "icon.svg"
        if _icon.exists():
            self.setWindowIcon(QIcon(str(_icon)))

        self._bridge = BridgeCast(self)
        self._bridge.status_message.connect(self._on_status)
        self._bridge.connected.connect(self._on_connected)

        # Optional REST API. The gateway marshals server-thread calls onto this
        # (GUI) thread; the server is owned here so it stops cleanly on quit.
        self._api_gateway = BridgeGateway(self._bridge, self)
        self._api_server = ApiServer(self._api_gateway, self)
        api_settings = load_settings()
        if api_settings.enabled:
            self._api_server.start(api_settings)

        # Close-button behaviour. None until the user picks once per session;
        # then "tray" or "quit" is reused for the rest of the session without
        # asking again. _quitting bypasses the prompt when we close for real.
        self._close_choice: str | None = None
        self._quitting = False

        self._setup_ui()
        self._setup_tray()

        # Auto-detect on startup
        QTimer.singleShot(300, self._auto_connect)

    # ── System tray ─────────────────────────────────────────────────────────────

    def _setup_tray(self) -> None:
        self._tray: QSystemTrayIcon | None = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        tray = QSystemTrayIcon(self.windowIcon(), self)
        tray.setToolTip("BridgeMix")

        menu = QMenu()
        show_action = QAction("Show BridgeMix", self)
        show_action.triggered.connect(self._restore_from_tray)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)
        tray.show()
        self._tray = tray

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._restore_from_tray()

    def _restore_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _minimize_to_tray(self) -> None:
        self.hide()
        if self._tray is not None:
            self._tray.showMessage(
                "BridgeMix",
                "Still running in the tray. Click the icon to restore.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )

    def _quit_app(self) -> None:
        self._quitting = True
        # Closing a hidden window does not fire quitOnLastWindowClosed, and the
        # tray icon keeps the event loop alive, so quit the app explicitly.
        if self._tray is not None:
            self._tray.hide()
        self.close()
        QApplication.quit()

    # ── UI setup ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._make_header())

        # Sidebar + content live in one wrapper so it can be blurred as a unit
        # when the routing drawer opens (the drawer itself stays sharp).
        self._main_area = QWidget()
        main_lay = QHBoxLayout(self._main_area)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        main_lay.addWidget(self._make_sidebar())
        main_lay.addWidget(self._make_content(), stretch=1)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._main_area, stretch=1)

        # Application audio routing — independent of the MIDI connection, so it
        # lives outside the disconnect overlay and runs whenever the app is open.
        # Linux-only (PipeWire/PulseAudio); on Windows/macOS the OS handles this,
        # so the panel is omitted entirely.
        self._routing_monitor: RoutingMonitor | None = None
        if routing_is_supported():
            self._routing_monitor = RoutingMonitor(parent=self)
            panel = RoutingPanel(self._routing_monitor)
            panel.expandedChanged.connect(self._on_routing_expanded)
            body.addWidget(panel)
            self._routing_monitor.start()
            self._setup_routing_blur()

        root.addLayout(body, stretch=1)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Not connected — plug in Bridge Cast and click Connect")

        # About/help button, pinned to the footer's bottom-right.
        about_btn = QPushButton("ⓘ")
        about_btn.setObjectName("btn_about")
        about_btn.setToolTip("About BridgeMix")
        about_btn.setFixedSize(24, 24)
        about_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        about_btn.clicked.connect(self._show_about)
        self._status_bar.addPermanentWidget(about_btn)

        # Start with overlay visible; hidden once connected signal fires.
        self._overlay.show()
        self._overlay.raise_()

    # ── Routing drawer blur ─────────────────────────────────────────────────────

    def _setup_routing_blur(self) -> None:
        """Blur the main area while the routing drawer is open, to set it apart."""
        self._blur = QGraphicsBlurEffect(self)
        self._blur.setBlurRadius(0.0)
        self._blur.setEnabled(False)   # no render cost while collapsed
        self._main_area.setGraphicsEffect(self._blur)

        self._blur_anim = QPropertyAnimation(self._blur, b"blurRadius", self)
        self._blur_anim.setDuration(190)   # matches the drawer slide
        self._blur_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._blur_anim.finished.connect(self._on_blur_anim_finished)

    def _on_routing_expanded(self, expanded: bool) -> None:
        self._blur_anim.stop()
        self._blur_anim.setStartValue(self._blur.blurRadius())
        if expanded:
            self._blur.setEnabled(True)
            self._blur_anim.setEndValue(9.0)
        else:
            self._blur_anim.setEndValue(0.0)
        self._blur_anim.start()

    def _on_blur_anim_finished(self) -> None:
        if self._blur.blurRadius() <= 0.01:
            self._blur.setEnabled(False)

    # ── Header ────────────────────────────────────────────────────────────────

    def _make_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(48)
        row = QHBoxLayout(header)
        row.setContentsMargins(14, 0, 14, 0)
        row.setSpacing(10)

        brand = QLabel(
            "<span style='font-weight:300;letter-spacing:-0.01em;'>Bridge</span>"
            "<span style='color:#e05c12;font-weight:700;'>Mix</span>"
        )
        brand.setStyleSheet("font-size: 20px; color: #e8e8ea;")
        row.addWidget(brand)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        row.addWidget(sep)

        row.addWidget(PresetBar(self._bridge))
        row.addStretch()

        self._device_lbl = QLabel("")
        self._device_lbl.setStyleSheet("color: #7a7a82; font-size: 11px;")
        row.addWidget(self._device_lbl)
        self._bridge.device_info_updated.connect(
            lambda model, fw: self._device_lbl.setText(f"{model}  ·  FW {fw}")
        )

        self._conn_btn = QPushButton("●  Connect")
        self._conn_btn.setObjectName("btn_connect")
        self._conn_btn.setProperty("connected", "false")
        self._conn_btn.setToolTip("Click to connect to Bridge Cast")
        self._conn_btn.clicked.connect(self._toggle_connection)
        row.addWidget(self._conn_btn)
        return header

    def _show_about(self) -> None:
        from bridgemix.gui.widgets.about_dialog import AboutDialog
        AboutDialog(self).exec()

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _make_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(68)
        vlay = QVBoxLayout(sidebar)
        vlay.setContentsMargins(4, 10, 4, 10)
        vlay.setSpacing(2)

        self._nav_btns: list[QPushButton] = []
        pages = [
            ("MIXER",     0),
            ("MIC SET.", 1),
            ("MIC FX",    2),
            ("VOICE FX",  3),
            ("GAME FX",   4),
            ("CHAT FX",   5),
            ("OUTPUT",    6),
            ("SYSTEM",    7),
            ("EXTRAS",    8),
            ("MIDI MON", 9),
        ]
        for label, idx in pages:
            btn = QPushButton(label)
            btn.setObjectName("nav_btn")
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setFixedHeight(52)
            btn.clicked.connect(lambda _, i=idx: self._switch_page(i))
            vlay.addWidget(btn)
            self._nav_btns.append(btn)

        vlay.addStretch()
        self._nav_btns[0].setChecked(True)
        return sidebar

    # ── Content stack ─────────────────────────────────────────────────────────

    def _make_content(self) -> QStackedWidget:
        self._stack = QStackedWidget()
        b = self._bridge

        self._stack.addWidget(HomePage(b))        # 0 — main mixer
        self._stack.addWidget(MicSetupPanel(b))   # 1 — mic input (type + gain + waveform)
        self._stack.addWidget(MicFxPanel(b))      # 2 — low cut, de-esser, NS, compressor, EQ
        self._stack.addWidget(MicSfxPanel(b))     # 3 — voice changer + reverb
        self._stack.addWidget(GameFxPanel(b))     # 4 — limiter, virtual surround, game EQ
        self._stack.addWidget(ChatFxPanel(b))     # 5 — chat de-esser + compressor
        self._stack.addWidget(OutputPanel(b))     # 6 — output routing
        self._stack.addWidget(SystemPanel(b))     # 7 — system settings
        self._stack.addWidget(ExtrasPanel(b, self._api_server))  # 8 — host-side extras
        self._stack.addWidget(MidiMonitor(b))     # 9 — MIDI debug

        self._overlay = _DisconnectOverlay(self._stack)
        self._overlay.resize(self._stack.size())
        self._overlay.raise_()
        self._stack.installEventFilter(self)
        return self._stack

    def eventFilter(self, obj: object, event: QEvent) -> bool:
        if obj is self._stack and event.type() == QEvent.Type.Resize:
            self._overlay.resize(self._stack.size())
            self._overlay.raise_()
        return super().eventFilter(obj, event)

    def _switch_page(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._nav_btns):
            btn.setChecked(i == idx)
        if self._overlay.isVisible():
            self._overlay.raise_()

    # ── Connection ────────────────────────────────────────────────────────────

    def _auto_connect(self) -> None:
        tx, rx = find_device()
        if tx and rx:
            self._bridge.connect_device(tx, rx)

    def _toggle_connection(self) -> None:
        if self._bridge.is_connected:
            self._bridge.disconnect_device()
        else:
            tx, rx = find_device()
            if tx and rx:
                self._bridge.connect_device(tx, rx)
            else:
                self._status_bar.showMessage(
                    "Bridge Cast MIDI ports not found — is the device plugged in?"
                )

    def _on_connected(self, connected: bool) -> None:
        if connected:
            self._conn_btn.setText("●  Connected")
            self._conn_btn.setToolTip("Click to disconnect")
            self._conn_btn.setProperty("connected", "true")
            self._overlay.hide()
        else:
            self._conn_btn.setText("●  Connect")
            self._conn_btn.setToolTip("Click to connect to Bridge Cast")
            self._conn_btn.setProperty("connected", "false")
            self._overlay.show()
            self._overlay.raise_()
        self._conn_btn.style().unpolish(self._conn_btn)
        self._conn_btn.style().polish(self._conn_btn)

    def _on_status(self, msg: str) -> None:
        self._status_bar.showMessage(msg)

    def _ask_close_behaviour(self) -> str:
        """Prompt for close vs. minimise-to-tray; returns "quit", "tray" or "cancel"."""
        box = QMessageBox(self)
        box.setWindowTitle("Close BridgeMix")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText("Close BridgeMix or keep it running in the system tray?")
        box.setInformativeText("Your choice is remembered until you quit BridgeMix.")
        tray_btn = box.addButton("Minimize to Tray", QMessageBox.ButtonRole.AcceptRole)
        quit_btn = box.addButton("Close", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(tray_btn)
        box.exec()

        clicked = box.clickedButton()
        if clicked is tray_btn:
            return "tray"
        if clicked is quit_btn:
            return "quit"
        return "cancel"

    def closeEvent(self, event):  # type: ignore[override]
        # A real quit (tray menu / "Close" choice) tears down and exits.
        if self._quitting:
            self._api_server.stop()
            if self._routing_monitor is not None:
                self._routing_monitor.stop()
            self._bridge.disconnect_device()
            super().closeEvent(event)
            return

        # No tray available → nothing to minimise into; quit as before.
        if self._tray is None:
            self._api_server.stop()
            if self._routing_monitor is not None:
                self._routing_monitor.stop()
            self._bridge.disconnect_device()
            super().closeEvent(event)
            return

        choice = self._close_choice
        if choice is None:
            choice = self._ask_close_behaviour()
            if choice == "cancel":
                event.ignore()
                return
            self._close_choice = choice

        if choice == "tray":
            event.ignore()
            self._minimize_to_tray()
            return

        # choice == "quit"
        self._api_server.stop()
        if self._routing_monitor is not None:
            self._routing_monitor.stop()
        self._bridge.disconnect_device()
        if self._tray is not None:
            self._tray.hide()
        super().closeEvent(event)
