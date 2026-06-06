"""About dialog: version, trademark disclaimer, and license."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from bridgemix.selfupdate import SelfUpdater, can_self_update, escape as _esc
from bridgemix.updates import UpdateChecker, UpdateInfo, current_version as _app_version


_DISCLAIMER = (
    "BridgeMix is an independent, unofficial project. It is <b>not affiliated "
    "with, authorized, or endorsed by Roland Corporation</b>. “Roland” "
    "and “BRIDGE CAST” are trademarks of Roland Corporation, used only to "
    "identify compatible hardware; the control protocol was determined through "
    "independent observation.<br><br>"
    "This software is provided <b>“as is”, without warranty of any "
    "kind</b>. Features described may not work on every platform, operating "
    "system, or device/firmware configuration. Use at your own risk."
)


class AboutDialog(QDialog):
    """Modal About box shown from the header info button."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About BridgeMix")
        self.setModal(True)
        self.setMinimumWidth(460)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 10, 16)
        lay.setSpacing(12)

        # Header: icon + name + version/license line
        head = QHBoxLayout()
        head.setSpacing(12)
        icon_path = Path(__file__).parents[3] / "assets" / "icon.svg"
        if icon_path.exists():
            ic = QLabel()
            ic.setPixmap(QIcon(str(icon_path)).pixmap(56, 56))
            head.addWidget(ic, alignment=Qt.AlignmentFlag.AlignTop)
        title = QLabel(
            "<div style='font-size:20px;color:#e8e8ea;'>Bridge"
            "<span style='color:#e05c12;font-weight:700;'>Mix</span></div>"
            f"<div style='color:#7a7a82;font-size:11px;margin-top:2px;'>"
            f"Version {_app_version()}  ·  GPL-3.0-or-later</div>"
        )
        title.setTextFormat(Qt.TextFormat.RichText)
        head.addWidget(title)
        head.addStretch()
        lay.addLayout(head)

        # Update status: filled in asynchronously once the check returns.
        update_row = QHBoxLayout()
        update_row.setSpacing(10)
        self._update_lbl = QLabel("Checking for updates…")
        self._update_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._update_lbl.setOpenExternalLinks(True)
        self._update_lbl.setStyleSheet("color:#7a7a82;font-size:11px;")
        update_row.addWidget(self._update_lbl)
        update_row.addStretch()
        # Manual re-query: always available, forces a fresh network check.
        self._check_btn = QPushButton("Check again")
        self._check_btn.clicked.connect(self._recheck)
        update_row.addWidget(self._check_btn)
        # Shown only when an in-place update is both available and possible.
        self._update_btn = QPushButton("Update now")
        self._update_btn.clicked.connect(self._start_update)
        self._update_btn.hide()
        update_row.addWidget(self._update_btn)
        lay.addLayout(update_row)

        self._info: UpdateInfo | None = None
        self._updater: SelfUpdater | None = None

        self._checker = UpdateChecker(self)
        self._checker.checked.connect(self._on_update_checked)
        # The startup check already refreshed the cache, so the dialog's initial
        # check reuses it; "Check again" forces a fresh network query.
        self._run_check()

        desc = QLabel(
            "A Linux desktop controller for the Roland BRIDGE CAST USB audio mixer."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#c8c8cc;font-size:12px;")
        lay.addWidget(desc)

        disclaimer = QLabel(_DISCLAIMER)
        disclaimer.setWordWrap(True)
        disclaimer.setTextFormat(Qt.TextFormat.RichText)
        disclaimer.setStyleSheet("color:#9a9aa2;font-size:11px;")
        lay.addWidget(disclaimer)

        links = QLabel(
            "&nbsp;&nbsp;·&nbsp;&nbsp;"
            "<a style='color:#e05c12;text-decoration:none;' "
            "href='https://github.com/Ex0danify/BridgeMix'>Ex0danify</a>"
            "&nbsp;&nbsp;·&nbsp;&nbsp;"
            "<a style='color:#e05c12;text-decoration:none;' "
            "href='https://www.gnu.org/licenses/gpl-3.0.html'>License (GPL-3.0)</a>"
        )
        links.setTextFormat(Qt.TextFormat.RichText)
        links.setOpenExternalLinks(True)
        links.setStyleSheet("font-size:11px;")
        lay.addWidget(links)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._close_btn)
        lay.addLayout(btn_row)

    def _run_check(self, force: bool = False) -> None:
        """Kick off a version check, reflecting the in-progress state in the UI."""
        self._check_btn.setEnabled(False)
        self._update_btn.hide()
        self._update_lbl.setText(
            "<span style='color:#7a7a82;'>Checking for updates…</span>"
        )
        self._checker.start(force=force)

    def _recheck(self) -> None:
        self._info = None
        self._run_check(force=True)

    def _on_update_checked(self, info: object) -> None:
        self._check_btn.setEnabled(True)
        if not isinstance(info, UpdateInfo):
            self._update_lbl.setText(
                "<span style='color:#7a7a82;'>Couldn’t check for updates</span>"
            )
            return
        if not info.available:
            self._update_lbl.setText(
                "<span style='color:#5a9a5a;'>✓ You’re on the latest version</span>"
            )
            return

        self._info = info
        self._update_lbl.setText(
            f"<span style='color:#e05c12;'>↑ Version {info.latest} available</span>"
        )
        if can_self_update():
            # In-place upgrade is possible: offer the button instead of a link.
            self._update_btn.show()
        else:
            # No git checkout / no git: fall back to the browser download.
            self._update_lbl.setText(
                self._update_lbl.text()
                + f"&nbsp;&nbsp;<a style='color:#e05c12;text-decoration:none;' "
                f"href='{info.url}'>Download</a>"
            )

    def _start_update(self) -> None:
        if self._info is None or (self._updater is not None and self._updater.is_running):
            return
        self._update_btn.setEnabled(False)
        self._check_btn.setEnabled(False)
        self._close_btn.setEnabled(False)
        self._update_lbl.setText(
            "<span style='color:#7a7a82;'>Updating… this can take a minute.</span>"
        )
        self._updater = SelfUpdater(self._info.latest, self)
        self._updater.finished.connect(self._on_update_finished)
        self._updater.start()

    def _on_update_finished(self, success: bool, message: str) -> None:
        color = "#5a9a5a" if success else "#e05c12"
        self._update_lbl.setText(f"<span style='color:{color};'>{_esc(message)}</span>")
        self._close_btn.setEnabled(True)
        self._check_btn.setEnabled(True)
        if success:
            self._update_btn.hide()
        else:
            self._update_btn.setEnabled(True)
