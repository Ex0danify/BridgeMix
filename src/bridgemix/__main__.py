"""Entry point: python -m bridgemix"""

import sys

from PyQt6.QtWidgets import QApplication

from bridgemix.theme import APP_STYLESHEET
from bridgemix.gui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("BridgeMix")
    app.setOrganizationName("SkyFire-Networks")
    # Wayland/KDE picks the taskbar icon by matching the window's app_id to an
    # installed .desktop file — the Qt window icon alone isn't used there. This
    # sets app_id to the reverse-DNS application id; it must match the Flatpak
    # app-id and the installed <app-id>.desktop.
    app.setDesktopFileName("io.github.ex0danify.BridgeMix")
    app.setStyleSheet(APP_STYLESHEET)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
