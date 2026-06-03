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
        self._update_lbl = QLabel("Checking for updates…")
        self._update_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._update_lbl.setOpenExternalLinks(True)
        self._update_lbl.setStyleSheet("color:#7a7a82;font-size:11px;")
        lay.addWidget(self._update_lbl)

        self._checker = UpdateChecker(self)
        self._checker.checked.connect(self._on_update_checked)
        self._checker.start()

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
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

    def _on_update_checked(self, info: object) -> None:
        if not isinstance(info, UpdateInfo):
            self._update_lbl.setText(
                "<span style='color:#7a7a82;'>Couldn’t check for updates</span>"
            )
        elif info.available:
            self._update_lbl.setText(
                f"<span style='color:#e05c12;'>↑ Version {info.latest} available</span>"
                f"&nbsp;&nbsp;<a style='color:#e05c12;text-decoration:none;' "
                f"href='{info.url}'>Download</a>"
            )
        else:
            self._update_lbl.setText(
                "<span style='color:#5a9a5a;'>✓ You’re on the latest version</span>"
            )
